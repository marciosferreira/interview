import psycopg2, sqlite3, os
from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgres://acing_root:cpfl2002@129.121.47.144:5433/acing?sslmode=disable")

pg = psycopg2.connect(DATABASE_URL)
pg.autocommit = True
cur = pg.cursor()

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
        plan                 TEXT NOT NULL DEFAULT 'free',
        stripe_customer_id     TEXT,
        stripe_subscription_id TEXT,
        stripe_cancel_at       BIGINT
    )
""")
cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS stripe_customer_id TEXT")
cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS stripe_subscription_id TEXT")
cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS stripe_cancel_at BIGINT")

cur.execute("""
    CREATE TABLE IF NOT EXISTS job_sessions (
        id                TEXT PRIMARY KEY,
        user_id           TEXT NOT NULL,
        job_title         TEXT NOT NULL,
        company           TEXT NOT NULL DEFAULT '',
        job_description   TEXT NOT NULL,
        resume_text       TEXT NOT NULL,
        interview_context TEXT NOT NULL DEFAULT '',
        created_at        BIGINT NOT NULL
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
print("Tabelas OK")

sq = sqlite3.connect("sessions.db")

users = sq.execute("""
    SELECT id, email, name, password_hash, language, created_at,
           email_verified, verification_token, verification_expires,
           reset_token, reset_token_expires, plan,
           stripe_customer_id, stripe_subscription_id, stripe_cancel_at
    FROM users
""").fetchall()
for u in users:
    cur.execute("""
        INSERT INTO users VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (id) DO UPDATE SET
            plan = EXCLUDED.plan,
            stripe_customer_id = EXCLUDED.stripe_customer_id,
            stripe_subscription_id = EXCLUDED.stripe_subscription_id,
            stripe_cancel_at = EXCLUDED.stripe_cancel_at
    """, u)
print(f"Usuarios migrados: {len(users)}")

jobs = sq.execute("""
    SELECT id, user_id, job_title, company, job_description,
           resume_text, interview_context, created_at FROM job_sessions
""").fetchall()
for j in jobs:
    cur.execute("""
        INSERT INTO job_sessions VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (id) DO NOTHING
    """, j)
print(f"Job sessions migradas: {len(jobs)}")

msgs = sq.execute("""
    SELECT id, name, email, subject, body, created_at, replied_at, reply_text
    FROM contact_messages
""").fetchall()
for m in msgs:
    cur.execute("""
        INSERT INTO contact_messages VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (id) DO NOTHING
    """, m)
print(f"Mensagens migradas: {len(msgs)}")

sq.close()
pg.close()
print("Migracao completa!")
