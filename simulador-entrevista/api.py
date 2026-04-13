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

        while True:
            messages: list = result.get("messages", [])
            interrupts = result.get("__interrupt__", [])
            fase = result.get("fase", "")

            # ── New-message filtering ─────────────────────────────────────────
            # When did_stream=True, the conversational reply was already sent as
            # stream_chunk events — skip the first new AIMessage (it's that reply).
            #
            # When did_stream=False, use the structural heuristic:
            #   • First AIMessage followed by a real user HumanMessage → re-generated
            #     interrupt question, already shown → skip.
            #   • First AIMessage followed by "[acknowledged...]" → completion feedback,
            #     NEW content → show as transition.
            new_messages = messages[prev_msg_count:]
            first_ai_idx = next(
                (i for i, m in enumerate(new_messages) if isinstance(m, AIMessage)), None
            )
            for i, msg in enumerate(new_messages):
                if not isinstance(msg, AIMessage):
                    continue
                if i == first_ai_idx:
                    if did_stream:
                        did_stream = False
                        continue  # already sent via stream_chunk — don't repeat
                    next_msg = new_messages[i + 1] if i + 1 < len(new_messages) else None
                    is_replay = (
                        next_msg is not None
                        and isinstance(next_msg, HumanMessage)
                        and "[acknowledged" not in next_msg.content
                    )
                    if is_replay:
                        continue
                is_scorecard = "INTERVIEW SCORECARD" in msg.content or fase == "done"
                msg_type = "feedback" if is_scorecard else "transition"
                await ws.send_json({"type": msg_type, "text": msg.content})

            if not interrupts:
                await ws.send_json({"type": "done"})
                break

            question = interrupts[0].value
            await ws.send_json({"type": "ai", "text": question})

            # Wait for the user's spoken/typed response
            data = await ws.receive_json()
            user_text = data.get("text", "").strip()
            if not user_text:
                continue

            await ws.send_json({"type": "user", "text": user_text})

            prev_msg_count = len(messages)
            system_prompt = FASE_TO_SYSTEM.get(fase, "")

            try:
                if system_prompt:
                    # ── Parallel: stream reply to client + run graph evaluation ──
                    # The streaming LLM needs the full context: state messages +
                    # the question that was shown (interrupt value) + user's answer.
                    # These are NOT yet in state["messages"] at this point.
                    stream_messages = messages + [
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
                    # Feedback / unknown phase — no streaming, normal invoke
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
