import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import bcrypt as _bcrypt
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from pydantic import BaseModel

SECRET_KEY = os.getenv("JWT_SECRET", "change-this-secret-in-production-please")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24 * 7  # 7 days

VERIFICATION_TOKEN_EXPIRES_HOURS = 24
RESET_TOKEN_EXPIRES_MINUTES = 15

security = HTTPBearer(auto_error=False)


def _hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode("utf-8"), _bcrypt.gensalt()).decode("utf-8")


def _verify_password(password: str, hashed: str) -> bool:
    try:
        return _bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def _now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


# ── Pydantic schemas ─────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    name: str
    email: str
    password: str
    language: str = "en"


class UserLogin(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = None
    language: Optional[str] = None


# ── DB setup (with migrations for existing DBs) ──────────────────────────────

def setup_user_tables(conn: Any) -> None:
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id                   TEXT PRIMARY KEY,
            email                TEXT UNIQUE NOT NULL,
            name                 TEXT NOT NULL,
            password_hash        TEXT NOT NULL,
            language             TEXT NOT NULL DEFAULT 'en',
            created_at           BIGINT NOT NULL,
            email_verified       INTEGER NOT NULL DEFAULT 0,
            verification_token   TEXT,
            verification_expires BIGINT,
            reset_token          TEXT,
            reset_token_expires  BIGINT,
            plan                 TEXT NOT NULL DEFAULT 'free'
        )
    """)
    # Migrate existing DBs — Postgres suporta ADD COLUMN IF NOT EXISTS
    for col, defn in [
        ("email_verified",       "INTEGER NOT NULL DEFAULT 0"),
        ("verification_token",   "TEXT"),
        ("verification_expires", "BIGINT"),
        ("reset_token",          "TEXT"),
        ("reset_token_expires",  "BIGINT"),
        ("plan",                 "TEXT NOT NULL DEFAULT 'free'"),
        ("stripe_customer_id",     "TEXT"),
        ("stripe_subscription_id", "TEXT"),
        ("stripe_cancel_at",       "BIGINT"),
    ]:
        cur.execute(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col} {defn}")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS job_sessions (
            id                TEXT PRIMARY KEY,
            user_id           TEXT NOT NULL,
            job_title         TEXT NOT NULL,
            company           TEXT NOT NULL DEFAULT '',
            job_description   TEXT NOT NULL,
            resume_text       TEXT NOT NULL,
            interview_context TEXT NOT NULL DEFAULT '',
            created_at        BIGINT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS contact_messages (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            email       TEXT NOT NULL,
            subject     TEXT NOT NULL,
            body        TEXT NOT NULL,
            created_at  BIGINT NOT NULL,
            replied_at  BIGINT,
            reply_text  TEXT
        )
    """)
    cur.close()
    conn.commit()


# ── User CRUD ────────────────────────────────────────────────────────────────

def create_user(conn: Any, name: str, email: str,
                password: str, language: str = "en") -> dict:
    import psycopg2
    user_id = str(uuid.uuid4())
    password_hash = _hash_password(password)
    now = _now_ms()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO users (id, name, email, password_hash, language, created_at, email_verified)
               VALUES (%s, %s, %s, %s, %s, %s, 0)""",
            (user_id, name, email.lower().strip(), password_hash, language, now),
        )
        cur.close()
        conn.commit()
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        raise HTTPException(status_code=409, detail="Email already registered")
    return {
        "id": user_id, "name": name,
        "email": email.lower().strip(), "language": language,
        "email_verified": False,
    }


PLAN_WEEKLY_LIMITS = {"free": 3, "hunter": 15}


def authenticate_user(conn: Any, email: str, password: str) -> Optional[dict]:
    cur = conn.cursor()
    cur.execute(
        "SELECT id, name, email, password_hash, language, email_verified, plan FROM users WHERE email = %s",
        (email.lower().strip(),),
    )
    row = cur.fetchone()
    cur.close()
    if not row:
        return None
    if not _verify_password(password, row[3]):
        return None
    return {
        "id": row[0], "name": row[1], "email": row[2],
        "language": row[4], "email_verified": bool(row[5]), "plan": row[6] or "free",
    }


def get_user_by_id(conn: Any, user_id: str) -> Optional[dict]:
    cur = conn.cursor()
    cur.execute(
        "SELECT id, name, email, language, created_at, email_verified, plan FROM users WHERE id = %s",
        (user_id,),
    )
    row = cur.fetchone()
    cur.close()
    if not row:
        return None
    return {
        "id": row[0], "name": row[1], "email": row[2], "language": row[3],
        "created_at": row[4], "email_verified": bool(row[5]), "plan": row[6] or "free",
    }


def upgrade_plan(conn: Any, user_id: str, plan: str = "hunter") -> None:
    cur = conn.cursor()
    cur.execute("UPDATE users SET plan = %s WHERE id = %s", (plan, user_id))
    cur.close()
    conn.commit()


def count_interviews_this_week(conn: Any, user_id: str) -> int:
    week_ago_ms = _now_ms() - 7 * 24 * 3_600_000
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM job_sessions WHERE user_id = %s AND created_at >= %s",
        (user_id, week_ago_ms),
    )
    row = cur.fetchone()
    cur.close()
    return row[0] if row else 0


def update_profile(conn: Any, user_id: str,
                   name: Optional[str], email: Optional[str],
                   current_password: Optional[str], new_password: Optional[str],
                   language: Optional[str] = None) -> dict:
    cur = conn.cursor()
    cur.execute(
        "SELECT name, email, password_hash, language, email_verified FROM users WHERE id = %s",
        (user_id,),
    )
    row = cur.fetchone()
    cur.close()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    cur_name, cur_email, cur_hash, cur_language, email_verified = row

    updates = {}
    email_changed = False

    if name and name.strip() and name.strip() != cur_name:
        updates["name"] = name.strip()

    if email and email.strip().lower() != cur_email:
        # Changing email requires current password
        if not current_password:
            raise HTTPException(status_code=422, detail="Current password required to change email")
        if not _verify_password(current_password, cur_hash):
            raise HTTPException(status_code=401, detail="Current password is incorrect")
        new_email = email.strip().lower()
        cur2 = conn.cursor()
        cur2.execute("SELECT id FROM users WHERE email = %s AND id != %s", (new_email, user_id))
        existing = cur2.fetchone()
        cur2.close()
        if existing:
            raise HTTPException(status_code=409, detail="Email already in use")
        updates["email"] = new_email
        updates["email_verified"] = 0
        updates["verification_token"] = None
        updates["verification_expires"] = None
        email_changed = True

    if new_password:
        if len(new_password) < 8:
            raise HTTPException(status_code=422, detail="New password must be at least 8 characters")
        if not current_password:
            raise HTTPException(status_code=422, detail="Current password required to set a new password")
        if not _verify_password(current_password, cur_hash):
            raise HTTPException(status_code=401, detail="Current password is incorrect")
        updates["password_hash"] = _hash_password(new_password)

    if language and language in ("en", "pt"):
        updates["language"] = language

    if not updates:
        raise HTTPException(status_code=422, detail="Nothing to update")

    set_clause = ", ".join(f"{k} = %s" for k in updates)
    cur3 = conn.cursor()
    cur3.execute(
        f"UPDATE users SET {set_clause} WHERE id = %s",
        (*updates.values(), user_id),
    )
    cur3.close()
    conn.commit()

    return {
        "name": updates.get("name", cur_name),
        "email": updates.get("email", cur_email),
        "language": updates.get("language", cur_language),
        "email_verified": False if email_changed else bool(email_verified),
        "email_changed": email_changed,
    }


# ── Email verification ────────────────────────────────────────────────────────

def create_verification_token(conn: Any, user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    expires = _now_ms() + VERIFICATION_TOKEN_EXPIRES_HOURS * 3_600_000
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET verification_token = %s, verification_expires = %s WHERE id = %s",
        (token, expires, user_id),
    )
    cur.close()
    conn.commit()
    return token


def verify_email_token(conn: Any, token: str) -> Optional[dict]:
    cur = conn.cursor()
    cur.execute(
        "SELECT id, email, verification_expires FROM users WHERE verification_token = %s",
        (token,),
    )
    row = cur.fetchone()
    cur.close()
    if not row:
        return None
    user_id, email, expires = row
    if expires and _now_ms() > expires:
        return None  # expired
    cur2 = conn.cursor()
    cur2.execute(
        "UPDATE users SET email_verified = 1, verification_token = NULL, verification_expires = NULL WHERE id = %s",
        (user_id,),
    )
    cur2.close()
    conn.commit()
    return {"id": user_id, "email": email}


def force_verify_email(conn: Any, user_id: str) -> bool:
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET email_verified = 1, verification_token = NULL, verification_expires = NULL WHERE id = %s",
        (user_id,),
    )
    updated = cur.rowcount
    cur.close()
    conn.commit()
    return updated > 0


# ── Password reset ────────────────────────────────────────────────────────────

def create_reset_token(conn: Any, email: str) -> Optional[tuple[str, str, str]]:
    """Returns (user_id, token, language) or None if email not found."""
    cur = conn.cursor()
    cur.execute("SELECT id, language FROM users WHERE email = %s", (email.lower().strip(),))
    row = cur.fetchone()
    cur.close()
    if not row:
        return None
    user_id, language = row
    token = secrets.token_urlsafe(32)
    expires = _now_ms() + RESET_TOKEN_EXPIRES_MINUTES * 60_000
    cur2 = conn.cursor()
    cur2.execute(
        "UPDATE users SET reset_token = %s, reset_token_expires = %s WHERE id = %s",
        (token, expires, user_id),
    )
    cur2.close()
    conn.commit()
    return user_id, token, language


def reset_password_with_token(conn: Any, token: str, new_password: str) -> bool:
    cur = conn.cursor()
    cur.execute(
        "SELECT id, reset_token_expires FROM users WHERE reset_token = %s",
        (token,),
    )
    row = cur.fetchone()
    cur.close()
    if not row:
        return False
    user_id, expires = row
    if expires and _now_ms() > expires:
        return False
    if len(new_password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters")
    cur2 = conn.cursor()
    cur2.execute(
        "UPDATE users SET password_hash = %s, reset_token = NULL, reset_token_expires = NULL WHERE id = %s",
        (_hash_password(new_password), user_id),
    )
    cur2.close()
    conn.commit()
    return True


# ── Job session helpers ──────────────────────────────────────────────────────

def create_job_session(conn: Any, user_id: str, job_title: str,
                       company: str, job_description: str, resume_text: str,
                       interview_context: str = "") -> str:
    session_id = str(uuid.uuid4())
    now = _now_ms()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO job_sessions
               (id, user_id, job_title, company, job_description, resume_text, interview_context, created_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
        (session_id, user_id, job_title, company, job_description, resume_text, interview_context, now),
    )
    cur.close()
    conn.commit()
    return session_id


def update_job_session_context(conn: Any, session_id: str, interview_context: str) -> None:
    cur = conn.cursor()
    cur.execute(
        "UPDATE job_sessions SET interview_context = %s WHERE id = %s",
        (interview_context, session_id),
    )
    cur.close()
    conn.commit()


def get_job_session(conn: Any, session_id: str, user_id: str) -> Optional[dict]:
    cur = conn.cursor()
    cur.execute(
        """SELECT id, user_id, job_title, company, interview_context, created_at
           FROM job_sessions WHERE id = %s AND user_id = %s""",
        (session_id, user_id),
    )
    row = cur.fetchone()
    cur.close()
    if not row:
        return None
    return {
        "id": row[0], "user_id": row[1], "job_title": row[2],
        "company": row[3], "interview_context": row[4], "created_at": row[5],
    }


def list_job_sessions(conn: Any, user_id: str) -> list:
    cur = conn.cursor()
    cur.execute(
        """SELECT id, job_title, company, created_at
           FROM job_sessions WHERE user_id = %s
           ORDER BY created_at DESC LIMIT 20""",
        (user_id,),
    )
    rows = cur.fetchall()
    cur.close()
    return [{"id": r[0], "job_title": r[1], "company": r[2], "created_at": r[3]} for r in rows]


# ── JWT ──────────────────────────────────────────────────────────────────────

def create_access_token(user_id: str, email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    return jwt.encode(
        {"sub": user_id, "email": email, "exp": expire},
        SECRET_KEY, algorithm=ALGORITHM,
    )


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return {"id": payload["sub"], "email": payload["email"]}
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return decode_token(credentials.credentials)


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Optional[dict]:
    if not credentials:
        return None
    try:
        return decode_token(credentials.credentials)
    except HTTPException:
        return None


def decode_token_raw(token: str) -> Optional[dict]:
    """Non-raising version for WebSocket use."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return {"id": payload["sub"], "email": payload["email"]}
    except JWTError:
        return None


# ── Contact messages ──────────────────────────────────────────────────────────

def create_contact_message(conn: Any, name: str, email: str,
                            subject: str, body: str) -> str:
    msg_id = str(uuid.uuid4())
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO contact_messages (id, name, email, subject, body, created_at) VALUES (%s, %s, %s, %s, %s, %s)",
        (msg_id, name.strip(), email.strip().lower(), subject.strip(), body.strip(), _now_ms()),
    )
    cur.close()
    conn.commit()
    return msg_id


def list_contact_messages(conn: Any) -> list:
    cur = conn.cursor()
    cur.execute(
        "SELECT id, name, email, subject, body, created_at, replied_at, reply_text "
        "FROM contact_messages ORDER BY created_at DESC"
    )
    rows = cur.fetchall()
    cur.close()
    return [
        {
            "id":         r[0],
            "name":       r[1],
            "email":      r[2],
            "subject":    r[3],
            "body":       r[4],
            "created_at": r[5],
            "replied_at": r[6],
            "reply_text": r[7],
        }
        for r in rows
    ]


def save_contact_reply(conn: Any, msg_id: str, reply_text: str) -> bool:
    cur = conn.cursor()
    cur.execute(
        "SELECT reply_text FROM contact_messages WHERE id = %s", (msg_id,)
    )
    existing = cur.fetchone()
    cur.close()
    if existing and existing[0]:
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        combined = existing[0] + f"\n\n--- Reply on {now_str} ---\n" + reply_text.strip()
    else:
        combined = reply_text.strip()
    cur2 = conn.cursor()
    cur2.execute(
        "UPDATE contact_messages SET replied_at = %s, reply_text = %s WHERE id = %s",
        (_now_ms(), combined, msg_id),
    )
    affected = cur2.rowcount
    cur2.close()
    conn.commit()
    return affected > 0


def delete_contact_message(conn: Any, msg_id: str) -> bool:
    cur = conn.cursor()
    cur.execute("DELETE FROM contact_messages WHERE id = %s", (msg_id,))
    affected = cur.rowcount
    cur.close()
    conn.commit()
    return affected > 0


def get_contact_message(conn: Any, msg_id: str) -> Optional[dict]:
    cur = conn.cursor()
    cur.execute(
        "SELECT id, name, email, subject, body, created_at, replied_at, reply_text "
        "FROM contact_messages WHERE id = %s",
        (msg_id,),
    )
    row = cur.fetchone()
    cur.close()
    if not row:
        return None
    return {
        "id":         row[0],
        "name":       row[1],
        "email":      row[2],
        "subject":    row[3],
        "body":       row[4],
        "created_at": row[5],
        "replied_at": row[6],
        "reply_text": row[7],
    }


# ── Stripe helpers ────────────────────────────────────────────────────────────

def set_stripe_info(conn: Any, user_id: str,
                    customer_id: str, subscription_id: str) -> None:
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET stripe_customer_id = %s, stripe_subscription_id = %s WHERE id = %s",
        (customer_id, subscription_id, user_id),
    )
    cur.close()
    conn.commit()


def clear_stripe_subscription(conn: Any, user_id: str) -> None:
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET stripe_subscription_id = NULL WHERE id = %s",
        (user_id,),
    )
    cur.close()
    conn.commit()


def get_user_by_stripe_customer(conn: Any, customer_id: str) -> Optional[dict]:
    cur = conn.cursor()
    cur.execute(
        "SELECT id, email, name, plan FROM users WHERE stripe_customer_id = %s",
        (customer_id,),
    )
    row = cur.fetchone()
    cur.close()
    if not row:
        return None
    return {"id": row[0], "email": row[1], "name": row[2], "plan": row[3]}


def get_user_by_email(conn: Any, email: str) -> Optional[dict]:
    cur = conn.cursor()
    cur.execute(
        "SELECT id, email, name, plan FROM users WHERE email = %s",
        (email.lower(),),
    )
    row = cur.fetchone()
    cur.close()
    if not row:
        return None
    return {"id": row[0], "email": row[1], "name": row[2], "plan": row[3]}


def get_stripe_info(conn: Any, user_id: str) -> dict:
    cur = conn.cursor()
    cur.execute(
        "SELECT stripe_customer_id, stripe_subscription_id, stripe_cancel_at FROM users WHERE id = %s",
        (user_id,),
    )
    row = cur.fetchone()
    cur.close()
    if not row:
        return {}
    return {"stripe_customer_id": row[0], "stripe_subscription_id": row[1], "stripe_cancel_at": row[2]}


def set_stripe_cancel_at(conn: Any, user_id: str, cancel_at) -> None:
    cur = conn.cursor()
    cur.execute("UPDATE users SET stripe_cancel_at = %s WHERE id = %s", (cancel_at, user_id))
    cur.close()
    conn.commit()
