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
        last_shown_question = ""  # tracks the interrupt text already sent to the client

        while True:
            messages: list = result.get("messages", [])
            interrupts = result.get("__interrupt__", [])
            fase = result.get("fase", "")

            # Send transition messages and final feedback.
            # When fase_completa=False the node commits AIMessage(question)+HumanMessage(answer),
            # so the first new AIMessage is the question already shown — skip it.
            # When fase_completa=True the node only commits AIMessage(final_feedback), which is
            # NEW and must NOT be skipped. We distinguish by comparing to last_shown_question.
            new_messages = messages[prev_msg_count:]
            first_ai_skipped = False
            for msg in new_messages:
                if not first_ai_skipped and isinstance(msg, AIMessage):
                    first_ai_skipped = True
                    if msg.content == last_shown_question:
                        continue   # already sent this one as the interrupt question
                if isinstance(msg, AIMessage):
                    is_scorecard = "INTERVIEW SCORECARD" in msg.content or fase == "done"
                    msg_type = "feedback" if is_scorecard else "transition"
                    await ws.send_json({"type": msg_type, "text": msg.content})

            if not interrupts:
                await ws.send_json({"type": "done"})
                break

            question = interrupts[0].value
            last_shown_question = question
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
