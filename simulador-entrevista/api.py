import asyncio
import functools
import hashlib
import os
import uuid
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

import stripe as _stripe

from fastapi import FastAPI, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect, Depends
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.types import Command
from openai import AsyncOpenAI
from pydantic import BaseModel

from simulator import (
    graph, make_initial_state, model, session_store,
    _build_report_system, REPORT_PHASE_MAP, _conn,
)
from auth import (
    UserCreate, UserLogin, TokenResponse, ProfileUpdate,
    create_user, authenticate_user, get_user_by_id, update_profile,
    create_verification_token, verify_email_token,
    create_reset_token, reset_password_with_token,
    upgrade_plan, count_interviews_this_week, PLAN_WEEKLY_LIMITS,
    create_job_session, update_job_session_context, get_job_session, list_job_sessions,
    create_access_token, get_current_user, decode_token_raw,
    create_contact_message, list_contact_messages, save_contact_reply, get_contact_message, delete_contact_message,
    set_stripe_info, clear_stripe_subscription, get_user_by_stripe_customer, get_stripe_info,
)
from email_service import send_verification_email, send_reset_email, send_contact_notification, send_contact_reply
from prompt_generator import generate_interview_context, extract_candidate_name

openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

_stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
_STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
_STRIPE_PRICE_ID_USD   = os.getenv("STRIPE_PRICE_ID_USD", os.getenv("STRIPE_PRICE_ID", ""))
_STRIPE_PRICE_ID_BRL   = os.getenv("STRIPE_PRICE_ID_BRL", "")
_APP_BASE_URL          = os.getenv("APP_BASE_URL", "http://localhost:8001").rstrip("/")


def _stripe_price_for(language: str) -> str:
    if language == "pt" and _STRIPE_PRICE_ID_BRL:
        return _STRIPE_PRICE_ID_BRL
    return _STRIPE_PRICE_ID_USD

TTS_CACHE_DIR = Path(__file__).parent / "static" / "tts_cache"
TTS_CACHE_DIR.mkdir(exist_ok=True)
_TTS_CACHE_HEADERS = {"Cache-Control": "public, max-age=31536000, immutable"}

app = FastAPI()


# ── Auth endpoints ────────────────────────────────────────────────────────────

@app.post("/auth/register", response_model=TokenResponse)
async def register(body: UserCreate):
    if not body.name.strip():
        raise HTTPException(status_code=422, detail="Name is required")
    if not body.email.strip() or "@" not in body.email:
        raise HTTPException(status_code=422, detail="Valid email is required")
    if len(body.password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters")
    loop = asyncio.get_running_loop()
    user = await loop.run_in_executor(
        None,
        lambda: create_user(_conn, body.name.strip(), body.email.strip(),
                            body.password, body.language),
    )
    # Send verification email
    token = await loop.run_in_executor(
        None, lambda: create_verification_token(_conn, user["id"])
    )
    try:
        await loop.run_in_executor(None, lambda: send_verification_email(user["email"], token, user.get("language", "en")))
    except Exception as exc:
        print(f"[register] Failed to send verification email: {exc}")
    access_token = create_access_token(user["id"], user["email"])
    return TokenResponse(access_token=access_token, user=user)


@app.post("/auth/login", response_model=TokenResponse)
async def login(body: UserLogin):
    loop = asyncio.get_running_loop()
    user = await loop.run_in_executor(
        None,
        lambda: authenticate_user(_conn, body.email, body.password),
    )
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token(user["id"], user["email"])
    return TokenResponse(access_token=token, user=user)


@app.get("/auth/me")
async def me(current_user: dict = Depends(get_current_user)):
    loop = asyncio.get_running_loop()
    user = await loop.run_in_executor(
        None, lambda: get_user_by_id(_conn, current_user["id"])
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.put("/auth/profile")
async def update_user_profile(body: ProfileUpdate, current_user: dict = Depends(get_current_user)):
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        lambda: update_profile(
            _conn, current_user["id"],
            body.name, body.email, body.current_password, body.new_password,
            body.language,
        ),
    )
    # If email changed, send new verification email
    if result.get("email_changed"):
        token = await loop.run_in_executor(
            None, lambda: create_verification_token(_conn, current_user["id"])
        )
        try:
            await loop.run_in_executor(
                None, lambda: send_verification_email(result["email"], token, result.get("language", "en"))
            )
        except Exception as exc:
            print(f"[profile] Failed to send verification email: {exc}")
    return result


@app.post("/auth/send-verification")
async def send_verification(current_user: dict = Depends(get_current_user)):
    loop = asyncio.get_running_loop()
    user = await loop.run_in_executor(None, lambda: get_user_by_id(_conn, current_user["id"]))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.get("email_verified"):
        return {"ok": True, "already_verified": True}
    token = await loop.run_in_executor(
        None, lambda: create_verification_token(_conn, current_user["id"])
    )
    mock = os.getenv("MOCK_EMAIL", "false").lower() == "true"
    try:
        await loop.run_in_executor(None, lambda: send_verification_email(user["email"], token, user.get("language", "en")))
    except Exception as exc:
        print(f"[send-verification] Failed: {exc}")
        raise HTTPException(status_code=503, detail="Failed to send email — please try again")
    response = {"ok": True}
    if mock:
        response["dev_token"] = token  # expose token in dev mode for manual testing
    return response


@app.get("/auth/verify-email")
async def verify_email(token: str):
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, lambda: verify_email_token(_conn, token))
    if not result:
        raise HTTPException(status_code=400, detail="Invalid or expired verification link")
    return {"ok": True, "email": result["email"]}


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


@app.post("/auth/forgot-password")
async def forgot_password(body: ForgotPasswordRequest):
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None, lambda: create_reset_token(_conn, body.email)
    )
    mock = os.getenv("MOCK_EMAIL", "false").lower() == "true"
    response = {"ok": True}  # always return ok to avoid email enumeration
    if result:
        _, token, lang = result
        try:
            await loop.run_in_executor(None, lambda: send_reset_email(body.email, token, lang))
        except Exception as exc:
            print(f"[forgot-password] Failed to send email: {exc}")
        if mock:
            response["dev_token"] = token
    return response


@app.post("/auth/reset-password")
async def reset_password(body: ResetPasswordRequest):
    loop = asyncio.get_running_loop()
    ok = await loop.run_in_executor(
        None, lambda: reset_password_with_token(_conn, body.token, body.new_password)
    )
    if not ok:
        raise HTTPException(status_code=400, detail="Invalid or expired reset link")
    return {"ok": True}


@app.post("/auth/upgrade")
async def upgrade_to_hunter(current_user: dict = Depends(get_current_user)):
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, lambda: upgrade_plan(_conn, current_user["id"], "hunter"))
    user = await loop.run_in_executor(None, lambda: get_user_by_id(_conn, current_user["id"]))
    return {"ok": True, "plan": "hunter", "user": user}


@app.get("/auth/usage")
async def get_usage(current_user: dict = Depends(get_current_user)):
    loop = asyncio.get_running_loop()
    user = await loop.run_in_executor(None, lambda: get_user_by_id(_conn, current_user["id"]))
    plan  = user.get("plan", "free") if user else "free"
    used  = await loop.run_in_executor(
        None, lambda: count_interviews_this_week(_conn, current_user["id"])
    )
    limit = PLAN_WEEKLY_LIMITS.get(plan, 3)
    stripe_info = await loop.run_in_executor(None, lambda: get_stripe_info(_conn, current_user["id"]))
    return {
        "plan": plan, "used": used, "limit": limit, "remaining": max(0, limit - used),
        "has_stripe_subscription": bool(stripe_info.get("stripe_subscription_id")),
    }


@app.post("/auth/downgrade")
async def downgrade_to_free(current_user: dict = Depends(get_current_user)):
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, lambda: upgrade_plan(_conn, current_user["id"], "free"))
    user = await loop.run_in_executor(None, lambda: get_user_by_id(_conn, current_user["id"]))
    return {"ok": True, "plan": "free", "user": user}


# ── Stripe endpoints ──────────────────────────────────────────────────────────

@app.post("/stripe/create-checkout-session")
async def stripe_create_checkout(current_user: dict = Depends(get_current_user)):
    price_id = _stripe_price_for(current_user.get("language", "en"))
    if not price_id:
        raise HTTPException(status_code=503, detail="Stripe not configured")
    if current_user.get("plan") == "hunter":
        raise HTTPException(status_code=400, detail="Already on Hunter plan")
    try:
        session = _stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=f"{_APP_BASE_URL}/upgrade-success.html?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{_APP_BASE_URL}/upgrade.html",
            client_reference_id=current_user["id"],
            customer_email=current_user.get("email"),
            metadata={"user_id": current_user["id"]},
        )
        return {"url": session.url}
    except _stripe.error.StripeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    payload    = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    try:
        event = _stripe.Webhook.construct_event(payload, sig_header, _STRIPE_WEBHOOK_SECRET)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except _stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    etype = event["type"]
    data  = event["data"]["object"]

    if etype == "checkout.session.completed":
        user_id = data.get("client_reference_id") or (data.get("metadata") or {}).get("user_id")
        customer_id      = data.get("customer")
        subscription_id  = data.get("subscription")
        if user_id and customer_id and subscription_id:
            upgrade_plan(_conn, user_id, "hunter")
            set_stripe_info(_conn, user_id, customer_id, subscription_id)
            print(f"[Stripe] Upgraded user {user_id} → hunter (sub {subscription_id})")

    elif etype in ("customer.subscription.deleted",):
        customer_id = data.get("customer")
        user = get_user_by_stripe_customer(_conn, customer_id)
        if user:
            upgrade_plan(_conn, user["id"], "free")
            clear_stripe_subscription(_conn, user["id"])
            print(f"[Stripe] Downgraded user {user['id']} → free (sub canceled)")

    elif etype == "invoice.payment_failed":
        customer_id = data.get("customer")
        print(f"[Stripe] Payment failed for customer {customer_id}")

    return {"ok": True}


@app.post("/stripe/portal")
async def stripe_portal(current_user: dict = Depends(get_current_user)):
    if not _STRIPE_PRICE_ID:
        raise HTTPException(status_code=503, detail="Stripe not configured")
    loop = asyncio.get_running_loop()
    info = await loop.run_in_executor(None, lambda: get_stripe_info(_conn, current_user["id"]))
    customer_id = info.get("stripe_customer_id")
    if not customer_id:
        raise HTTPException(status_code=400, detail="No Stripe subscription found")
    try:
        portal = _stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=f"{_APP_BASE_URL}/upgrade.html",
        )
        return {"url": portal.url}
    except _stripe.error.StripeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


# ── Job session / prepare endpoints ──────────────────────────────────────────

class PrepareRequest(BaseModel):
    job_title:       str
    company:         str = ""
    job_description: str
    resume_text:     str


@app.post("/prepare")
async def prepare(body: PrepareRequest, current_user: dict = Depends(get_current_user)):
    """Generate a personalized interview context and create a job session."""
    if len(body.job_description.strip()) < 50:
        raise HTTPException(status_code=422, detail="Job description is too short")
    if len(body.resume_text.strip()) < 50:
        raise HTTPException(status_code=422, detail="Resume text is too short")

    loop = asyncio.get_running_loop()

    # Fetch user info (language + plan)
    user = await loop.run_in_executor(
        None, lambda: get_user_by_id(_conn, current_user["id"])
    )
    language = user.get("language", "en") if user else "en"
    plan     = user.get("plan", "free")   if user else "free"

    # Enforce weekly interview limit
    week_count = await loop.run_in_executor(
        None, lambda: count_interviews_this_week(_conn, current_user["id"])
    )
    limit = PLAN_WEEKLY_LIMITS.get(plan, 3)
    if week_count >= limit:
        raise HTTPException(
            status_code=429,
            detail={
                "code": "weekly_limit_reached",
                "plan": plan,
                "limit": limit,
                "used": week_count,
                "message": f"You've used all {limit} interviews this week on your {plan.capitalize()} plan.",
            },
        )

    # Generate personalized interview context (LLM call — may take 10–20 seconds)
    try:
        interview_context = await generate_interview_context(
            job_title=body.job_title,
            company=body.company,
            job_description=body.job_description,
            resume_text=body.resume_text,
            language=language,
        )
    except Exception as exc:
        print(f"[prepare] LLM generation failed: {exc}")
        raise HTTPException(
            status_code=503,
            detail="Failed to generate interview context — please try again in a moment.",
        )

    candidate_name = extract_candidate_name(interview_context)

    # Persist in DB
    job_session_id = await loop.run_in_executor(
        None,
        lambda: create_job_session(
            _conn,
            user_id=current_user["id"],
            job_title=body.job_title,
            company=body.company,
            job_description=body.job_description,
            resume_text=body.resume_text,
            interview_context=interview_context,
        ),
    )

    return {
        "job_session_id": job_session_id,
        "candidate_name": candidate_name,
        "job_title": body.job_title,
        "company": body.company,
        "context_preview": interview_context[:500] + "…" if len(interview_context) > 500 else interview_context,
    }


@app.get("/job-sessions")
async def list_user_job_sessions(current_user: dict = Depends(get_current_user)):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, lambda: list_job_sessions(_conn, current_user["id"])
    )


# ── Session history endpoints ─────────────────────────────────────────────────

class SessionUpsert(BaseModel):
    startedAt:    int
    lastActiveAt: int
    fase:         str
    history:      list
    jobSessionId: str = ""


@app.get("/sessions")
async def list_sessions(current_user: dict = Depends(get_current_user)):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, lambda: session_store.list_sessions(user_id=current_user["id"])
    )


@app.put("/sessions/{thread_id}")
async def upsert_session(thread_id: str, body: SessionUpsert,
                         current_user: dict = Depends(get_current_user)):
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None,
        lambda: session_store.upsert(
            thread_id,
            body.startedAt,
            body.lastActiveAt,
            body.fase,
            body.history,
            user_id=current_user["id"],
            job_session_id=body.jobSessionId or None,
        ),
    )
    return {"ok": True}


@app.delete("/sessions/{thread_id}")
async def delete_session(thread_id: str, current_user: dict = Depends(get_current_user)):
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None, lambda: session_store.delete(thread_id, user_id=current_user["id"])
    )
    return {"ok": True}


ADMIN_EMAIL = "marciosferreira@yahoo.com.br"


@app.get("/admin/users")
async def admin_list_users(current_user: dict = Depends(get_current_user)):
    if current_user.get("email") != ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="Admin only")
    loop = asyncio.get_running_loop()
    week_ago_ms = int((__import__("time").time() - 7 * 24 * 3600) * 1000)

    def _query():
        rows = _conn.execute("""
            SELECT
                u.id, u.name, u.email, u.plan, u.email_verified, u.created_at,
                COUNT(sm.thread_id)                                          AS total_sessions,
                SUM(CASE WHEN sm.fase = 'done' THEN 1 ELSE 0 END)           AS completed,
                SUM(CASE WHEN sm.started_at >= ? THEN 1 ELSE 0 END)         AS sessions_week,
                MAX(sm.last_active_at)                                       AS last_active
            FROM users u
            LEFT JOIN session_meta sm ON u.id = sm.user_id
            GROUP BY u.id
            ORDER BY u.created_at DESC
        """, (week_ago_ms,)).fetchall()
        return [
            {
                "id": r[0], "name": r[1], "email": r[2],
                "plan": r[3] or "free", "email_verified": bool(r[4]),
                "created_at": r[5],
                "total_sessions": r[6] or 0, "completed": r[7] or 0,
                "sessions_week": r[8] or 0, "last_active": r[9],
            }
            for r in rows
        ]

    users = await loop.run_in_executor(None, _query)
    return {"users": users}


@app.post("/admin/users/{user_id}/plan")
async def admin_set_plan(user_id: str, body: dict, current_user: dict = Depends(get_current_user)):
    if current_user.get("email") != ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="Admin only")
    plan = body.get("plan")
    if plan not in ("free", "hunter"):
        raise HTTPException(status_code=422, detail="Invalid plan")
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, lambda: upgrade_plan(_conn, user_id, plan))
    return {"ok": True}


@app.delete("/admin/users/{user_id}")
async def admin_delete_user(user_id: str, current_user: dict = Depends(get_current_user)):
    if current_user.get("email") != ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="Admin only")

    def _delete():
        # Guard: never delete the admin account
        row = _conn.execute("SELECT email FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        if row[0] == ADMIN_EMAIL:
            raise HTTPException(status_code=403, detail="Cannot delete the admin account")
        # Delete all interview data, then the user
        thread_ids = [r[0] for r in _conn.execute(
            "SELECT thread_id FROM session_meta WHERE user_id = ?", (user_id,)
        ).fetchall()]
        if thread_ids:
            placeholders = ",".join("?" * len(thread_ids))
            _conn.execute(f"DELETE FROM session_meta WHERE thread_id IN ({placeholders})", thread_ids)
        _conn.execute("DELETE FROM job_sessions WHERE user_id = ?", (user_id,))
        _conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        _conn.commit()

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _delete)
    return {"ok": True}


@app.get("/sessions/{thread_id}/scorecard")
async def get_scorecard(thread_id: str, current_user: dict = Depends(get_current_user)):
    loop = asyncio.get_running_loop()
    user = await loop.run_in_executor(None, lambda: get_user_by_id(_conn, current_user["id"]))
    if not user or user.get("plan", "free") != "hunter":
        raise HTTPException(status_code=403, detail="Scorecard access requires the Hunter plan")
    scorecard = await loop.run_in_executor(
        None,
        lambda: session_store.get_scorecard(thread_id, current_user["id"]),
    )
    if not scorecard:
        raise HTTPException(status_code=404, detail="Scorecard not found for this session")
    return {"scorecard": scorecard}


# ── Audio endpoints ───────────────────────────────────────────────────────────

@app.post("/parse-document")
async def parse_document(file: UploadFile):
    data = await file.read()
    name = (file.filename or "").lower()
    text = ""
    try:
        if name.endswith(".pdf"):
            import pdfplumber, io
            with pdfplumber.open(io.BytesIO(data)) as pdf:
                text = "\n".join(p.extract_text() or "" for p in pdf.pages)
        elif name.endswith(".docx"):
            import docx, io
            doc = docx.Document(io.BytesIO(data))
            text = "\n".join(p.text for p in doc.paragraphs)
        else:
            raise HTTPException(status_code=415, detail="Only PDF and DOCX files are supported.")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not parse file: {exc}")
    text = text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="No text found in the file.")
    return {"text": text}


@app.post("/stt")
async def stt(audio: UploadFile, lang: str = "en"):
    audio_bytes = await audio.read()
    whisper_lang = "pt" if lang == "pt" else "en"
    transcript = await openai_client.audio.transcriptions.create(
        model="whisper-1",
        file=(audio.filename or "audio.webm", audio_bytes, audio.content_type or "audio/webm"),
        language=whisper_lang,
    )
    return {"text": transcript.text}


_TTS_LANG_INSTRUCTIONS = {
    "pt": "Fale em Português do Brasil com sotaque brasileiro natural e claro.",
    "en": "",
}

@app.get("/tts")
async def tts(text: str, voice: str = "nova", lang: str = "en", nocache: bool = False):
    allowed = {"alloy", "echo", "fable", "onyx", "nova", "shimmer"}
    if voice not in allowed:
        voice = "nova"

    instructions = _TTS_LANG_INSTRUCTIONS.get(lang, "")
    use_mini = bool(instructions)  # gpt-4o-mini-tts only needed when we have instructions
    tts_model = "gpt-4o-mini-tts" if use_mini else "tts-1"
    cache_key_str = f"{tts_model}:{voice}:{lang}:{text}"

    if not nocache:
        cache_key  = hashlib.md5(cache_key_str.encode()).hexdigest()
        cache_file = TTS_CACHE_DIR / f"{cache_key}.mp3"
        if cache_file.exists():
            return Response(content=cache_file.read_bytes(), media_type="audio/mpeg",
                            headers=_TTS_CACHE_HEADERS)
    else:
        cache_file = None

    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            kwargs = dict(model=tts_model, voice=voice, input=text)
            if instructions:
                kwargs["instructions"] = instructions
            response = await openai_client.audio.speech.create(**kwargs)
            audio_bytes = response.content
            if cache_file is not None:
                cache_file.write_bytes(audio_bytes)
            headers = _TTS_CACHE_HEADERS if cache_file is not None else {}
            return Response(content=audio_bytes, media_type="audio/mpeg", headers=headers)
        except Exception as exc:
            last_exc = exc
            if attempt < 2:
                await asyncio.sleep(0.5 * (attempt + 1))

    print(f"[tts] failed after 3 attempts: {last_exc}")
    raise HTTPException(status_code=503, detail="TTS service temporarily unavailable")


# ── WebSocket streaming helper ────────────────────────────────────────────────

async def _stream_to_client(ws: WebSocket, messages: list, system_prompt: str,
                             voice: str = "nova", lang: str = "en", max_retries: int = 5) -> str:
    from anthropic import APIStatusError
    full_msg = [SystemMessage(content=[{
        "type": "text",
        "text": system_prompt,
        "cache_control": {"type": "ephemeral"},
    }])] + messages
    for attempt in range(max_retries):
        full_text = ""
        try:
            async for chunk in model.astream(full_msg):
                if chunk.content:
                    full_text += chunk.content
                    await ws.send_json({"type": "stream_chunk", "text": chunk.content, "voice": voice, "lang": lang})
            await ws.send_json({"type": "stream_done"})
            return full_text
        except APIStatusError as exc:
            if exc.status_code == 529 and attempt < max_retries - 1:
                wait = 5.0 * (2 ** attempt)
                print(f"[stream retry] Anthropic overloaded (529) — waiting {wait:.0f}s (attempt {attempt + 1}/{max_retries})")
                await asyncio.sleep(wait)
            else:
                print(f"[stream error] {exc}")
                await ws.send_json({"type": "stream_done"})
                return full_text
        except Exception as exc:
            print(f"[stream error] {exc}")
            await ws.send_json({"type": "stream_done"})
            return full_text
    return ""


# ── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def interview_ws(ws: WebSocket):
    await ws.accept()
    loop = asyncio.get_running_loop()

    # ── Initial handshake ──────────────────────────────────────────────────
    # Client sends: {"type": "init"|"resume", "token": "...", "job_session_id": "...",
    #                "thread_id": "..." (optional, for resume)}
    thread_id: str = str(uuid.uuid4())
    is_resuming = False
    job_session_id: str = ""
    interview_context: str = ""
    candidate_name: str = "the candidate"
    job_title: str = ""
    company: str = ""

    try:
        init = await asyncio.wait_for(ws.receive_json(), timeout=5.0)
    except Exception:
        await ws.send_json({"type": "error", "text": "No init message received"})
        return

    # Authenticate via token in the init message
    token = init.get("token", "")
    user_info = decode_token_raw(token) if token else None
    if not user_info:
        await ws.send_json({"type": "error", "text": "Unauthorized — please log in again"})
        return

    user_id = user_info["id"]
    job_session_id = init.get("job_session_id", "")

    # Load user status — email_verified gates phase 2+; plan gates scorecard
    user_db = await loop.run_in_executor(None, lambda: get_user_by_id(_conn, user_id))
    email_verified: bool = bool(user_db.get("email_verified")) if user_db else False
    user_plan: str     = user_db.get("plan", "free")     if user_db else "free"
    user_language: str = user_db.get("language", "en")   if user_db else "en"

    # Load interview context from the job session
    if job_session_id:
        js = await loop.run_in_executor(
            None, lambda: get_job_session(_conn, job_session_id, user_id)
        )
        if js:
            interview_context = js.get("interview_context", "")
            job_title = js.get("job_title", "")
            company   = js.get("company", "")
            candidate_name = extract_candidate_name(interview_context)
        else:
            print(f"[ws] job_session_id={job_session_id!r} not found for user={user_id!r}")
            await ws.send_json({"type": "error", "text": "Interview session not found — please start a new interview from the onboarding page."})
            return
    else:
        print(f"[ws] no job_session_id for user={user_id!r} — starting without context")
        await ws.send_json({"type": "error", "text": "No interview prepared — please go to the home page and start a new interview."})
        return

    # Check for resume
    if init.get("type") == "resume" and init.get("thread_id"):
        thread_id = init["thread_id"]
        is_resuming = True

    config = {"configurable": {"thread_id": thread_id}}
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
                await ws.send_json({"type": "resumed"})
                await ws.send_json({"type": "phase", "fase": result.get("fase", "")})
            else:
                is_resuming = False

        if not is_resuming:
            initial_state = make_initial_state(
                interview_context=interview_context,
                candidate_name=candidate_name,
                job_title=job_title,
                company=company,
                language=user_language,
            )
            result = await loop.run_in_executor(
                None, functools.partial(graph.invoke, initial_state, config)
            )
            prev_msg_count       = 1
            prev_report_streamed = False
            skip_advance         = False

        while True:
            messages: list = result.get("messages", [])
            interrupts = result.get("__interrupt__", [])
            fase = result.get("fase", "")

            await ws.send_json({"type": "phase", "fase": fase})

            was_report_streamed  = prev_report_streamed
            prev_report_streamed = False

            new_messages = messages[prev_msg_count:]

            # ── Scorecard gate (Hunter plan only) ─────────────────────────
            if fase == "done":
                user_db = await loop.run_in_executor(
                    None, lambda: get_user_by_id(_conn, user_id)
                )
                user_plan = user_db.get("plan", "free") if user_db else "free"

                # Always save the scorecard to DB regardless of plan
                scorecard_msg = next(
                    (m.content for m in new_messages
                     if isinstance(m, AIMessage) and "INTERVIEW SCORECARD" in m.content),
                    None,
                )
                if scorecard_msg:
                    await loop.run_in_executor(
                        None,
                        lambda: session_store.save_scorecard(thread_id, user_id, scorecard_msg),
                    )

                if user_plan != "hunter":
                    await ws.send_json({"type": "scorecard_ready"})
                    await ws.send_json({"type": "done"})
                    break

            first_ai_idx = next(
                (i for i, m in enumerate(new_messages) if isinstance(m, AIMessage)), None
            )
            had_transition = any(
                isinstance(m, HumanMessage) and "[acknowledged" in m.content
                for m in new_messages
            )

            for i, msg in enumerate(new_messages):
                if not isinstance(msg, AIMessage):
                    continue
                if msg.content in ("[no_report]", ""):
                    continue
                if i == first_ai_idx:
                    next_msg = new_messages[i + 1] if i + 1 < len(new_messages) else None
                    is_replay = (
                        next_msg is not None
                        and isinstance(next_msg, HumanMessage)
                        and "[acknowledged" not in next_msg.content
                    )
                    if is_replay:
                        continue
                    if was_report_streamed and had_transition:
                        continue
                if "INTERVIEW SCORECARD" in msg.content:
                    continue  # scorecard served separately via /sessions/{thread_id}/scorecard
                is_scorecard = fase == "done"
                msg_type = "feedback" if is_scorecard else "transition"
                await ws.send_json({"type": msg_type, "text": msg.content})

            if not interrupts:
                if fase == "done" and user_plan == "hunter":
                    await ws.send_json({"type": "scorecard_ready"})
                await ws.send_json({"type": "done"})
                break

            question = interrupts[0].value

            # ── Report streaming ──────────────────────────────────────────
            if question == "[report_ready]":
                phase_key = REPORT_PHASE_MAP.get(fase, "")
                phase_messages = result.get("phase_messages") or []

                # Detect if the candidate skipped this phase
                was_skipped = any(
                    isinstance(m, HumanMessage) and "[Candidate skipped" in m.content
                    for m in phase_messages
                )

                _NEXT_PHASE_LABEL = {
                    "elevator_pitch_report": "the CAR Project Story",
                    "CAR_report":            "the Technical Questions",
                    "technical_report":      "Leadership & Project Approach",
                    "leadership_report":     "Fit & Motivation",
                    "motivation_report":     "your questions for me",
                }
                next_label = _NEXT_PHASE_LABEL.get(fase, "the next phase")

                if was_skipped:
                    full_text    = "[no_report]"
                    skip_advance = True
                    await ws.send_json({"type": "ai", "text": "⏭ Phase skipped — moving on."})
                elif phase_key:
                    # Build dynamic report system prompt with per-session context
                    ctx = result.get("interview_context") or interview_context
                    lang = result.get("language") or user_language
                    report_system = _build_report_system(ctx, phase_key, lang)
                    full_text = await _stream_to_client(
                        ws, phase_messages, report_system, voice="onyx", lang=lang
                    )
                    await ws.send_json({
                        "type": "ai",
                        "text": f"Take a moment to review that feedback. When you're ready to move on to {next_label}, just send me a message.",
                    })
                else:
                    full_text = ""
                prev_msg_count       = len(messages)
                prev_report_streamed = bool(full_text) and not was_skipped
                result = await loop.run_in_executor(
                    None,
                    functools.partial(
                        graph.invoke, Command(resume=full_text or "[no_report]"), config
                    ),
                )
                continue

            if had_transition and not skip_advance:
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
                skip_advance = False
                await ws.send_json({"type": "ai", "text": question})

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
                break

            await ws.send_json({"type": "user", "text": user_text})
            prev_msg_count = len(messages)

            # Block advancing past Elevator Pitch if email not verified
            if fase == "elevator_pitch_report" and not email_verified:
                # Re-fetch in case user verified during the session
                user_db = await loop.run_in_executor(None, lambda: get_user_by_id(_conn, user_id))
                email_verified = bool(user_db.get("email_verified")) if user_db else False
                if not email_verified:
                    await ws.send_json({
                        "type": "ai",
                        "text": (
                            "⚠️ **Email verification required.**\n\n"
                            "To continue to the next phase, please verify your email address first. "
                            "Check your inbox for the verification link, or go to **Settings → Resend verification email**.\n\n"
                            "Once verified, send any message here to continue."
                        ),
                    })
                    continue  # wait for the next message, re-check at top of loop

            try:
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


# ── Contact endpoints ─────────────────────────────────────────────────────────

class ContactRequest(BaseModel):
    name:    str
    email:   str
    subject: str
    body:    str


@app.post("/contact")
async def submit_contact(body: ContactRequest):
    if not body.name.strip():
        raise HTTPException(status_code=422, detail="Name is required")
    if not body.email.strip() or "@" not in body.email:
        raise HTTPException(status_code=422, detail="Valid email is required")
    if not body.subject.strip():
        raise HTTPException(status_code=422, detail="Subject is required")
    if len(body.body.strip()) < 10:
        raise HTTPException(status_code=422, detail="Message is too short")

    loop = asyncio.get_running_loop()
    msg_id = await loop.run_in_executor(
        None,
        lambda: create_contact_message(_conn, body.name, body.email, body.subject, body.body),
    )
    try:
        await loop.run_in_executor(
            None,
            lambda: send_contact_notification(body.name, body.email, body.subject, body.body),
        )
    except Exception as exc:
        print(f"[contact] Failed to send notification: {exc}")
    return {"ok": True, "id": msg_id}


@app.get("/admin/contact")
async def admin_list_contact(current_user: dict = Depends(get_current_user)):
    if current_user.get("email") != ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="Admin only")
    loop = asyncio.get_running_loop()
    messages = await loop.run_in_executor(None, lambda: list_contact_messages(_conn))
    return {"messages": messages}


class ContactReplyRequest(BaseModel):
    reply_text: str


@app.post("/admin/contact/{msg_id}/reply")
async def admin_reply_contact(msg_id: str, body: ContactReplyRequest,
                              current_user: dict = Depends(get_current_user)):
    if current_user.get("email") != ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="Admin only")
    if not body.reply_text.strip():
        raise HTTPException(status_code=422, detail="Reply text is required")

    loop = asyncio.get_running_loop()
    msg = await loop.run_in_executor(None, lambda: get_contact_message(_conn, msg_id))
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")

    await loop.run_in_executor(
        None, lambda: save_contact_reply(_conn, msg_id, body.reply_text)
    )
    try:
        await loop.run_in_executor(
            None,
            lambda: send_contact_reply(msg["email"], msg["name"], msg["subject"], body.reply_text),
        )
    except Exception as exc:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=503, detail=f"Reply saved but email failed: {exc}")
    return {"ok": True}


@app.delete("/admin/contact/{msg_id}")
async def admin_delete_contact(msg_id: str, current_user: dict = Depends(get_current_user)):
    if current_user.get("email") != ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="Admin only")
    loop = asyncio.get_running_loop()
    deleted = await loop.run_in_executor(None, lambda: delete_contact_message(_conn, msg_id))
    if not deleted:
        raise HTTPException(status_code=404, detail="Message not found")
    return {"ok": True}


# Serve the frontend — mount last so API routes are registered first
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
