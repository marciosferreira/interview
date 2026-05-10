import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated, Optional
from typing_extensions import TypedDict
from langchain_core.runnables import RunnableConfig

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
import json as _json

# Carrega .env antes de ler qualquer variável de ambiente
load_dotenv()


def _invoke_with_retry(runnable, messages, max_retries: int = 5, base_delay: float = 5.0):
    """Invoke a LangChain runnable with exponential backoff on Anthropic 529 Overloaded."""
    from anthropic import APIStatusError
    for attempt in range(max_retries):
        try:
            return runnable.invoke(messages)
        except APIStatusError as exc:
            if exc.status_code == 529 and attempt < max_retries - 1:
                wait = base_delay * (2 ** attempt)
                print(f"[retry] Anthropic overloaded (529) — waiting {wait:.0f}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait)
            else:
                raise

import sqlite3 as _sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver as _SqliteSaver

_database_url = os.getenv("DATABASE_URL")

if _database_url:
    # ── PostgreSQL (produção) — app data only ─────────────────────────────────
    try:
        import psycopg2 as _psycopg2
        from psycopg2.pool import ThreadedConnectionPool as _ThreadedConnectionPool

        _pool = _ThreadedConnectionPool(
            2, 10,
            dsn=_database_url,
            connect_timeout=15,
            options="-c lock_timeout=5000 -c statement_timeout=30000",
        )
        _conn = None

        @contextmanager
        def get_db_conn():
            conn = _pool.getconn()
            conn.autocommit = True
            try:
                yield conn
            finally:
                _pool.putconn(conn)

    except Exception as _e:
        print(f"[warn] Falha ao conectar no PostgreSQL: {_e}")
        _pool = None
        _conn = None

        @contextmanager
        def get_db_conn():
            yield None

else:
    # ── SQLite (dev local sem DATABASE_URL) — app data ────────────────────────
    _db_path = str(Path(__file__).parent / "sessions.db")
    _conn = _sqlite3.connect(_db_path, check_same_thread=False)
    _pool = None

    @contextmanager
    def get_db_conn():
        yield _conn


# ── LangGraph checkpointer — always SQLite, separate connection ───────────────
# Survives server restarts in both dev (local file) and prod (persistent volume).
# Set LANGGRAPH_DB_PATH env var to a volume-mounted path in production.
_cp_path = os.getenv("LANGGRAPH_DB_PATH", str(Path(__file__).parent / "sessions.db"))
try:
    _cp_conn = _sqlite3.connect(_cp_path, check_same_thread=False)
    _cp_saver = _SqliteSaver(_cp_conn)
    _cp_saver.setup()
    _Checkpointer = lambda: _cp_saver  # noqa: E731
    print(f"[checkpointer] SQLite → {_cp_path}")
except Exception as _e:
    print(f"[warn] SQLite checkpointer failed: {_e} — using MemorySaver (sessions won't survive restarts)")
    from langgraph.checkpoint.memory import MemorySaver as _MemorySaver
    _Checkpointer = _MemorySaver

_is_pg = _pool is not None


# ── Session store ─────────────────────────────────────────────────────────────

class SessionStore:
    """Stores chat history + metadata for the dashboard page.
    Backed by sessions.db (SQLite) or PostgreSQL pool; falls back to in-memory dict.
    """

    def __init__(self):
        self._is_pg = _is_pg
        has_db = _pool is not None or _conn is not None
        if has_db:
            with get_db_conn() as conn:
                if conn is None:
                    self._mem: dict = {}
                    return
                if self._is_pg:
                    cur = conn.cursor()
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS session_meta (
                            thread_id      TEXT PRIMARY KEY,
                            user_id        TEXT,
                            job_session_id TEXT,
                            started_at     BIGINT NOT NULL,
                            last_active_at BIGINT NOT NULL,
                            fase           TEXT   NOT NULL DEFAULT '',
                            history        TEXT   NOT NULL DEFAULT '[]'
                        )
                    """)
                    for col, defn in [
                        ("user_id",        "TEXT"),
                        ("job_session_id", "TEXT"),
                        ("scorecard_text", "TEXT"),
                    ]:
                        cur.execute(f"ALTER TABLE session_meta ADD COLUMN IF NOT EXISTS {col} {defn}")
                    cur.close()
                else:
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS session_meta (
                            thread_id      TEXT PRIMARY KEY,
                            user_id        TEXT,
                            job_session_id TEXT,
                            started_at     INTEGER NOT NULL,
                            last_active_at INTEGER NOT NULL,
                            fase           TEXT    NOT NULL DEFAULT '',
                            history        TEXT    NOT NULL DEFAULT '[]'
                        )
                    """)
                    for col_def in [
                        "ALTER TABLE session_meta ADD COLUMN user_id TEXT",
                        "ALTER TABLE session_meta ADD COLUMN job_session_id TEXT",
                        "ALTER TABLE session_meta ADD COLUMN scorecard_text TEXT",
                    ]:
                        try:
                            conn.execute(col_def)
                        except Exception:
                            pass
                    conn.commit()
        else:
            self._mem = {}

    def _exec(self, conn, sql: str, params=()):
        """Execute a query on the given connection; return cursor (pg) or result (sqlite)."""
        if self._is_pg:
            cur = conn.cursor()
            cur.execute(sql, params)
            return cur
        return conn.execute(sql, params)

    def upsert(self, thread_id: str, started_at: int, last_active_at: int,
               fase: str, history: list,
               user_id: Optional[str] = None, job_session_id: Optional[str] = None) -> None:
        if _pool is not None or _conn is not None:
            ph = "%s" if self._is_pg else "?"
            sql = f"""INSERT INTO session_meta
                       (thread_id, user_id, job_session_id, started_at, last_active_at, fase, history)
                   VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
                   ON CONFLICT(thread_id) DO UPDATE SET
                       last_active_at = excluded.last_active_at,
                       fase           = excluded.fase,
                       history        = excluded.history"""
            with get_db_conn() as conn:
                cur = self._exec(conn, sql, (thread_id, user_id, job_session_id, started_at,
                                             last_active_at, fase, _json.dumps(history)))
                if self._is_pg:
                    cur.close()
                else:
                    conn.commit()
        else:
            self._mem[thread_id] = dict(
                threadId=thread_id, userId=user_id, jobSessionId=job_session_id,
                startedAt=started_at, lastActiveAt=last_active_at, fase=fase, history=history,
            )

    def list_sessions(self, user_id: Optional[str] = None, limit: int = 20) -> list:
        if _pool is not None or _conn is not None:
            ph = "%s" if self._is_pg else "?"
            if user_id:
                sql = f"""SELECT sm.thread_id, sm.user_id, sm.job_session_id,
                              sm.started_at, sm.last_active_at, sm.fase, sm.history,
                              js.job_title, js.company, sm.scorecard_text
                       FROM session_meta sm
                       LEFT JOIN job_sessions js ON sm.job_session_id = js.id
                       WHERE sm.user_id = {ph}
                       ORDER BY sm.last_active_at DESC LIMIT {ph}"""
                params = (user_id, limit)
            else:
                sql = f"""SELECT sm.thread_id, sm.user_id, sm.job_session_id,
                              sm.started_at, sm.last_active_at, sm.fase, sm.history,
                              js.job_title, js.company, sm.scorecard_text
                       FROM session_meta sm
                       LEFT JOIN job_sessions js ON sm.job_session_id = js.id
                       ORDER BY sm.last_active_at DESC LIMIT {ph}"""
                params = (limit,)
            with get_db_conn() as conn:
                cur = self._exec(conn, sql, params)
                rows = cur.fetchall()
                if self._is_pg:
                    cur.close()
            return [
                {
                    "threadId":      r[0],
                    "userId":        r[1],
                    "jobSessionId":  r[2],
                    "startedAt":     r[3],
                    "lastActiveAt":  r[4],
                    "fase":          r[5],
                    "history":       _json.loads(r[6]),
                    "jobTitle":      r[7] or "",
                    "company":       r[8] or "",
                    "hireSignal":    extract_hire_signal(r[9] or ""),
                }
                for r in rows
            ]
        else:
            sessions = list(self._mem.values())
            if user_id:
                sessions = [s for s in sessions if s.get("userId") == user_id]
            return sorted(sessions, key=lambda s: s["lastActiveAt"], reverse=True)[:limit]

    def delete(self, thread_id: str, user_id: Optional[str] = None) -> None:
        if _pool is not None or _conn is not None:
            ph = "%s" if self._is_pg else "?"
            if user_id:
                sql = f"DELETE FROM session_meta WHERE thread_id = {ph} AND user_id = {ph}"
                params = (thread_id, user_id)
            else:
                sql = f"DELETE FROM session_meta WHERE thread_id = {ph}"
                params = (thread_id,)
            with get_db_conn() as conn:
                cur = self._exec(conn, sql, params)
                if self._is_pg:
                    cur.close()
                else:
                    conn.commit()
        else:
            self._mem.pop(thread_id, None)

    def save_history(self, thread_id: str, user_id: str, history: list) -> None:
        if _pool is not None or _conn is not None:
            ph = "%s" if self._is_pg else "?"
            sql = f"UPDATE session_meta SET history = {ph} WHERE thread_id = {ph} AND user_id = {ph}"
            with get_db_conn() as conn:
                cur = self._exec(conn, sql, (_json.dumps(history), thread_id, user_id))
                if self._is_pg:
                    cur.close()
                else:
                    conn.commit()
        elif thread_id in self._mem:
            self._mem[thread_id]["history"] = history

    def get_history(self, thread_id: str, user_id: str) -> list:
        if _pool is not None or _conn is not None:
            ph = "%s" if self._is_pg else "?"
            sql = f"SELECT history FROM session_meta WHERE thread_id = {ph} AND user_id = {ph}"
            with get_db_conn() as conn:
                cur = self._exec(conn, sql, (thread_id, user_id))
                row = cur.fetchone()
                if self._is_pg:
                    cur.close()
            return _json.loads(row[0]) if row and row[0] else []
        return self._mem.get(thread_id, {}).get("history", [])

    def save_scorecard(self, thread_id: str, user_id: str, scorecard_text: str) -> None:
        if _pool is not None or _conn is not None:
            ph = "%s" if self._is_pg else "?"
            sql = f"UPDATE session_meta SET scorecard_text = {ph} WHERE thread_id = {ph} AND user_id = {ph}"
            with get_db_conn() as conn:
                cur = self._exec(conn, sql, (scorecard_text, thread_id, user_id))
                if self._is_pg:
                    cur.close()
                else:
                    conn.commit()

    def owns_session(self, thread_id: str, user_id: str) -> bool:
        if _pool is not None or _conn is not None:
            ph = "%s" if self._is_pg else "?"
            sql = f"SELECT 1 FROM session_meta WHERE thread_id = {ph} AND user_id = {ph}"
            with get_db_conn() as conn:
                cur = self._exec(conn, sql, (thread_id, user_id))
                row = cur.fetchone()
                if self._is_pg:
                    cur.close()
            return row is not None
        return thread_id in self._mem

    def get_scorecard(self, thread_id: str, user_id: str) -> Optional[str]:
        if _pool is not None or _conn is not None:
            ph = "%s" if self._is_pg else "?"
            sql = f"SELECT scorecard_text FROM session_meta WHERE thread_id = {ph} AND user_id = {ph}"
            with get_db_conn() as conn:
                cur = self._exec(conn, sql, (thread_id, user_id))
                row = cur.fetchone()
                if self._is_pg:
                    cur.close()
            return row[0] if row else None
        return None


session_store = SessionStore()

# ── Setup auth tables ─────────────────────────────────────────────────────────
# Done here so the pool/conn is shared across auth.py and simulator.py without circular imports.
if _pool is not None or _conn is not None:
    from auth import setup_user_tables
    with get_db_conn() as _setup_conn:
        if _setup_conn is not None:
            setup_user_tables(_setup_conn)

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.types import interrupt, Command
from pydantic import BaseModel, BeforeValidator, Field


def _coerce_list(v):
    if isinstance(v, list):
        return v
    if isinstance(v, str):
        try:
            parsed = _json.loads(v)
            if isinstance(parsed, list):
                return parsed
        except (_json.JSONDecodeError, ValueError):
            pass
        return [v] if v.strip() else []
    return v


StrList = Annotated[list[str], BeforeValidator(_coerce_list)]

_EXPLORER_MODEL = os.getenv("EXPLORER_MODEL", "claude-haiku-4-5-20251001")
_HUNTER_MODEL   = os.getenv("HUNTER_MODEL",   "claude-sonnet-4-6")

_model_explorer = ChatAnthropic(model=_EXPLORER_MODEL, api_key=os.getenv("ANTHROPIC_API_KEY"))
_model_hunter   = ChatAnthropic(model=_HUNTER_MODEL,   api_key=os.getenv("ANTHROPIC_API_KEY"))

model = _model_explorer  # fallback used by _stream_to_client default


def get_model(plan: str) -> ChatAnthropic:
    """Return the LLM instance for the given user plan."""
    return _model_hunter if plan == "hunter" else _model_explorer

# ---------------------------------------------------------------------------
# Prompt loader
# ---------------------------------------------------------------------------

PROMPTS_DIR = Path(__file__).parent / "prompts"


def load_prompt(*filenames: str) -> str:
    parts = []
    for name in filenames:
        path = PROMPTS_DIR / name
        parts.append(path.read_text(encoding="utf-8"))
    return "\n\n---\n\n".join(parts)


# Static base prompts (generic — no candidate-specific content)
_PERSONA      = load_prompt("persona_alex.md")
_REPORT_BASE  = load_prompt("report_format_generic.md")
_SCORECARD    = load_prompt("scorecard_generic.md")
_PHASE_FILES  = {
    "elevator_pitch": load_prompt("elevator_pitch_generic.md"),
    "CAR":            load_prompt("car_generic.md"),
    "technical":      load_prompt("technical_generic.md"),
    "leadership":     load_prompt("leadership_generic.md"),
    "motivation":     load_prompt("motivation_generic.md"),
    "candidate_questions": load_prompt("candidate_questions_generic.md"),
}


_LANG_REMINDER = {
    "en": "\n\n---\n\n**FINAL REMINDER:** Respond in English only. If the candidate writes in another language, redirect them to English before continuing.",
    "pt": "\n\n---\n\n**LEMBRETE FINAL:** Responda SOMENTE em Português do Brasil. Se o candidato escrever em outro idioma, redirecione-o gentilmente antes de continuar.",
}


def _build_interview_system(interview_context: str, phase: str, language: str = "en") -> str:
    """Compose: persona + candidate context + phase guide.

    Only injects the interview_context sections relevant to this phase so the
    model cannot 'see' questions from other phases and confuse them.
    """
    phase_guide = _PHASE_FILES.get(phase, "")
    lang_block = "\n\n---\n\n" + _LANG_DIRECTIVE.get(language, _LANG_DIRECTIVE["en"])
    slim_context = _extract_context_for_phase(interview_context, phase, extra=_INTERVIEW_EXTRA_SECTIONS)
    context_block = (
        "\n\n---\n\n## CANDIDATE & JOB CONTEXT\n\n"
        + slim_context
        + "\n\n---\n\n"
    ) if slim_context else "\n\n---\n\n"
    lang_reminder = _LANG_REMINDER.get(language, _LANG_REMINDER["en"])
    return _PERSONA + lang_block + context_block + phase_guide + lang_reminder


_REPORT_PHASE_SECTIONS = {
    "elevator_pitch": "# ELEVATOR PITCH GUIDANCE",
    "CAR":            "# CAR PROJECT GUIDANCE",
    "technical":      "# TECHNICAL EVALUATION FOCUS",
    "leadership":     "# LEADERSHIP & APPROACH EVALUATION",
    "motivation":     "# FIT & MOTIVATION EVALUATION",
}

# Sections always included regardless of phase
_ALWAYS_INCLUDE_SECTIONS = {"# CANDIDATE PROFILE", "# LANGUAGE & COMMUNICATION NOTES"}
# Also included for interview nodes (gives role-level context without leaking other phase content)
_INTERVIEW_EXTRA_SECTIONS = {"# TARGET ROLE ANALYSIS"}


def _extract_context_for_phase(interview_context: str, phase: str, extra: set = frozenset()) -> str:
    """Return only the sections of interview_context relevant to a given phase."""
    if not interview_context:
        return ""
    phase_section = _REPORT_PHASE_SECTIONS.get(phase, "")
    keep = _ALWAYS_INCLUDE_SECTIONS | extra | ({phase_section} if phase_section else set())

    import re
    parts = re.split(r'(?=^# )', interview_context, flags=re.MULTILINE)
    selected = []
    for part in parts:
        heading = part.split('\n', 1)[0].strip()
        if not heading or any(heading.startswith(h) for h in keep):
            selected.append(part)
    return "\n\n".join(selected).strip()


def _extract_context_for_report(interview_context: str, phase: str) -> str:
    return _extract_context_for_phase(interview_context, phase)


_REPORT_LANG_PREFIX = {
    "pt": (
        "**INSTRUÇÃO DE IDIOMA — PRIORIDADE MÁXIMA:** Todo o relatório — títulos, rótulos, "
        "seções e conteúdo — deve ser escrito EXCLUSIVAMENTE em Português do Brasil. "
        "Não use inglês em nenhuma parte da resposta."
    ),
    "en": (
        "**LANGUAGE INSTRUCTION — HIGHEST PRIORITY:** The entire report — all headers, "
        "labels, sections, and content — must be written EXCLUSIVELY in English. "
        "Do not use any other language."
    ),
}


def _build_report_system(interview_context: str, phase: str, language: str = "en") -> str:
    """Compose: language prefix + report format + phase context + phase guide."""
    lang_prefix = _REPORT_LANG_PREFIX.get(language, _REPORT_LANG_PREFIX["en"])
    phase_guide = _PHASE_FILES.get(phase, "")
    slim_context = _extract_context_for_report(interview_context, phase)
    context_block = (
        "\n\n---\n\n## CANDIDATE & JOB CONTEXT\n\n"
        + slim_context
        + "\n\n---\n\n"
    ) if slim_context else "\n\n---\n\n"
    return lang_prefix + "\n\n---\n\n" + _REPORT_BASE + context_block + phase_guide


def _build_scorecard_system(interview_context: str, language: str = "en") -> str:
    lang_block = "\n\n---\n\n" + _LANG_DIRECTIVE.get(language, _LANG_DIRECTIVE["en"])
    context_block = (
        "\n\n---\n\n## CANDIDATE & JOB CONTEXT\n\n"
        + interview_context
        + "\n\n---\n\n"
    ) if interview_context else "\n\n---\n\n"
    lang_reminder = _LANG_REMINDER.get(language, _LANG_REMINDER["en"])
    return _SCORECARD + lang_block + context_block + lang_reminder


def _cached_system(prompt: str) -> SystemMessage:
    return SystemMessage(content=[{
        "type": "text",
        "text": prompt,
        "cache_control": {"type": "ephemeral"},
    }])


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

_LANG_DIRECTIVE = {
    "en": (
        "## LANGUAGE REQUIREMENT — ENGLISH\n\n"
        "**This entire interview must be conducted in English.** "
        "Every message you send — opening lines, questions, follow-ups, coaching nudges, phase transitions, and closings — must be in English. "
        "Adapt any template phrasing from the phase guide to English if needed (they are already written in English). "
        "If the candidate responds in a language other than English, acknowledge their answer briefly and remind them: "
        "'Just a reminder — this interview is in English. Please continue in English.' "
        "Then ask your follow-up in English. Never switch to another language under any circumstances."
    ),
    "pt": (
        "## REQUISITO DE IDIOMA — PORTUGUÊS DO BRASIL\n\n"
        "**Toda esta entrevista deve ser conduzida em Português do Brasil.** "
        "Todas as suas mensagens devem estar em Português do Brasil — linhas de abertura, perguntas, follow-ups, dicas de coaching, transições de fase e encerramento. "
        "Adapte TODAS as frases de exemplo dos guias de fase para o Português do Brasil. "
        "NUNCA reproduza as linhas de abertura em inglês — elas são apenas referências de conteúdo, não de idioma. "
        "Se o candidato responder em inglês ou qualquer outro idioma, reconheça a resposta e lembre-o gentilmente: "
        "'Só um aviso — esta entrevista está sendo conduzida em Português do Brasil. Por favor, continue respondendo em Português.' "
        "Em seguida, faça sua pergunta em Português. Nunca mude de idioma, independentemente do que o candidato faça. "
        "O campo `english_adequate` deve avaliar a qualidade da comunicação em Português do candidato."
    ),
}


class EntrevistaState(TypedDict):
    messages:       Annotated[list, add_messages]
    phase_messages: list
    archive:        list
    fase:           str
    language:       str      # user's preferred language ("en" or "pt")
    user_plan:      str      # "explorer" or "hunter" — determines which LLM model to use
    interview_context: str   # generated per-session from CV + job description
    candidate_name: str      # extracted from interview_context
    job_title:      str
    company:        str

    checklist_pitch:      dict
    checklist_CAR:        dict
    checklist_technical:  dict
    checklist_leadership: dict
    checklist_motivation: dict

    notas_pitch:      str
    notas_CAR:        str
    notas_technical:  str
    notas_leadership: str
    notas_motivation: str

    ingles_erros_acumulados: list


# ---------------------------------------------------------------------------
# Generic Pydantic models (phase-agnostic, driven by system prompt context)
# ---------------------------------------------------------------------------

_MENSAGEM_FIELD = Field(
    description=(
        "Alex's next spoken line — a question or short coaching nudge only. "
        "(1) Opening turn: reproduce the exact greeting from the phase prompt verbatim. "
        "(2) Ongoing interview: one follow-up question or coaching prompt, 1–3 sentences max. "
        "(3) Coaching after 2+ failed attempts: a brief hint. "
        "(4) When fase_completa=True or skip_requested=True: set this to exactly 'OK'. "
        "NEVER include feedback, scoring, report content, or a summary of how the candidate did. "
        "The Judge handles all feedback after the phase ends — Alex never delivers it. "
        "CRITICAL: Alex has already read the candidate's CV from CANDIDATE & JOB CONTEXT. "
        "NEVER ask for information that is already there (name, employer, tenure, degree, role title). "
        "Follow-ups must probe DEPTH, IMPACT, or DIFFERENTIATION — not re-collect known facts."
    )
)

_SKIP_REQUESTED_FIELD = Field(
    default=False,
    description=(
        "Set to True if — and only if — the candidate's most recent message clearly expresses "
        "a desire to skip this phase, move on, or not answer further. "
        "Recognize any natural phrasing in any language: 'skip', 'pular', 'next', 'move on', "
        "'quero pular', 'pode ir para a próxima', 'vamos avançar', 'let's continue', etc. "
        "NEVER set this on the very first turn (when there is no real candidate response yet). "
        "NEVER set this if the candidate is answering the question, even partially or poorly."
    )
)


class ElevatorPitchPhase(BaseModel):
    personal_intro_clear: bool
    background_framed_as_asset: bool
    key_achievement_mentioned: bool
    career_narrative_coherent: bool
    current_role_in_business_terms: bool
    closes_with_differentiator: bool
    english_adequate: bool
    mensagem: str = _MENSAGEM_FIELD
    fase_completa: bool
    skip_requested: bool = _SKIP_REQUESTED_FIELD
    observacoes: str
    ingles_erros: StrList


class CARPhase(BaseModel):
    business_context_clear: bool
    problem_stated_clearly: bool
    personal_ownership: bool
    specific_actions: bool
    deliberate_choices: bool
    result_in_business_terms: bool
    production_mindset: bool
    english_adequate: bool
    mensagem: str = _MENSAGEM_FIELD
    fase_completa: bool
    skip_requested: bool = _SKIP_REQUESTED_FIELD
    observacoes: str
    ingles_erros: StrList


class TechnicalPhase(BaseModel):
    q1_answered: bool
    q2_answered: bool
    q3_answered: bool
    answers_show_depth: bool
    production_mindset: bool
    english_adequate: bool
    mensagem: str = _MENSAGEM_FIELD
    fase_completa: bool
    skip_requested: bool = _SKIP_REQUESTED_FIELD
    observacoes: str
    ingles_erros: StrList


class LeadershipPhase(BaseModel):
    starts_with_situation_assessment: bool
    identifies_primary_risk: bool
    execution_realism: bool
    concrete_mitigation_plan: bool
    stakeholder_management: bool
    connects_to_real_experience: bool
    english_adequate: bool
    mensagem: str = _MENSAGEM_FIELD
    fase_completa: bool
    skip_requested: bool = _SKIP_REQUESTED_FIELD
    observacoes: str
    ingles_erros: StrList


class MotivationPhase(BaseModel):
    specific_company_knowledge: bool
    genuine_connection: bool
    unique_fit: bool
    authentic_tone: bool
    english_adequate: bool
    mensagem: str = _MENSAGEM_FIELD
    fase_completa: bool
    skip_requested: bool = _SKIP_REQUESTED_FIELD
    observacoes: str
    ingles_erros: StrList


class CandidateQuestionsPhase(BaseModel):
    mensagem: str = _MENSAGEM_FIELD
    fase_completa: bool
    skip_requested: bool = _SKIP_REQUESTED_FIELD
    observacoes: str


class Scorecard(BaseModel):
    score_pitch:       int
    comentario_pitch:  str
    score_CAR:         int
    comentario_CAR:    str
    score_technical:   int
    comentario_technical: str
    score_leadership:  int
    comentario_leadership: str
    score_motivation:  int
    comentario_motivation: str
    oportunidades_pitch:      StrList
    oportunidades_CAR:        StrList
    oportunidades_technical:  StrList
    oportunidades_leadership: StrList
    vocabulario_para_praticar: StrList
    ingles_rating:   str
    ingles_padroes:  StrList
    score_total:     int
    hire_signal:     str
    forcas:          StrList
    melhorias:       StrList
    insight_chave:   str


# ---------------------------------------------------------------------------
# Node factories
# ---------------------------------------------------------------------------

# Opening messages that don't count as real candidate input for skip detection
_PHASE_OPENING_MSGS = frozenset({
    "I'm ready to start this phase.",
    "Olá, estou pronto para começar a entrevista.",
    "Hi, I'm ready to start the interview.",
})


def _has_real_candidate_input(phase_msgs: list) -> bool:
    """True if the candidate has sent at least one real reply (not just the synthetic opener)."""
    return any(
        isinstance(m, HumanMessage)
        and m.content not in _PHASE_OPENING_MSGS
        and not m.content.startswith("[")
        for m in phase_msgs
    )


_MAX_EXCHANGES_PER_PHASE = 4


def _make_interview_node(output_class, checklist_key, notas_key, report_fase, phase_name):
    def node(state: EntrevistaState, config: RunnableConfig) -> dict:
        interview_context = state.get("interview_context", "")
        language = state.get("language", "en")
        system_prompt = _build_interview_system(interview_context, phase_name, language)
        structured = get_model(state.get("user_plan", "explorer")).with_structured_output(output_class)

        phase_msgs: list = state.get("phase_messages") or [
            HumanMessage(content="I'm ready to start this phase.")
        ]

        # Hard exchange limit: count AI messages already sent in this phase.
        # Each AI message represents one exchange. After MAX_EXCHANGES, force advance
        # without calling the LLM — the phase ends regardless of checklist status.
        ai_exchange_count = sum(1 for m in phase_msgs if isinstance(m, AIMessage))
        if ai_exchange_count >= _MAX_EXCHANGES_PER_PHASE:
            return {
                "messages": [],
                "phase_messages": phase_msgs,
                checklist_key: state[checklist_key],
                notas_key: state[notas_key],
                "ingles_erros_acumulados": state.get("ingles_erros_acumulados", []),
                "fase": report_fase,
            }

        # On the final allowed exchange, append the limit notice to the system prompt
        if ai_exchange_count == _MAX_EXCHANGES_PER_PHASE - 1:
            system_prompt = (
                system_prompt
                + "\n\n[INTERVIEWER INSTRUCTION: This is exchange 4 — the final exchange for this phase. "
                "After the candidate's response you must set fase_completa=True. "
                "Keep your closing remark brief.]"
            )

        messages = [_cached_system(system_prompt)] + phase_msgs

        avaliacao = _invoke_with_retry(structured, messages)

        old_checklist = state[checklist_key]
        new_checklist = {
            k: old_checklist.get(k, False) or getattr(avaliacao, k, False)
            for k in old_checklist
        }
        old_notas = state[notas_key]
        new_notas = (old_notas + "\n" + avaliacao.observacoes).strip() if avaliacao.observacoes else old_notas
        old_ingles = state.get("ingles_erros_acumulados", [])
        new_ingles = old_ingles + (avaliacao.ingles_erros or [])

        # Skip detected via structured output (model understood candidate's intent semantically)
        if avaliacao.skip_requested and _has_real_candidate_input(phase_msgs):
            return {
                "messages": [],
                "phase_messages": phase_msgs + [
                    HumanMessage(content="[Candidate skipped — phase incomplete]"),
                ],
                checklist_key: new_checklist,
                notas_key: new_notas,
                "ingles_erros_acumulados": new_ingles,
                "fase": report_fase,
            }

        # Safety guard: mensagem="OK" with fase_completa=False → treat as complete
        if avaliacao.mensagem.strip().lower() == "ok" and not avaliacao.fase_completa:
            return {
                "messages": [],
                "phase_messages": phase_msgs,
                checklist_key: new_checklist,
                notas_key: new_notas,
                "ingles_erros_acumulados": new_ingles,
                "fase": report_fase,
            }

        if not avaliacao.fase_completa:
            user_response = interrupt(avaliacao.mensagem)

            new_phase_msgs = phase_msgs + [
                AIMessage(content=avaliacao.mensagem),
                HumanMessage(content=user_response),
            ]
            return {
                "messages": [
                    AIMessage(content=avaliacao.mensagem),
                    HumanMessage(content=user_response),
                ],
                "phase_messages": new_phase_msgs,
                checklist_key: new_checklist,
                notas_key: new_notas,
                "ingles_erros_acumulados": new_ingles,
                "fase": state["fase"],
            }

        return {
            "messages": [],
            "phase_messages": phase_msgs,
            checklist_key: new_checklist,
            notas_key: new_notas,
            "ingles_erros_acumulados": new_ingles,
            "fase": report_fase,
        }

    node.__name__ = f"interview_{phase_name}"
    return node


def _make_report_node(phase_name, next_fase):
    def node(state: EntrevistaState, config: RunnableConfig) -> dict:
        feedback_text = interrupt("[report_ready]")
        # Archive only the distilled report — raw phase messages are discarded
        phase_label = phase_name.replace("_", " ").title()
        summary = f"=== Phase Report: {phase_label} ===\n{feedback_text}"
        new_archive = state.get("archive", []) + [HumanMessage(content=summary)]
        return {
            "messages": [
                AIMessage(content=feedback_text),
                HumanMessage(content="[acknowledged — ready for next phase]"),
            ],
            "phase_messages": [],
            "archive": new_archive,
            "fase": next_fase,
        }

    node.__name__ = f"report_{phase_name}_to_{next_fase}"
    return node


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

elevator_pitch_interview = _make_interview_node(
    ElevatorPitchPhase, "checklist_pitch", "notas_pitch",
    report_fase="elevator_pitch_report", phase_name="elevator_pitch",
)
CAR_interview = _make_interview_node(
    CARPhase, "checklist_CAR", "notas_CAR",
    report_fase="CAR_report", phase_name="CAR",
)
technical_interview = _make_interview_node(
    TechnicalPhase, "checklist_technical", "notas_technical",
    report_fase="technical_report", phase_name="technical",
)
leadership_interview = _make_interview_node(
    LeadershipPhase, "checklist_leadership", "notas_leadership",
    report_fase="leadership_report", phase_name="leadership",
)
motivation_interview = _make_interview_node(
    MotivationPhase, "checklist_motivation", "notas_motivation",
    report_fase="motivation_report", phase_name="motivation",
)

elevator_pitch_report = _make_report_node("elevator_pitch", next_fase="CAR")
CAR_report            = _make_report_node("CAR",            next_fase="technical")
technical_report      = _make_report_node("technical",      next_fase="leadership")
leadership_report     = _make_report_node("leadership",     next_fase="motivation")
motivation_report     = _make_report_node("motivation",     next_fase="candidate_questions")


def candidate_questions(state: EntrevistaState, config: RunnableConfig) -> dict:
    interview_context = state.get("interview_context", "")
    language = state.get("language", "en")
    system_prompt = _build_interview_system(interview_context, "candidate_questions", language)
    structured = get_model(state.get("user_plan", "explorer")).with_structured_output(CandidateQuestionsPhase)

    _cq_opener = "I'm ready to ask my questions."
    phase_msgs: list = state.get("phase_messages") or [
        HumanMessage(content=_cq_opener)
    ]
    messages = [_cached_system(system_prompt)] + phase_msgs
    avaliacao = structured.invoke(messages)

    # Skip detected via structured output
    has_input = any(
        isinstance(m, HumanMessage)
        and m.content != _cq_opener
        and not m.content.startswith("[")
        for m in phase_msgs
    )
    if avaliacao.skip_requested and has_input:
        return {
            "messages": [],
            "phase_messages": [],
            "archive": state.get("archive", []),
            "fase": "feedback",
        }

    if not avaliacao.fase_completa:
        user_response = interrupt(avaliacao.mensagem)
        new_phase_msgs = phase_msgs + [
            AIMessage(content=avaliacao.mensagem),
            HumanMessage(content=user_response),
        ]
        return {
            "messages": [
                AIMessage(content=avaliacao.mensagem),
                HumanMessage(content=user_response),
            ],
            "phase_messages": new_phase_msgs,
            "fase": "candidate_questions",
        }

    name = state.get("candidate_name") or "the candidate"
    language = state.get("language", "en")
    _fallback = (
        f"Obrigado, {name}. Foi uma sessão muito boa. Vou preparar o seu scorecard agora."
        if language == "pt" else
        f"Thank you, {name}. This has been a really strong session. Let me put together your scorecard."
    )
    closing_msg = avaliacao.mensagem if avaliacao.mensagem.strip().lower() != "ok" else _fallback
    # Archive only the closing — raw candidate_questions messages discarded
    new_archive = state.get("archive", [])
    return {
        "messages": [AIMessage(content=closing_msg)],
        "phase_messages": [],
        "archive": new_archive,
        "fase": "feedback",
    }


def feedback(state: EntrevistaState, config: RunnableConfig) -> dict:
    interview_context = state.get("interview_context", "")
    language = state.get("language", "en")
    system_prompt = _build_scorecard_system(interview_context, language)
    structured = get_model(state.get("user_plan", "explorer")).with_structured_output(Scorecard)

    # Build compact context from distilled phase reports + structured notes
    parts = []

    # Phase reports (already distilled — one per phase)
    archive = state.get("archive", [])
    if archive:
        parts.append("## Per-Phase Reports\n")
        for msg in archive:
            parts.append(msg.content)

    # Structured observer notes accumulated during each phase
    note_map = [
        ("Elevator Pitch",        state.get("notas_pitch", "")),
        ("CAR Project Story",     state.get("notas_CAR", "")),
        ("Technical Questions",   state.get("notas_technical", "")),
        ("Leadership",            state.get("notas_leadership", "")),
        ("Fit & Motivation",      state.get("notas_motivation", "")),
    ]
    notes_block = "\n".join(
        f"**{label}:** {note}" for label, note in note_map if note and note.strip()
    )
    if notes_block:
        parts.append("\n## Observer Notes (structured)\n" + notes_block)

    # Checklist summaries
    checklist_map = [
        ("Elevator Pitch",  state.get("checklist_pitch", {})),
        ("CAR",             state.get("checklist_CAR", {})),
        ("Technical",       state.get("checklist_technical", {})),
        ("Leadership",      state.get("checklist_leadership", {})),
        ("Motivation",      state.get("checklist_motivation", {})),
    ]
    checklist_lines = []
    for label, cl in checklist_map:
        if cl:
            passed = [k for k, v in cl.items() if v]
            failed = [k for k, v in cl.items() if not v]
            checklist_lines.append(
                f"**{label}** — ✓ {', '.join(passed) or 'none'} | ✗ {', '.join(failed) or 'none'}"
            )
    if checklist_lines:
        parts.append("\n## Evaluation Checklists\n" + "\n".join(checklist_lines))

    # Accumulated language errors
    ingles_erros = state.get("ingles_erros_acumulados") or []
    if ingles_erros:
        parts.append(
            "\n## Accumulated Language Errors\n"
            + "\n".join(f"- {e}" for e in ingles_erros)
        )

    context_text = "\n".join(parts)
    messages = [_cached_system(system_prompt), HumanMessage(content=context_text)]
    scorecard: Scorecard = _invoke_with_retry(structured, messages)

    job_title = state.get("job_title", "")
    company   = state.get("company", "")
    formatted = _format_scorecard(scorecard, job_title=job_title, company=company, language=language)
    return {
        "messages": [AIMessage(content=formatted)],
        "fase": "done",
    }


# ---------------------------------------------------------------------------
# Scorecard formatter
# ---------------------------------------------------------------------------

_SCORECARD_LABELS = {
    "en": {
        "header": "INTERVIEW SCORECARD",
        "scores_section": "Scores by Section",
        "part1": "Part 1 — Elevator Pitch",
        "part2": "Part 2 — CAR Project Story",
        "part3": "Part 3 — Technical Questions",
        "part4": "Part 4 — Leadership & Approach",
        "part5": "Part 5 — Fit & Motivation",
        "missed_section": "What You Didn't Say (But Should Have)",
        "missed_pitch": "Elevator Pitch:",
        "missed_car": "CAR Project:",
        "missed_tech": "Technical Questions:",
        "missed_lead": "Leadership:",
        "vocab_section": "Vocabulary & Framing to Practice",
        "comm_section": "Overall Communication Performance",
        "rating_label": "Rating:",
        "patterns_label": "Recurring patterns to fix:",
        "assessment_section": "Overall Assessment",
        "total_label": "Total score:",
        "hire_label": "Hire signal:",
        "strengths_label": "Top 2 Strengths",
        "improve_label": "Top 2 Areas to Improve Before the Real Interview",
        "insight_label": "One Thing That Could Make or Break Your Interview",
        "none": "*(none identified)*",
    },
    "pt": {
        "header": "SCORECARD DA ENTREVISTA",
        "scores_section": "Pontuações por Seção",
        "part1": "Parte 1 — Elevator Pitch",
        "part2": "Parte 2 — Projeto CAR",
        "part3": "Parte 3 — Perguntas Técnicas",
        "part4": "Parte 4 — Liderança & Abordagem",
        "part5": "Parte 5 — Fit & Motivação",
        "missed_section": "O Que Você Não Disse (Mas Deveria Ter Dito)",
        "missed_pitch": "Elevator Pitch:",
        "missed_car": "Projeto CAR:",
        "missed_tech": "Perguntas Técnicas:",
        "missed_lead": "Liderança:",
        "vocab_section": "Vocabulário & Enquadramento para Praticar",
        "comm_section": "Desempenho Geral de Comunicação",
        "rating_label": "Avaliação:",
        "patterns_label": "Padrões recorrentes a corrigir:",
        "assessment_section": "Avaliação Geral",
        "total_label": "Pontuação total:",
        "hire_label": "Sinal de contratação:",
        "strengths_label": "Top 2 Pontos Fortes",
        "improve_label": "Top 2 Áreas para Melhorar Antes da Entrevista Real",
        "insight_label": "Uma Coisa Que Pode Definir Sua Entrevista",
        "none": "*(nenhum identificado)*",
    },
}


_HIRE_SIGNAL_TRANSLATIONS = {
    "pt": {
        "Strong Yes": "Contrate agora",
        "Yes":        "Boas chances de contratação",
        "Borderline": "Quase lá",
        "Not Yet":    "Ainda não é sua vez",
    },
}

_HIRE_SIGNAL_PT_REVERSE = {v: k for k, v in _HIRE_SIGNAL_TRANSLATIONS["pt"].items()}


def extract_hire_signal(scorecard_text: str) -> str:
    """Return canonical hire_signal value (English) from stored scorecard markdown."""
    if not scorecard_text:
        return ""
    for line in scorecard_text.splitlines():
        if "Hire signal:" in line or "Sinal de contratação:" in line:
            val = line.split(":", 1)[-1].strip().lstrip("*").rstrip("*").strip()
            return _HIRE_SIGNAL_PT_REVERSE.get(val, val)
    return ""


def _format_scorecard(s: Scorecard, job_title: str = "", company: str = "", language: str = "en") -> str:
    lbl = _SCORECARD_LABELS.get(language, _SCORECARD_LABELS["en"])
    hire_signal = _HIRE_SIGNAL_TRANSLATIONS.get(language, {}).get(s.hire_signal, s.hire_signal)

    def bullets(items: list[str]) -> str:
        return "\n".join(f"- {item}" for item in items) if items else f"- {lbl['none']}"

    def numbered(items: list[str]) -> str:
        return "\n".join(f"{i+1}. {item}" for i, item in enumerate(items)) if items else f"1. {lbl['none']}"

    header = lbl["header"]
    if job_title and company:
        header += f" — {job_title} at {company}"
    elif job_title:
        header += f" — {job_title}"

    lines = [
        f"# 🎯 {header}",
        "",
        "---",
        "",
        f"## 📊 {lbl['scores_section']}",
        "",
        f"**{lbl['part1']}** — {s.score_pitch}/5",
        f"{s.comentario_pitch}",
        "",
        f"**{lbl['part2']}** — {s.score_CAR}/5",
        f"{s.comentario_CAR}",
        "",
        f"**{lbl['part3']}** — {s.score_technical}/5",
        f"{s.comentario_technical}",
        "",
        f"**{lbl['part4']}** — {s.score_leadership}/5",
        f"{s.comentario_leadership}",
        "",
        f"**{lbl['part5']}** — {s.score_motivation}/5",
        f"{s.comentario_motivation}",
        "",
        "---",
        "",
        f"## 💬 {lbl['missed_section']}",
        "",
        f"**{lbl['missed_pitch']}**",
        bullets(s.oportunidades_pitch),
        "",
        f"**{lbl['missed_car']}**",
        bullets(s.oportunidades_CAR),
        "",
        f"**{lbl['missed_tech']}**",
        bullets(s.oportunidades_technical),
        "",
        f"**{lbl['missed_lead']}**",
        bullets(s.oportunidades_leadership),
        "",
        "---",
        "",
        f"## 📝 {lbl['vocab_section']}",
        "",
        bullets(s.vocabulario_para_praticar),
        "",
        "---",
        "",
        f"## 🗣️ {lbl['comm_section']}",
        "",
        f"**{lbl['rating_label']}** {s.ingles_rating}",
        "",
        f"**{lbl['patterns_label']}**",
        numbered(s.ingles_padroes),
        "",
        "---",
        "",
        f"## 🏁 {lbl['assessment_section']}",
        "",
        f"**{lbl['total_label']}** {s.score_total}/25  ",
        f"**{lbl['hire_label']}** {hire_signal}",
        "",
        f"### ✅ {lbl['strengths_label']}",
        numbered(s.forcas),
        "",
        f"### 🔧 {lbl['improve_label']}",
        numbered(s.melhorias),
        "",
        f"### ⚡ {lbl['insight_label']}",
        "",
        f"> {s.insight_chave}",
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Graph — report system prompts exposed for api.py streaming
# ---------------------------------------------------------------------------

# These are built dynamically per-session; api.py calls _build_report_system()
# instead of using static globals. The mapping below tells api.py which phase
# to use for each report node.
REPORT_PHASE_MAP = {
    "elevator_pitch_report": "elevator_pitch",
    "CAR_report":            "CAR",
    "technical_report":      "technical",
    "leadership_report":     "leadership",
    "motivation_report":     "motivation",
}

builder = StateGraph(EntrevistaState)

for name, fn in [
    ("elevator_pitch",        elevator_pitch_interview),
    ("elevator_pitch_report", elevator_pitch_report),
    ("CAR",                   CAR_interview),
    ("CAR_report",            CAR_report),
    ("technical",             technical_interview),
    ("technical_report",      technical_report),
    ("leadership",            leadership_interview),
    ("leadership_report",     leadership_report),
    ("motivation",            motivation_interview),
    ("motivation_report",     motivation_report),
    ("candidate_questions",   candidate_questions),
    ("feedback",              feedback),
]:
    builder.add_node(name, fn)

builder.add_edge(START, "elevator_pitch")

_INTERVIEW_ROUTING = [
    ("elevator_pitch",   {"elevator_pitch": "elevator_pitch", "elevator_pitch_report": "elevator_pitch_report"}),
    ("CAR",              {"CAR": "CAR", "CAR_report": "CAR_report"}),
    ("technical",        {"technical": "technical", "technical_report": "technical_report"}),
    ("leadership",       {"leadership": "leadership", "leadership_report": "leadership_report"}),
    ("motivation",       {"motivation": "motivation", "motivation_report": "motivation_report"}),
    ("candidate_questions", {"candidate_questions": "candidate_questions", "feedback": "feedback"}),
]

for node_name, path_map in _INTERVIEW_ROUTING:
    builder.add_conditional_edges(
        node_name,
        lambda state, _m=path_map: _m.get(state["fase"], END),
        path_map,
    )

builder.add_edge("elevator_pitch_report", "CAR")
builder.add_edge("CAR_report",            "technical")
builder.add_edge("technical_report",      "leadership")
builder.add_edge("leadership_report",     "motivation")
builder.add_edge("motivation_report",     "candidate_questions")
builder.add_edge("feedback",              END)

checkpointer = _Checkpointer()
graph = builder.compile(checkpointer=checkpointer)


# ---------------------------------------------------------------------------
# Initial state factory
# ---------------------------------------------------------------------------

def make_initial_state(
    interview_context: str = "",
    candidate_name: str = "the candidate",
    job_title: str = "",
    company: str = "",
    language: str = "en",
    user_plan: str = "explorer",
) -> EntrevistaState:
    opening = "Olá, estou pronto para começar a entrevista." if language == "pt" else "Hi, I'm ready to start the interview."
    return {
        "messages": [HumanMessage(content=opening)],
        "phase_messages": [HumanMessage(content=opening)],
        "archive": [],
        "fase": "elevator_pitch",
        "language": language,
        "user_plan": user_plan,
        "interview_context": interview_context,
        "candidate_name": candidate_name,
        "job_title": job_title,
        "company": company,
        "checklist_pitch": {
            "personal_intro_clear": False,
            "background_framed_as_asset": False,
            "key_achievement_mentioned": False,
            "career_narrative_coherent": False,
            "current_role_in_business_terms": False,
            "closes_with_differentiator": False,
            "english_adequate": False,
        },
        "checklist_CAR": {
            "business_context_clear": False,
            "problem_stated_clearly": False,
            "personal_ownership": False,
            "specific_actions": False,
            "deliberate_choices": False,
            "result_in_business_terms": False,
            "production_mindset": False,
            "english_adequate": False,
        },
        "checklist_technical": {
            "q1_answered": False,
            "q2_answered": False,
            "q3_answered": False,
            "answers_show_depth": False,
            "production_mindset": False,
            "english_adequate": False,
        },
        "checklist_leadership": {
            "starts_with_situation_assessment": False,
            "identifies_primary_risk": False,
            "execution_realism": False,
            "concrete_mitigation_plan": False,
            "stakeholder_management": False,
            "connects_to_real_experience": False,
            "english_adequate": False,
        },
        "checklist_motivation": {
            "specific_company_knowledge": False,
            "genuine_connection": False,
            "unique_fit": False,
            "authentic_tone": False,
            "english_adequate": False,
        },
        "notas_pitch": "",
        "notas_CAR": "",
        "notas_technical": "",
        "notas_leadership": "",
        "notas_motivation": "",
        "ingles_erros_acumulados": [],
    }
