import asyncio
import functools
import hashlib
import os
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.types import Command
from openai import AsyncOpenAI
from pydantic import BaseModel

from simulator import graph, make_initial_state, model, session_store
from simulator import (
    SYSTEM_PITCH_REPORT,
    SYSTEM_CAR_REPORT,
    SYSTEM_TECHNICAL_REPORT,
    SYSTEM_LEADERSHIP_REPORT,
    SYSTEM_MOTIVATION_REPORT,
)

openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ── TTS disk cache ────────────────────────────────────────────────────────────
# Audio is generated once and stored in static/tts_cache/ keyed by md5(voice:text).
# Subsequent requests for the same text+voice are served directly from disk — free.
TTS_CACHE_DIR = Path(__file__).parent / "static" / "tts_cache"
TTS_CACHE_DIR.mkdir(exist_ok=True)

app = FastAPI()

# Maps report phase name → report system prompt.
# Used when the report node fires "[report_ready]" — api.py streams the report
# with model.astream() and resumes the graph with the full text for archiving.
FASE_TO_REPORT_SYSTEM = {
    "elevator_pitch_report": SYSTEM_PITCH_REPORT,
    "CAR_report":            SYSTEM_CAR_REPORT,
    "technical_report":      SYSTEM_TECHNICAL_REPORT,
    "leadership_report":     SYSTEM_LEADERSHIP_REPORT,
    "motivation_report":     SYSTEM_MOTIVATION_REPORT,
}


async def _stream_to_client(ws: WebSocket, messages: list, system_prompt: str, voice: str = "nova") -> str:
    """Stream LLM tokens directly to the client as stream_chunk events.

    Runs in parallel with graph.invoke (interview phase) or as the primary
    generator (report phase).  Returns the full accumulated text so report
    nodes can archive it without a second LLM call.
    """
    full_text = ""
    try:
        async for chunk in model.astream(
            [SystemMessage(content=[{
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }])] + messages
        ):
            if chunk.content:
                full_text += chunk.content
                await ws.send_json({"type": "stream_chunk", "text": chunk.content, "voice": voice})
    except Exception as exc:
        print(f"[stream error] {exc}")
    await ws.send_json({"type": "stream_done"})
    return full_text


# ── Session history endpoints ────────────────────────────────────────────────

class SessionUpsert(BaseModel):
    startedAt:    int
    lastActiveAt: int
    fase:         str
    history:      list


@app.get("/sessions")
async def list_sessions():
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, session_store.list_sessions)


@app.put("/sessions/{thread_id}")
async def upsert_session(thread_id: str, body: SessionUpsert):
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None,
        lambda: session_store.upsert(
            thread_id,
            body.startedAt,
            body.lastActiveAt,
            body.fase,
            body.history,
        ),
    )
    return {"ok": True}


@app.delete("/sessions/{thread_id}")
async def delete_session(thread_id: str):
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, lambda: session_store.delete(thread_id))
    return {"ok": True}


# ── Audio endpoints ──────────────────────────────────────────────────────────

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
async def tts(text: str, voice: str = "nova"):
    # Allowed voices: alloy, echo, fable, onyx, nova, shimmer
    allowed = {"alloy", "echo", "fable", "onyx", "nova", "shimmer"}
    if voice not in allowed:
        voice = "nova"

    # Check disk cache first — same text+voice always produces identical audio.
    cache_key  = hashlib.md5(f"{voice}:{text}".encode()).hexdigest()
    cache_file = TTS_CACHE_DIR / f"{cache_key}.mp3"
    if cache_file.exists():
        return Response(content=cache_file.read_bytes(), media_type="audio/mpeg")

    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            response = await openai_client.audio.speech.create(
                model="tts-1",
                voice=voice,
                input=text,
            )
            audio_bytes = response.content
            cache_file.write_bytes(audio_bytes)   # save for future requests
            return Response(content=audio_bytes, media_type="audio/mpeg")
        except Exception as exc:
            last_exc = exc
            if attempt < 2:
                await asyncio.sleep(0.5 * (attempt + 1))

    print(f"[tts] failed after 3 attempts: {last_exc}")
    raise HTTPException(status_code=503, detail="TTS service temporarily unavailable")


@app.websocket("/ws")
async def interview_ws(ws: WebSocket):
    await ws.accept()
    loop = asyncio.get_running_loop()

    # ── Session setup ────────────────────────────────────────────────────────
    # Listen briefly for a {"type": "resume", "thread_id": "…"} from the client.
    # If present, we restore the existing LangGraph checkpoint instead of starting
    # a new session.  This allows the interview to survive page refreshes.
    thread_id: str = str(uuid.uuid4())
    is_resuming = False
    try:
        init = await asyncio.wait_for(ws.receive_json(), timeout=0.5)
        if init.get("type") == "resume" and init.get("thread_id"):
            thread_id = init["thread_id"]
            is_resuming = True
    except Exception:
        pass

    config = {"configurable": {"thread_id": thread_id}}
    # Always echo the thread_id back so the client can persist it.
    await ws.send_json({"type": "session", "thread_id": thread_id})

    try:
        if is_resuming:
            state_snap = await loop.run_in_executor(
                None, functools.partial(graph.get_state, config)
            )
            if state_snap and state_snap.values:
                interrupts_list = [
                    intr for task in state_snap.tasks for intr in task.interrupts
                ]
                result = dict(state_snap.values)
                result["__interrupt__"] = interrupts_list
                prev_msg_count       = len(state_snap.values.get("messages", []))
                prev_report_streamed = False
                prev_was_skip        = False
                await ws.send_json({"type": "resumed"})
                await ws.send_json({"type": "phase", "fase": result.get("fase", "")})
            else:
                is_resuming = False  # no checkpoint — fall through to fresh start

        if not is_resuming:
            initial_state = make_initial_state()
            result = await loop.run_in_executor(
                None, functools.partial(graph.invoke, initial_state, config)
            )
            prev_msg_count       = 1
            prev_report_streamed = False
            prev_was_skip        = False

        while True:
            messages: list = result.get("messages", [])
            interrupts = result.get("__interrupt__", [])
            fase = result.get("fase", "")

            # Notify the client of the current phase so the progress bar can update.
            await ws.send_json({"type": "phase", "fase": fase})

            # Save and reset per-iteration flags
            was_report_streamed  = prev_report_streamed
            prev_report_streamed = False
            prev_was_skip        = False

            # ── New-message filtering ─────────────────────────────────────────
            # • First AIMessage followed by a real HumanMessage → the question
            #   that triggered the interrupt (already shown) → skip.
            # • First AIMessage followed by "[acknowledged — ready for next phase]"
            #   → phase report archived by the graph → suppress if already streamed.
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
                    # Report was already streamed with onyx voice — suppress the
                    # graph's archived copy so it doesn't appear as a second bubble.
                    if was_report_streamed and had_transition:
                        continue
                is_scorecard = "INTERVIEW SCORECARD" in msg.content or fase == "done"
                msg_type = "feedback" if is_scorecard else "transition"
                await ws.send_json({"type": msg_type, "text": msg.content})

            if not interrupts:
                await ws.send_json({"type": "done"})
                break

            question = interrupts[0].value

            # ── Report streaming ──────────────────────────────────────────────
            # When the report node fires "[report_ready]", stream the report now
            # with the Judge voice.  Resume the graph with the full text so the
            # report node can archive it without a second LLM call.
            if question == "[report_ready]":
                report_system = FASE_TO_REPORT_SYSTEM.get(fase, "")
                phase_messages = result.get("phase_messages") or []
                if report_system:
                    full_text = await _stream_to_client(
                        ws, phase_messages, report_system, voice="onyx"
                    )
                else:
                    full_text = ""
                # Judge is done — Maria takes the floor back.
                await ws.send_json({
                    "type": "ai",
                    "text": "Take your time with that. Whenever you're ready, just let me know.",
                })
                prev_msg_count       = len(messages)
                prev_report_streamed = bool(full_text)
                result = await loop.run_in_executor(
                    None,
                    functools.partial(graph.invoke, Command(resume=full_text or "[no_report]"), config),
                )
                continue  # restart loop — next interrupt is the next phase's question

            if had_transition:
                # Phase transition: report is shown/spoken. Wait for the user to
                # signal they're ready before showing the next phase question.
                await ws.send_json({"type": "await_input"})
                while True:
                    data = await ws.receive_json()
                    if data.get("type") == "ping":
                        await ws.send_json({"type": "pong"})
                        continue
                    ready_text = data.get("text", "").strip()
                    if ready_text:
                        break
                await ws.send_json({"type": "user", "text": ready_text})
                await ws.send_json({"type": "ai", "text": question})
            else:
                await ws.send_json({"type": "ai", "text": question})

            # Wait for the user's answer to the current question.
            # Only "skip" (or "s") is treated as an explicit phase skip —
            # everything else goes straight to the graph.
            _SKIP_KEYWORDS = {"skip", "s"}
            while True:
                data = await ws.receive_json()
                if data.get("type") == "ping":
                    await ws.send_json({"type": "pong"})
                    continue
                user_text = data.get("text", "").strip()
                if not user_text:
                    continue
                if user_text.lower() in _SKIP_KEYWORDS:
                    user_text = "skip"
                    prev_was_skip = True
                break

            await ws.send_json({"type": "user", "text": user_text})

            prev_msg_count = len(messages)

            try:
                # Run graph evaluation and wait for the result.
                # Parallel streaming was removed: the streaming LLM and the graph LLM
                # independently decide what to ask next and often diverge, causing Maria
                # to show two different questions and then evaluate answers against the
                # wrong one.  A single graph call with the typing indicator is correct
                # and the 3–7 s wait is acceptable for an interview context.
                result = await loop.run_in_executor(
                    None,
                    functools.partial(graph.invoke, Command(resume=user_text), config),
                )
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
