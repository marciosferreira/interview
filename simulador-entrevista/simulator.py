import os
import time
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

_database_url = os.getenv("DATABASE_URL")

if _database_url:
    # ── PostgreSQL (produção) ──────────────────────────────────────────────────
    try:
        import psycopg2 as _psycopg2
        from langgraph.checkpoint.memory import MemorySaver as _MemorySaver
        _conn = _psycopg2.connect(
            _database_url,
            connect_timeout=5,
            options="-c lock_timeout=5000 -c statement_timeout=30000",
        )
        _conn.autocommit = True          # DDL sem transações pendentes
        # LangGraph não tem checkpointer nativo para psycopg2 síncrono;
        # usa MemorySaver para o grafo e psycopg2 para as tabelas de negócio.
        _Checkpointer = _MemorySaver
    except Exception as _e:
        print(f"[warn] Falha ao conectar no PostgreSQL: {_e} — usando MemorySaver")
        _conn = None
        from langgraph.checkpoint.memory import MemorySaver as _MemorySaver
        _Checkpointer = _MemorySaver
else:
    # ── SQLite (dev local sem DATABASE_URL) ───────────────────────────────────
    try:
        import sqlite3 as _sqlite3
        from langgraph.checkpoint.sqlite import SqliteSaver as _SqliteSaver
        _db_path = str(Path(__file__).parent / "sessions.db")
        _conn = _sqlite3.connect(_db_path, check_same_thread=False)
        _saver = _SqliteSaver(_conn)
        _saver.setup()
        _Checkpointer = lambda: _saver  # noqa: E731
    except Exception:
        _conn = None
        from langgraph.checkpoint.memory import MemorySaver as _MemorySaver
        _Checkpointer = _MemorySaver


# ── Session store ─────────────────────────────────────────────────────────────

class SessionStore:
    """Stores chat history + metadata for the dashboard page.
    Backed by sessions.db (SQLite) or PostgreSQL; falls back to in-memory dict if unavailable.
    """

    def __init__(self, conn):
        self._conn = conn
        # Detecta se é psycopg2 (Postgres) ou sqlite3 para escolher placeholder correto
        self._is_pg = conn is not None and hasattr(conn, 'server_version')
        ph = "%s" if self._is_pg else "?"  # placeholder
        if conn:
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
                # Migration com IF NOT EXISTS (Postgres)
                for col, defn in [
                    ("user_id",        "TEXT"),
                    ("job_session_id", "TEXT"),
                    ("scorecard_text", "TEXT"),
                ]:
                    cur.execute(f"ALTER TABLE session_meta ADD COLUMN IF NOT EXISTS {col} {defn}")
                cur.close()
                conn.commit()
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
                # Migration para SQLite (sem IF NOT EXISTS no ALTER TABLE)
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
            self._mem: dict = {}

    def _exec(self, sql: str, params=()):
        """Executa uma query e retorna o cursor (psycopg2) ou resultado direto (sqlite3)."""
        if self._is_pg:
            cur = self._conn.cursor()
            cur.execute(sql, params)
            return cur
        else:
            return self._conn.execute(sql, params)

    def upsert(self, thread_id: str, started_at: int, last_active_at: int,
               fase: str, history: list,
               user_id: Optional[str] = None, job_session_id: Optional[str] = None) -> None:
        if self._conn:
            ph = "%s" if self._is_pg else "?"
            sql = f"""INSERT INTO session_meta
                       (thread_id, user_id, job_session_id, started_at, last_active_at, fase, history)
                   VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
                   ON CONFLICT(thread_id) DO UPDATE SET
                       last_active_at = excluded.last_active_at,
                       fase           = excluded.fase,
                       history        = excluded.history"""
            cur = self._exec(sql, (thread_id, user_id, job_session_id, started_at, last_active_at,
                                   fase, _json.dumps(history)))
            if self._is_pg:
                cur.close()
            self._conn.commit()
        else:
            self._mem[thread_id] = dict(
                threadId=thread_id, userId=user_id, jobSessionId=job_session_id,
                startedAt=started_at, lastActiveAt=last_active_at, fase=fase, history=history,
            )

    def list_sessions(self, user_id: Optional[str] = None, limit: int = 20) -> list:
        if self._conn:
            ph = "%s" if self._is_pg else "?"
            if user_id:
                sql = f"""SELECT sm.thread_id, sm.user_id, sm.job_session_id,
                              sm.started_at, sm.last_active_at, sm.fase, sm.history,
                              js.job_title, js.company
                       FROM session_meta sm
                       LEFT JOIN job_sessions js ON sm.job_session_id = js.id
                       WHERE sm.user_id = {ph}
                       ORDER BY sm.last_active_at DESC LIMIT {ph}"""
                cur = self._exec(sql, (user_id, limit))
            else:
                sql = f"""SELECT sm.thread_id, sm.user_id, sm.job_session_id,
                              sm.started_at, sm.last_active_at, sm.fase, sm.history,
                              js.job_title, js.company
                       FROM session_meta sm
                       LEFT JOIN job_sessions js ON sm.job_session_id = js.id
                       ORDER BY sm.last_active_at DESC LIMIT {ph}"""
                cur = self._exec(sql, (limit,))
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
                }
                for r in rows
            ]
        else:
            sessions = list(self._mem.values())
            if user_id:
                sessions = [s for s in sessions if s.get("userId") == user_id]
            return sorted(sessions, key=lambda s: s["lastActiveAt"], reverse=True)[:limit]

    def delete(self, thread_id: str, user_id: Optional[str] = None) -> None:
        if self._conn:
            ph = "%s" if self._is_pg else "?"
            if user_id:
                cur = self._exec(
                    f"DELETE FROM session_meta WHERE thread_id = {ph} AND user_id = {ph}",
                    (thread_id, user_id),
                )
            else:
                cur = self._exec(
                    f"DELETE FROM session_meta WHERE thread_id = {ph}", (thread_id,)
                )
            if self._is_pg:
                cur.close()
            self._conn.commit()
        else:
            self._mem.pop(thread_id, None)

    def save_scorecard(self, thread_id: str, user_id: str, scorecard_text: str) -> None:
        if self._conn:
            ph = "%s" if self._is_pg else "?"
            cur = self._exec(
                f"UPDATE session_meta SET scorecard_text = {ph} WHERE thread_id = {ph} AND user_id = {ph}",
                (scorecard_text, thread_id, user_id),
            )
            if self._is_pg:
                cur.close()
            self._conn.commit()

    def get_scorecard(self, thread_id: str, user_id: str) -> Optional[str]:
        if self._conn:
            ph = "%s" if self._is_pg else "?"
            cur = self._exec(
                f"SELECT scorecard_text FROM session_meta WHERE thread_id = {ph} AND user_id = {ph}",
                (thread_id, user_id),
            )
            row = cur.fetchone()
            if self._is_pg:
                cur.close()
            return row[0] if row else None
        return None


session_store = SessionStore(_conn)

# ── Setup auth tables ─────────────────────────────────────────────────────────
# Done here so _conn is shared across auth.py and simulator.py without circular imports.
if _conn:
    from auth import setup_user_tables
    setup_user_tables(_conn)

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

model = ChatAnthropic(
    model=os.getenv("MODEL_NAME", "claude-sonnet-4-6"),
    api_key=os.getenv("ANTHROPIC_API_KEY"),
)

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


def _build_interview_system(interview_context: str, phase: str, language: str = "en") -> str:
    """Compose: persona + candidate context + phase guide."""
    phase_guide = _PHASE_FILES.get(phase, "")
    lang_block = "\n\n---\n\n" + _LANG_DIRECTIVE.get(language, _LANG_DIRECTIVE["en"])
    context_block = (
        "\n\n---\n\n## CANDIDATE & JOB CONTEXT\n\n"
        + interview_context
        + "\n\n---\n\n"
    ) if interview_context else "\n\n---\n\n"
    return _PERSONA + lang_block + context_block + phase_guide


_REPORT_PHASE_SECTIONS = {
    "elevator_pitch": "# ELEVATOR PITCH GUIDANCE",
    "CAR":            "# CAR PROJECT GUIDANCE",
    "technical":      "# TECHNICAL EVALUATION FOCUS",
    "leadership":     "# LEADERSHIP & APPROACH EVALUATION",
    "motivation":     "# FIT & MOTIVATION EVALUATION",
}

_ALWAYS_INCLUDE_SECTIONS = {"# CANDIDATE PROFILE", "# LANGUAGE & COMMUNICATION NOTES"}


def _extract_context_for_report(interview_context: str, phase: str) -> str:
    """Return only the sections of interview_context relevant to this phase's report."""
    if not interview_context:
        return ""
    phase_section = _REPORT_PHASE_SECTIONS.get(phase, "")
    keep = _ALWAYS_INCLUDE_SECTIONS | ({phase_section} if phase_section else set())

    # Split on markdown H1 headings
    import re
    parts = re.split(r'(?=^# )', interview_context, flags=re.MULTILINE)
    selected = []
    for part in parts:
        heading = part.split('\n', 1)[0].strip()
        if not heading or any(heading.startswith(h) for h in keep):
            selected.append(part)
    return "\n\n".join(selected).strip()


def _build_report_system(interview_context: str, phase: str, language: str = "en") -> str:
    """Compose: report format + phase-relevant context slice + phase guide."""
    phase_guide = _PHASE_FILES.get(phase, "")
    slim_context = _extract_context_for_report(interview_context, phase)
    lang_block = "\n\n---\n\n" + _LANG_DIRECTIVE.get(language, _LANG_DIRECTIVE["en"])
    context_block = (
        "\n\n---\n\n## CANDIDATE & JOB CONTEXT\n\n"
        + slim_context
        + "\n\n---\n\n"
    ) if slim_context else "\n\n---\n\n"
    return _REPORT_BASE + lang_block + context_block + phase_guide


def _build_scorecard_system(interview_context: str, language: str = "en") -> str:
    lang_block = "\n\n---\n\n" + _LANG_DIRECTIVE.get(language, _LANG_DIRECTIVE["en"])
    context_block = (
        "\n\n---\n\n## CANDIDATE & JOB CONTEXT\n\n"
        + interview_context
        + "\n\n---\n\n"
    ) if interview_context else "\n\n---\n\n"
    return _SCORECARD + lang_block + context_block


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
        "**Language:** Conduct the entire interview in English. "
        "All your messages must be in English."
    ),
    "pt": (
        "**Idioma:** Conduza toda a entrevista em Português do Brasil. "
        "Todas as suas mensagens devem estar em Português do Brasil. "
        "O campo `english_adequate` deve avaliar a qualidade da comunicação em Português do candidato."
    ),
}


class EntrevistaState(TypedDict):
    messages:       Annotated[list, add_messages]
    phase_messages: list
    archive:        list
    fase:           str
    language:       str      # user's preferred language ("en" or "pt")
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
        "(3) Coaching after 2+ failed attempts: a brief hint followed by "
            "'take another attempt or say skip to move on'. "
        "(4) When fase_completa=True: set this to exactly the string 'OK' and nothing else. "
        "NEVER include feedback, scoring, report content, or a summary of how the candidate did. "
        "The Judge handles all feedback after the phase ends — Alex never delivers it."
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
    observacoes: str
    ingles_erros: StrList


class LeadershipPhase(BaseModel):
    starts_with_data_assessment: bool
    identifies_primary_risk: bool
    pilot_to_production_awareness: bool
    concrete_mitigation_plan: bool
    stakeholder_management: bool
    connects_to_real_experience: bool
    english_adequate: bool
    mensagem: str = _MENSAGEM_FIELD
    fase_completa: bool
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
    observacoes: str
    ingles_erros: StrList


class CandidateQuestionsPhase(BaseModel):
    mensagem: str
    fase_completa: bool
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

def _make_interview_node(output_class, checklist_key, notas_key, report_fase, phase_name):
    def node(state: EntrevistaState, config: RunnableConfig) -> dict:
        interview_context = state.get("interview_context", "")
        language = state.get("language", "en")
        system_prompt = _build_interview_system(interview_context, phase_name, language)
        structured = model.with_structured_output(output_class)

        phase_msgs: list = state.get("phase_messages") or [
            HumanMessage(content="I'm ready to start this phase.")
        ]
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

            if user_response.strip().lower() in ("skip", "s"):
                return {
                    "messages": [],
                    "phase_messages": phase_msgs + [
                        AIMessage(content=avaliacao.mensagem),
                        HumanMessage(content="[Candidate skipped — phase incomplete]"),
                    ],
                    checklist_key: new_checklist,
                    notas_key: new_notas,
                    "ingles_erros_acumulados": new_ingles,
                    "fase": report_fase,
                }

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
    structured = model.with_structured_output(CandidateQuestionsPhase)

    phase_msgs: list = state.get("phase_messages") or [
        HumanMessage(content="I'm ready to ask my questions.")
    ]
    messages = [_cached_system(system_prompt)] + phase_msgs
    avaliacao = structured.invoke(messages)

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
    closing_msg = avaliacao.mensagem if avaliacao.mensagem.strip().lower() != "ok" else (
        f"Thank you, {name}. This has been a really strong session. "
        "Let me put together your scorecard."
    )
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
    structured = model.with_structured_output(Scorecard)

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
    formatted = _format_scorecard(scorecard, job_title=job_title, company=company)
    return {
        "messages": [AIMessage(content=formatted)],
        "fase": "done",
    }


# ---------------------------------------------------------------------------
# Scorecard formatter
# ---------------------------------------------------------------------------

def _format_scorecard(s: Scorecard, job_title: str = "", company: str = "") -> str:
    def bullets(items: list[str]) -> str:
        return "\n".join(f"  - {item}" for item in items) if items else "  (none identified)"

    def numbered(items: list[str]) -> str:
        return "\n".join(f"  {i+1}. {item}" for i, item in enumerate(items)) if items else "  (none identified)"

    header = f"INTERVIEW SCORECARD"
    if job_title and company:
        header += f" — {job_title} at {company}"
    elif job_title:
        header += f" — {job_title}"

    return "\n".join([
        "",
        "============================================",
        f"🎯 {header}",
        "============================================",
        "",
        "PART 1 — Elevator Pitch",
        f"Score: {s.score_pitch}/5 | {s.comentario_pitch}",
        "",
        "PART 2 — CAR Project Story",
        f"Score: {s.score_CAR}/5 | {s.comentario_CAR}",
        "",
        "PART 3 — Technical Questions",
        f"Score: {s.score_technical}/5 | {s.comentario_technical}",
        "",
        "PART 4 — Leadership & Project Approach",
        f"Score: {s.score_leadership}/5 | {s.comentario_leadership}",
        "",
        "PART 5 — Fit & Motivation",
        f"Score: {s.score_motivation}/5 | {s.comentario_motivation}",
        "",
        "--------------------------------------------",
        "WHAT YOU DIDN'T SAY (BUT SHOULD HAVE)",
        "",
        "Elevator Pitch:",
        bullets(s.oportunidades_pitch),
        "",
        "CAR Project:",
        bullets(s.oportunidades_CAR),
        "",
        "Technical Questions:",
        bullets(s.oportunidades_technical),
        "",
        "Leadership:",
        bullets(s.oportunidades_leadership),
        "",
        "--------------------------------------------",
        "VOCABULARY & FRAMING TO PRACTICE",
        "",
        bullets(s.vocabulario_para_praticar),
        "",
        "--------------------------------------------",
        "OVERALL COMMUNICATION PERFORMANCE",
        f"Rating: {s.ingles_rating}",
        "Recurring patterns to fix:",
        numbered(s.ingles_padroes),
        "",
        "--------------------------------------------",
        "OVERALL ASSESSMENT",
        f"Total score: {s.score_total}/25",
        f"Hire signal: {s.hire_signal}",
        "",
        "TOP 2 STRENGTHS:",
        numbered(s.forcas),
        "",
        "TOP 2 AREAS TO IMPROVE BEFORE THE REAL INTERVIEW:",
        numbered(s.melhorias),
        "",
        "ONE THING THAT COULD MAKE OR BREAK YOUR INTERVIEW:",
        f"  {s.insight_chave}",
        "============================================",
    ])


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
) -> EntrevistaState:
    opening = "Olá, estou pronto para começar a entrevista." if language == "pt" else "Hi, I'm ready to start the interview."
    return {
        "messages": [HumanMessage(content=opening)],
        "phase_messages": [HumanMessage(content=opening)],
        "archive": [],
        "fase": "elevator_pitch",
        "language": language,
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
            "starts_with_data_assessment": False,
            "identifies_primary_risk": False,
            "pilot_to_production_awareness": False,
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
