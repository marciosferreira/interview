import asyncio
import functools
import os
import uuid
from pathlib import Path

from fastapi import FastAPI, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.types import Command
from openai import AsyncOpenAI

from simulator import graph, make_initial_state, model
from simulator import (
    SYSTEM_PITCH, SYSTEM_CAR, SYSTEM_TECHNICAL,
    SYSTEM_LEADERSHIP, SYSTEM_MOTIVATION, SYSTEM_MARCIO_Q,
)

openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = FastAPI()

# Maps the active phase to the system prompt used for parallel streaming
FASE_TO_SYSTEM = {
    "elevator_pitch":   SYSTEM_PITCH,
    "CAR":              SYSTEM_CAR,
    "technical":        SYSTEM_TECHNICAL,
    "leadership":       SYSTEM_LEADERSHIP,
    "motivation":       SYSTEM_MOTIVATION,
    "marcio_questions": SYSTEM_MARCIO_Q,
}


async def _stream_to_client(ws: WebSocket, messages: list, system_prompt: str) -> bool:
    """Stream LLM tokens directly to the client as stream_chunk events.

    Runs in parallel with graph.invoke so the user hears audio in ~0.5s
    instead of waiting for the full structured-output JSON to complete.
    Returns True if any content was actually streamed.
    """
    streamed = False
    try:
        async for chunk in model.astream(
            [SystemMessage(content=system_prompt)] + messages
        ):
            if chunk.content:
                await ws.send_json({"type": "stream_chunk", "text": chunk.content})
                streamed = True
    except Exception as exc:
        print(f"[stream error] {exc}")
    await ws.send_json({"type": "stream_done"})
    return streamed


@app.post("/stt")
async def stt(audio: UploadFile):
    audio_bytes = await audio.read()
    transcript = await openai_client.audio.transcriptions.create(
        model="whisper-1",
        file=(audio.filename or "audio.webm", audio_bytes, audio.content_type or "audio/webm"),
        language="en",
    )
    return {"text": transcript.text}


@app.get("/tts")
async def tts(text: str):
    response = await openai_client.audio.speech.create(
        model="tts-1",
        voice="nova",
        input=text,
    )
    return Response(content=response.content, media_type="audio/mpeg")


@app.websocket("/ws")
async def interview_ws(ws: WebSocket):
    await ws.accept()
    loop = asyncio.get_running_loop()

    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    initial_state = make_initial_state()

    try:
        result = await loop.run_in_executor(
            None, functools.partial(graph.invoke, initial_state, config)
        )

        prev_msg_count = 1
        did_stream = False   # True when the previous invoke used parallel streaming
        question   = ""      # last interrupt value, needed for next stream_messages
        prev_was_skip = False  # True when the previous user input was "skip"

        while True:
            messages: list = result.get("messages", [])
            interrupts = result.get("__interrupt__", [])
            fase = result.get("fase", "")

            # Save and reset per-iteration flags
            was_streamed  = did_stream
            did_stream    = False
            was_skip      = prev_was_skip
            prev_was_skip = False

            # ── New-message filtering ─────────────────────────────────────────
            # Use a single heuristic for both streaming and non-streaming paths:
            #   • First AIMessage followed by a real user HumanMessage (not
            #     "[acknowledged...]") → echo of the interrupt question that was
            #     already shown/spoken → skip.
            #   • First AIMessage followed by "[acknowledged — ready for next phase]"
            #     → completion feedback, NEW content → show as transition.
            new_messages = messages[prev_msg_count:]
            first_ai_idx = next(
                (i for i, m in enumerate(new_messages) if isinstance(m, AIMessage)), None
            )

            # True when a phase transition occurred in this result
            had_transition = any(
                isinstance(m, HumanMessage) and "[acknowledged" in m.content
                for m in new_messages
            )

            for i, msg in enumerate(new_messages):
                if not isinstance(msg, AIMessage):
                    continue
                # When the user explicitly skipped, the streaming bubble already
                # acknowledged it ("Got it — moving on.").  Suppress ALL graph
                # AIMessages for this round (the echoed question AND the structured
                # feedback) — the graph produces two of them when skipping, but only
                # the streaming bubble should appear.  The per-phase feedback will
                # still be visible in the final scorecard.
                if had_transition and was_skip and "INTERVIEW SCORECARD" not in msg.content:
                    continue
                if i == first_ai_idx:
                    next_msg = new_messages[i + 1] if i + 1 < len(new_messages) else None
                    is_replay = (
                        next_msg is not None
                        and isinstance(next_msg, HumanMessage)
                        and "[acknowledged" not in next_msg.content
                    )
                    if is_replay:
                        continue  # already shown/spoken — skip
                    # When streaming ran (was_streamed=True) and no phase transition
                    # occurred, the first AIMessage is the graph's re-generation of
                    # what was already shown in the streaming bubble.  Skip it to
                    # avoid a duplicate bubble and competing TTS — unless it IS the
                    # scorecard itself (which has no streaming equivalent).
                    if was_streamed and not had_transition and "INTERVIEW SCORECARD" not in msg.content:
                        continue
                is_scorecard = "INTERVIEW SCORECARD" in msg.content or fase == "done"
                msg_type = "feedback" if is_scorecard else "transition"
                await ws.send_json({"type": msg_type, "text": msg.content})

            if not interrupts:
                await ws.send_json({"type": "done"})
                break

            question = interrupts[0].value

            if had_transition:
                # Phase transition: feedback is shown/spoken. Wait for the user to
                # signal they're ready (any input) before showing the next phase
                # question — so the two don't appear simultaneously.
                await ws.send_json({"type": "await_input"})
                while True:
                    data = await ws.receive_json()
                    ready_text = data.get("text", "").strip()
                    if ready_text:
                        break
                await ws.send_json({"type": "user", "text": ready_text})
                # Now show the next phase's opening question.
                await ws.send_json({"type": "ai", "text": question})
            elif was_streamed:
                # Streaming bubble already shows the response — don't add a second
                # bubble for the same interrupt question. Just enable input after TTS.
                await ws.send_json({"type": "await_input"})
            else:
                await ws.send_json({"type": "ai", "text": question})

            # Wait for the user's answer to the current question.
            # Only "skip" (or "s") is treated as an explicit phase skip —
            # everything else goes straight to the graph.
            _SKIP_KEYWORDS = {"skip", "s"}
            while True:
                data = await ws.receive_json()
                user_text = data.get("text", "").strip()
                if not user_text:
                    continue
                if user_text.lower() in _SKIP_KEYWORDS:
                    user_text = "skip"
                    prev_was_skip = True
                break

            await ws.send_json({"type": "user", "text": user_text})

            prev_msg_count = len(messages)
            system_prompt = FASE_TO_SYSTEM.get(fase, "")

            try:
                if system_prompt:
                    # ── Parallel: stream reply to client + run graph evaluation ──
                    # Use the graph's phase_messages (current-phase transcript only)
                    # so the streaming model never sees prior-phase history.
                    phase_messages = result.get("phase_messages") or messages
                    stream_messages = phase_messages + [
                        AIMessage(content=question),
                        HumanMessage(content=user_text),
                    ]
                    stream_task = asyncio.create_task(
                        _stream_to_client(ws, stream_messages, system_prompt)
                    )
                    graph_future = loop.run_in_executor(
                        None,
                        functools.partial(graph.invoke, Command(resume=user_text), config),
                    )
                    outcomes = await asyncio.gather(
                        stream_task, graph_future, return_exceptions=True
                    )
                    streamed, result = outcomes
                    if isinstance(result, Exception):
                        raise result
                    did_stream = bool(streamed) and not isinstance(streamed, Exception)
                else:
                    # No streaming: either no system prompt, or input too short
                    # to warrant a streamed response (avoids spurious feedback bubbles).
                    result = await loop.run_in_executor(
                        None,
                        functools.partial(graph.invoke, Command(resume=user_text), config),
                    )
                    did_stream = False

            except Exception as exc:
                import traceback
                traceback.print_exc()
                await ws.send_json({
                    "type": "error",
                    "text": f"[Server error — please reload and try again]\n{exc}",
                })
                break

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        import traceback
        traceback.print_exc()
        try:
            await ws.send_json({
                "type": "error",
                "text": f"[Connection error — please reload]\n{exc}",
            })
        except Exception:
            pass


# Serve the frontend — mount last so /ws and /stt are registered first
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
