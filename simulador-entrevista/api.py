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
                if i == first_ai_idx:
                    next_msg = new_messages[i + 1] if i + 1 < len(new_messages) else None
                    is_replay = (
                        next_msg is not None
                        and isinstance(next_msg, HumanMessage)
                        and "[acknowledged" not in next_msg.content
                    )
                    if is_replay:
                        continue  # already shown/spoken — skip
                    # When the user explicitly skipped, the streaming bubble already
                    # acknowledged it ("Got it — moving on.").  Suppress the graph's
                    # structured feedback block (it will appear in the final scorecard)
                    # so the user doesn't see the same phase feedback twice.
                    if had_transition and was_skip:
                        continue
                is_scorecard = "INTERVIEW SCORECARD" in msg.content or fase == "done"
                msg_type = "feedback" if is_scorecard else "transition"
                await ws.send_json({"type": msg_type, "text": msg.content})

            if not interrupts:
                await ws.send_json({"type": "done"})
                break

            question = interrupts[0].value

            if had_transition:
                # Phase transition: the transition feedback TTS is still playing.
                # Send the new question as "phase_question" so the client can
                # buffer it and only show/speak it after transition TTS drains.
                await ws.send_json({"type": "phase_question", "text": question})
            elif was_streamed:
                # Streaming bubble already shows the response — don't add a second
                # bubble for the same interrupt question. Just enable input after TTS.
                await ws.send_json({"type": "await_input"})
            else:
                await ws.send_json({"type": "ai", "text": question})

            # Wait for the user's spoken/typed response
            data = await ws.receive_json()
            user_text = data.get("text", "").strip()
            if not user_text:
                continue

            # Normalise skip intent: only the exact word "skip" (case-insensitive)
            # triggers a phase skip.  Casual phrases like "move on", "Y", "ok",
            # "let's continue" are passed through as normal answers so the LLM
            # evaluates them as content — not as skip commands.
            _SKIP_KEYWORDS = {"skip", "s"}
            if user_text.lower() in _SKIP_KEYWORDS:
                user_text = "skip"
                prev_was_skip = True

            await ws.send_json({"type": "user", "text": user_text})

            prev_msg_count = len(messages)
            system_prompt = FASE_TO_SYSTEM.get(fase, "")

            try:
                # Only stream if the user gave a substantive answer (≥ 8 words).
                # Short inputs like "Y", "ok", "let's go", "move on" are
                # meta-commands or non-answers.  Streaming them produces
                # confusing feedback bubbles; let the graph handle them silently.
                _is_substantive = len(user_text.split()) >= 8

                if system_prompt and _is_substantive:
                    # ── Parallel: stream reply to client + run graph evaluation ──
                    # Trim stream context to the current phase only: messages after
                    # the last "[acknowledged — ready for next phase]" sentinel.
                    # This prevents the streaming model from seeing prior-phase
                    # history (e.g. elevator-pitch feedback) and generating stale
                    # feedback while the graph is already in a later phase.
                    last_ack = max(
                        (i for i, m in enumerate(messages)
                         if isinstance(m, HumanMessage) and "[acknowledged" in m.content),
                        default=-1,
                    )
                    phase_messages = messages[last_ack + 1:]
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
