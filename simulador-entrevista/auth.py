import os
import secrets
import uuid
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Optional

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


# ── DB setup (with migrations for existing DBs) ──────────────────────────────

def setup_user_tables(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id                   TEXT PRIMARY KEY,
            email                TEXT UNIQUE NOT NULL,
            name                 TEXT NOT NULL,
            password_hash        TEXT NOT NULL,
            language             TEXT NOT NULL DEFAULT 'en',
            created_at           INTEGER NOT NULL,
            email_verified       INTEGER NOT NULL DEFAULT 0,
            verification_token   TEXT,
            verification_expires INTEGER,
            reset_token          TEXT,
            reset_token_expires  INTEGER,
            plan                 TEXT NOT NULL DEFAULT 'free'
        )
    """)
    # Migrate existing DBs that lack the new columns
    for col, defn in [
        ("email_verified",       "INTEGER NOT NULL DEFAULT 0"),
        ("verification_token",   "TEXT"),
        ("verification_expires", "INTEGER"),
        ("reset_token",          "TEXT"),
        ("reset_token_expires",  "INTEGER"),
        ("plan",                 "TEXT NOT NULL DEFAULT 'free'"),
    ]:
        try:
            conn.execute(f"ALTER TABLE users ADD COLUMN {col} {defn}")
        except sqlite3.OperationalError:
            pass  # column already exists

    conn.execute("""
        CREATE TABLE IF NOT EXISTS job_sessions (
            id                TEXT PRIMARY KEY,
            user_id           TEXT NOT NULL,
            job_title         TEXT NOT NULL,
            company           TEXT NOT NULL DEFAULT '',
            job_description   TEXT NOT NULL,
            resume_text       TEXT NOT NULL,
            interview_context TEXT NOT NULL DEFAULT '',
            created_at        INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    conn.commit()


# ── User CRUD ────────────────────────────────────────────────────────────────

def create_user(conn: sqlite3.Connection, name: str, email: str,
                password: str, language: str = "en") -> dict:
    user_id = str(uuid.uuid4())
    password_hash = _hash_password(password)
    now = _now_ms()
    try:
        conn.execute(
            """INSERT INTO users (id, name, email, password_hash, language, created_at, email_verified)
               VALUES (?, ?, ?, ?, ?, ?, 0)""",
            (user_id, name, email.lower().strip(), password_hash, language, now),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Email already registered")
    return {
        "id": user_id, "name": name,
        "email": email.lower().strip(), "language": language,
        "email_verified": False,
    }


PLAN_WEEKLY_LIMITS = {"free": 3, "hunter": 15}


def authenticate_user(conn: sqlite3.Connection, email: str, password: str) -> Optional[dict]:
    row = conn.execute(
        "SELECT id, name, email, password_hash, language, email_verified, plan FROM users WHERE email = ?",
        (email.lower().strip(),),
    ).fetchone()
    if not row:
        return None
    if not _verify_password(password, row[3]):
        return None
    return {
        "id": row[0], "name": row[1], "email": row[2],
        "language": row[4], "email_verified": bool(row[5]), "plan": row[6] or "free",
    }


def get_user_by_id(conn: sqlite3.Connection, user_id: str) -> Optional[dict]:
    row = conn.execute(
        "SELECT id, name, email, language, created_at, email_verified, plan FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    if not row:
        return None
    return {
        "id": row[0], "name": row[1], "email": row[2], "language": row[3],
        "created_at": row[4], "email_verified": bool(row[5]), "plan": row[6] or "free",
    }


def upgrade_plan(conn: sqlite3.Connection, user_id: str, plan: str = "hunter") -> None:
    conn.execute("UPDATE users SET plan = ? WHERE id = ?", (plan, user_id))
    conn.commit()


def count_interviews_this_week(conn: sqlite3.Connection, user_id: str) -> int:
    week_ago_ms = _now_ms() - 7 * 24 * 3_600_000
    row = conn.execute(
        "SELECT COUNT(*) FROM job_sessions WHERE user_id = ? AND created_at >= ?",
        (user_id, week_ago_ms),
    ).fetchone()
    return row[0] if row else 0


def update_profile(conn: sqlite3.Connection, user_id: str,
                   name: Optional[str], email: Optional[str],
                   current_password: Optional[str], new_password: Optional[str]) -> dict:
    row = conn.execute(
        "SELECT name, email, password_hash, language, email_verified FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    cur_name, cur_email, cur_hash, language, email_verified = row

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
        existing = conn.execute("SELECT id FROM users WHERE email = ? AND id != ?", (new_email, user_id)).fetchone()
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

    if not updates:
        raise HTTPException(status_code=422, detail="Nothing to update")

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    conn.execute(
        f"UPDATE users SET {set_clause} WHERE id = ?",
        (*updates.values(), user_id),
    )
    conn.commit()

    return {
        "name": updates.get("name", cur_name),
        "email": updates.get("email", cur_email),
        "email_verified": False if email_changed else bool(email_verified),
        "email_changed": email_changed,
    }


# ── Email verification ────────────────────────────────────────────────────────

def create_verification_token(conn: sqlite3.Connection, user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    expires = _now_ms() + VERIFICATION_TOKEN_EXPIRES_HOURS * 3_600_000
    conn.execute(
        "UPDATE users SET verification_token = ?, verification_expires = ? WHERE id = ?",
        (token, expires, user_id),
    )
    conn.commit()
    return token


def verify_email_token(conn: sqlite3.Connection, token: str) -> Optional[dict]:
    row = conn.execute(
        "SELECT id, email, verification_expires FROM users WHERE verification_token = ?",
        (token,),
    ).fetchone()
    if not row:
        return None
    user_id, email, expires = row
    if expires and _now_ms() > expires:
        return None  # expired
    conn.execute(
        "UPDATE users SET email_verified = 1, verification_token = NULL, verification_expires = NULL WHERE id = ?",
        (user_id,),
    )
    conn.commit()
    return {"id": user_id, "email": email}


# ── Password reset ────────────────────────────────────────────────────────────

def create_reset_token(conn: sqlite3.Connection, email: str) -> Optional[tuple[str, str]]:
    """Returns (user_id, token) or None if email not found."""
    row = conn.execute("SELECT id FROM users WHERE email = ?", (email.lower().strip(),)).fetchone()
    if not row:
        return None
    user_id = row[0]
    token = secrets.token_urlsafe(32)
    expires = _now_ms() + RESET_TOKEN_EXPIRES_MINUTES * 60_000
    conn.execute(
        "UPDATE users SET reset_token = ?, reset_token_expires = ? WHERE id = ?",
        (token, expires, user_id),
    )
    conn.commit()
    return user_id, token


def reset_password_with_token(conn: sqlite3.Connection, token: str, new_password: str) -> bool:
    row = conn.execute(
        "SELECT id, reset_token_expires FROM users WHERE reset_token = ?",
        (token,),
    ).fetchone()
    if not row:
        return False
    user_id, expires = row
    if expires and _now_ms() > expires:
        return False
    if len(new_password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters")
    conn.execute(
        "UPDATE users SET password_hash = ?, reset_token = NULL, reset_token_expires = NULL WHERE id = ?",
        (_hash_password(new_password), user_id),
    )
    conn.commit()
    return True


# ── Job session helpers ──────────────────────────────────────────────────────

def create_job_session(conn: sqlite3.Connection, user_id: str, job_title: str,
                       company: str, job_description: str, resume_text: str,
                       interview_context: str = "") -> str:
    session_id = str(uuid.uuid4())
    now = _now_ms()
    conn.execute(
        """INSERT INTO job_sessions
               (id, user_id, job_title, company, job_description, resume_text, interview_context, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (session_id, user_id, job_title, company, job_description, resume_text, interview_context, now),
    )
    conn.commit()
    return session_id


def update_job_session_context(conn: sqlite3.Connection, session_id: str, interview_context: str) -> None:
    conn.execute(
        "UPDATE job_sessions SET interview_context = ? WHERE id = ?",
        (interview_context, session_id),
    )
    conn.commit()


def get_job_session(conn: sqlite3.Connection, session_id: str, user_id: str) -> Optional[dict]:
    row = conn.execute(
        """SELECT id, user_id, job_title, company, interview_context, created_at
           FROM job_sessions WHERE id = ? AND user_id = ?""",
        (session_id, user_id),
    ).fetchone()
    if not row:
        return None
    return {
        "id": row[0], "user_id": row[1], "job_title": row[2],
        "company": row[3], "interview_context": row[4], "created_at": row[5],
    }


def list_job_sessions(conn: sqlite3.Connection, user_id: str) -> list:
    rows = conn.execute(
        """SELECT id, job_title, company, created_at
           FROM job_sessions WHERE user_id = ?
           ORDER BY created_at DESC LIMIT 20""",
        (user_id,),
    ).fetchall()
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
