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

        while True:
            messages: list = result.get("messages", [])
            interrupts = result.get("__interrupt__", [])
            fase = result.get("fase", "")

            # Send transition messages and final feedback.
            # The first new AIMessage is always the previously-shown question
            # (committed on resume) — skip it. Everything after is new.
            new_messages = messages[prev_msg_count:]
            skip_first_ai = True
            for msg in new_messages:
                if skip_first_ai and isinstance(msg, AIMessage):
                    skip_first_ai = False
                    continue
                if isinstance(msg, AIMessage):
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
            result = await loop.run_in_executor(
                None, functools.partial(graph.invoke, Command(resume=user_text), config)
            )

    except WebSocketDisconnect:
        pass


# Serve the frontend — mount last so /ws is registered first
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
