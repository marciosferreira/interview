import asyncio
import functools
import os
import uuid
from pathlib import Path

from fastapi import FastAPI, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import Command
from openai import AsyncOpenAI

from simulator import graph, make_initial_state


def _same_message(a: str, b: str) -> bool:
    """Compare two strings tolerating minor LLM re-generation artifacts
    (curly vs straight quotes, whitespace differences)."""
    if a == b:
        return True
    import re
    def norm(s: str) -> str:
        s = s.strip()
        s = s.replace('\u201c', '"').replace('\u201d', '"')   # " " → "
        s = s.replace('\u2018', "'").replace('\u2019', "'")   # ' ' → '
        s = re.sub(r'\s+', ' ', s)
        return s
    return norm(a) == norm(b)

openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = FastAPI()


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
    audio_bytes = response.content
    return Response(content=audio_bytes, media_type="audio/mpeg")


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

        while True:
            messages: list = result.get("messages", [])
            interrupts = result.get("__interrupt__", [])
            fase = result.get("fase", "")

            # Filter new messages to send to the client.
            #
            # When fase_completa=False the node commits:
            #   [AIMessage(re-generated-question), HumanMessage(user-answer)]
            # The AIMessage is a re-generation of the question already sent as the
            # interrupt value — skip it. The user response is not an AIMessage, skip too.
            #
            # When fase_completa=True the node commits:
            #   [AIMessage(completion-feedback), HumanMessage("[acknowledged...]")]
            # The AIMessage is NEW and must be shown.
            #
            # Reliable heuristic: the first new AIMessage should be skipped if and
            # only if it is followed by a real user HumanMessage (not our placeholder).
            # Completion feedback is always followed by "[acknowledged — ready for next phase]".
            new_messages = messages[prev_msg_count:]
            first_ai_idx = next(
                (i for i, m in enumerate(new_messages) if isinstance(m, AIMessage)), None
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
                        continue  # re-generated interrupt question — already shown
                is_scorecard = "INTERVIEW SCORECARD" in msg.content or fase == "done"
                msg_type = "feedback" if is_scorecard else "transition"
                await ws.send_json({"type": msg_type, "text": msg.content})

            if not interrupts:
                await ws.send_json({"type": "done"})
                break

            question = interrupts[0].value
            await ws.send_json({"type": "ai", "text": question})

            # Wait for user's spoken/typed response
            data = await ws.receive_json()
            user_text = data.get("text", "").strip()
            if not user_text:
                continue

            await ws.send_json({"type": "user", "text": user_text})

            prev_msg_count = len(messages)
            try:
                result = await loop.run_in_executor(
                    None, functools.partial(graph.invoke, Command(resume=user_text), config)
                )
            except Exception as exc:
                import traceback
                traceback.print_exc()
                await ws.send_json({
                    "type": "error",
                    "text": f"[Server error — please reload and try again]\n{exc}"
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
                "text": f"[Connection error — please reload]\n{exc}"
            })
        except Exception:
            pass


# Serve the frontend — mount last so /ws is registered first
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
