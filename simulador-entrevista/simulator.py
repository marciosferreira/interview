import os
from pathlib import Path
from typing import Annotated
from typing_extensions import TypedDict

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
import json as _json

try:
    import sqlite3 as _sqlite3
    from langgraph.checkpoint.sqlite import SqliteSaver as _SqliteSaver
    _db_path = str(Path(__file__).parent / "sessions.db")
    _conn = _sqlite3.connect(_db_path, check_same_thread=False)
    _saver = _SqliteSaver(_conn)
    _saver.setup()   # creates checkpoint tables if they don't exist yet
    _Checkpointer = lambda: _saver   # noqa: E731
except Exception:
    _conn = None
    from langgraph.checkpoint.memory import MemorySaver as _MemorySaver
    _Checkpointer = _MemorySaver


class SessionStore:
    """Stores chat history + metadata for the history page.
    Backed by the same sessions.db used for LangGraph checkpoints.
    Falls back to an in-memory dict if SQLite is unavailable.
    """

    def __init__(self, conn):
        self._conn = conn
        if conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS session_meta (
                    thread_id      TEXT PRIMARY KEY,
                    started_at     INTEGER NOT NULL,
                    last_active_at INTEGER NOT NULL,
                    fase           TEXT    NOT NULL DEFAULT '',
                    history        TEXT    NOT NULL DEFAULT '[]'
                )
            """)
            conn.commit()
        else:
            self._mem: dict = {}

    def upsert(self, thread_id: str, started_at: int, last_active_at: int,
               fase: str, history: list) -> None:
        if self._conn:
            self._conn.execute(
                """INSERT INTO session_meta (thread_id, started_at, last_active_at, fase, history)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(thread_id) DO UPDATE SET
                       last_active_at = excluded.last_active_at,
                       fase           = excluded.fase,
                       history        = excluded.history""",
                (thread_id, started_at, last_active_at, fase, _json.dumps(history)),
            )
            self._conn.commit()
        else:
            self._mem[thread_id] = dict(
                threadId=thread_id, startedAt=started_at,
                lastActiveAt=last_active_at, fase=fase, history=history,
            )

    def list_sessions(self, limit: int = 10) -> list:
        if self._conn:
            rows = self._conn.execute(
                """SELECT thread_id, started_at, last_active_at, fase, history
                   FROM session_meta
                   ORDER BY last_active_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()
            return [
                {
                    "threadId":      r[0],
                    "startedAt":     r[1],
                    "lastActiveAt":  r[2],
                    "fase":          r[3],
                    "history":       _json.loads(r[4]),
                }
                for r in rows
            ]
        else:
            return sorted(self._mem.values(),
                          key=lambda s: s["lastActiveAt"], reverse=True)[:limit]

    def delete(self, thread_id: str) -> None:
        if self._conn:
            self._conn.execute(
                "DELETE FROM session_meta WHERE thread_id = ?", (thread_id,)
            )
            self._conn.commit()
        else:
            self._mem.pop(thread_id, None)


session_store = SessionStore(_conn)
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.types import interrupt, Command
from pydantic import BaseModel, BeforeValidator, Field

load_dotenv()


def _coerce_list(v):
    """Accept list[str] or a JSON-encoded string of a list (model sometimes returns the latter)."""
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


# Type alias: list[str] that tolerates a JSON-string from the LLM
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
    """Concatenate one or more .md prompt files into a single system prompt."""
    parts = []
    for name in filenames:
        path = PROMPTS_DIR / name
        parts.append(path.read_text(encoding="utf-8"))
    return "\n\n---\n\n".join(parts)


# Interview system prompts — conduct the interview, ask follow-ups, coach
SYSTEM_PITCH_INTERVIEW       = load_prompt("persona_interview.md", "context_marcio.md", "elevator_pitch.md")
SYSTEM_CAR_INTERVIEW         = load_prompt("persona_interview.md", "context_marcio.md", "car.md")
SYSTEM_TECHNICAL_INTERVIEW   = load_prompt("persona_interview.md", "context_marcio.md", "technical.md")
SYSTEM_LEADERSHIP_INTERVIEW  = load_prompt("persona_interview.md", "context_marcio.md", "leadership.md")
SYSTEM_MOTIVATION_INTERVIEW  = load_prompt("persona_interview.md", "context_marcio.md", "motivation.md")

# Report system prompts — generate the structured feedback block after phase completion
SYSTEM_PITCH_REPORT          = load_prompt("report_format.md", "context_marcio.md", "elevator_pitch.md")
SYSTEM_CAR_REPORT            = load_prompt("report_format.md", "context_marcio.md", "car.md")
SYSTEM_TECHNICAL_REPORT      = load_prompt("report_format.md", "context_marcio.md", "technical.md")
SYSTEM_LEADERSHIP_REPORT     = load_prompt("report_format.md", "context_marcio.md", "leadership.md")
SYSTEM_MOTIVATION_REPORT     = load_prompt("report_format.md", "context_marcio.md", "motivation.md")

# Other phases
SYSTEM_MARCIO_Q  = load_prompt("persona_interview.md", "marcio_questions.md")
SYSTEM_SCORECARD = load_prompt("context_marcio.md", "scorecard.md")

# Aliases for api.py streaming (interview nodes only)
SYSTEM_PITCH      = SYSTEM_PITCH_INTERVIEW
SYSTEM_CAR        = SYSTEM_CAR_INTERVIEW
SYSTEM_TECHNICAL  = SYSTEM_TECHNICAL_INTERVIEW
SYSTEM_LEADERSHIP = SYSTEM_LEADERSHIP_INTERVIEW
SYSTEM_MOTIVATION = SYSTEM_MOTIVATION_INTERVIEW
SYSTEM_MARCIO_Q   = SYSTEM_MARCIO_Q


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

class EntrevistaState(TypedDict):
    messages: Annotated[list, add_messages]  # full history (LangGraph checkpointing)
    phase_messages: list   # current-phase transcript — preserved until report node reads it
    archive: list          # completed phases transcript — fed to scorecard at the end
    fase: str              # current phase name

    checklist_pitch: dict
    checklist_CAR: dict
    checklist_technical: dict
    checklist_leadership: dict
    checklist_motivation: dict

    notas_pitch: str
    notas_CAR: str
    notas_technical: str
    notas_leadership: str
    notas_motivation: str

    ingles_erros_acumulados: list


# ---------------------------------------------------------------------------
# Lean interview Pydantic models (no feedback fields — report node handles those)
# ---------------------------------------------------------------------------

# Shared Field descriptor for the `mensagem` field in all interview Pydantic models.
# Rule (3) from previous versions ("deliver the Judge's feedback block") has been
# removed — that caused the LLM to put report content into Maria's message.
# The Judge streams the report separately; Maria's mensagem is ONLY a question or
# short coaching nudge, never feedback, never a summary.
_MENSAGEM_FIELD = Field(
    description=(
        "Maria Ximena's next spoken line — a question or short coaching nudge only. "
        "(1) Opening turn: reproduce the exact greeting from the phase prompt verbatim. "
        "(2) Ongoing interview: one follow-up question or coaching prompt, 1–3 sentences max. "
        "(3) Coaching after 2+ failed attempts: a brief hint followed by "
            "'take another attempt or say skip to move on'. "
        "(4) When fase_completa=True: set this to exactly the string 'OK' and nothing else. "
        "NEVER include feedback, scoring, report content, or a summary of how the candidate did. "
        "The Judge handles all feedback after the phase ends — Maria never delivers it."
    )
)


class PitchInterview(BaseModel):
    apresentacao_pessoal: bool    # item 1: name + current role introduced
    phd_como_forca: bool          # item 2: PhD framed as cognitive asset (not just credential)
    pesquisa_internacional: bool  # item 3: international research (EMBL-EBI / Tulane)
    software_cv: bool             # item 4: first-author software with AI/CV referenced
    transicao_industria: bool     # item 5: transition framed as evolution, not gap
    venturus_milestone: bool      # item 6: Venturus framed as entry point into production AI
    trabalho_atual_negocio: bool  # item 7: current work in business terms (no stack names)
    closing_demo_producao: bool   # item 8: demo-to-production gap framing (NON-NEGOTIABLE)
    sem_stack_names: bool         # item 9: no technical stack names used
    sem_metricas: bool            # item 10: no specific metrics or percentages
    ingles_adequado: bool         # item 11: English mostly fluent and natural
    mensagem: str = _MENSAGEM_FIELD
    fase_completa: bool
    observacoes: str
    ingles_erros: StrList


class CARInterview(BaseModel):
    contexto_negocio: bool        # item 1: business context clear (manufacturing, account managers)
    problema_negocio: bool        # item 2: problem stated in business terms (not technical framing)
    acoes_pessoais: bool          # item 3: personal ownership — uses "I", not "we"
    langfuse_observability: bool  # item 4: Langfuse as deliberate decision from day one
    token_optimization: bool      # item 5: token problem + multi-technique fix + validation
    resultado_negocio: bool       # item 6: result in business impact terms
    production_mindset: bool      # item 7: proactive production thinking (NON-NEGOTIABLE)
    ingles_adequado: bool         # item 8: English mostly fluent and natural
    mensagem: str = _MENSAGEM_FIELD
    fase_completa: bool
    observacoes: str
    ingles_erros: StrList


class TechnicalInterview(BaseModel):
    q1_monitoring: bool
    q2_degradacao: bool
    q3_rag: bool
    producao_mindset: bool
    ingles_adequado: bool
    mensagem: str = _MENSAGEM_FIELD
    fase_completa: bool
    observacoes: str
    ingles_erros: StrList


class LeadershipInterview(BaseModel):
    data_audit: bool               # item 1: data audit before any model code
    data_como_risco_primario: bool # item 2: data framed as primary project risk
    pilot_producao_gap: bool       # item 3: pilot-to-production gap named as known risk
    mitigacao_concreta: bool       # item 4: concrete mitigation (observability, cost modeling, exit criteria)
    stakeholder_mgmt: bool         # item 5: stakeholder management proactive, not reactive
    data_point_usado: bool         # item 6: industry data point used naturally
    experiencia_real: bool         # item 7: connects to real experience (Iris Hub / Venturus)
    ingles_adequado: bool          # item 8: English mostly fluent and natural
    mensagem: str = _MENSAGEM_FIELD
    fase_completa: bool
    observacoes: str
    ingles_erros: StrList


class MotivationInterview(BaseModel):
    especifico_factored: bool              # item 1: references 2+ Factored attributes with understanding
    conexao_real: bool                     # item 2: draws explicit line between background and Factored
    nao_pode_obter_em_outro_lugar: bool    # item 3: names what he can't get in current role
    tom_genuino: bool                      # item 4: tone feels genuine, not rehearsed
    ingles_adequado: bool                  # item 5: English mostly fluent and natural
    mensagem: str = _MENSAGEM_FIELD
    fase_completa: bool
    observacoes: str
    ingles_erros: StrList


class AvaliacaoMarcioQuestions(BaseModel):
    mensagem: str
    fase_completa: bool
    observacoes: str


class Scorecard(BaseModel):
    score_pitch: int
    comentario_pitch: str
    score_CAR: int
    comentario_CAR: str
    score_technical: int
    comentario_technical: str
    score_leadership: int
    comentario_leadership: str
    score_motivation: int
    comentario_motivation: str
    oportunidades_pitch: StrList
    oportunidades_CAR: StrList
    oportunidades_technical: StrList
    oportunidades_leadership: StrList
    vocabulario_para_praticar: StrList
    ingles_rating: str
    ingles_padroes: StrList
    score_total: int
    hire_signal: str
    forcas: StrList
    melhorias: StrList
    insight_chave: str


# ---------------------------------------------------------------------------
# Node factories
# ---------------------------------------------------------------------------

def _make_interview_node(system_prompt, output_class, checklist_key, notas_key, report_fase):
    """
    Interview node: asks questions, coaches, loops until quality gate met.
    When complete, advances to the corresponding report node — no feedback generated here.
    """
    def node(state: EntrevistaState) -> dict:
        structured = model.with_structured_output(output_class)

        phase_msgs: list = state.get("phase_messages") or [
            HumanMessage(content="I'm ready to start this phase.")
        ]
        messages = [SystemMessage(content=system_prompt)] + phase_msgs
        avaliacao = structured.invoke(messages)

        # Merge checklist — fields already True stay True
        old_checklist = state[checklist_key]
        new_checklist = {
            k: old_checklist.get(k, False) or getattr(avaliacao, k, False)
            for k in old_checklist
        }

        old_notas = state[notas_key]
        new_notas = (old_notas + "\n" + avaliacao.observacoes).strip() if avaliacao.observacoes else old_notas

        old_ingles = state.get("ingles_erros_acumulados", [])
        new_ingles = old_ingles + (avaliacao.ingles_erros or [])

        # Safety guard: if the LLM returned mensagem="OK" but forgot to set
        # fase_completa=True, treat it as complete — avoids the graph getting
        # stuck waiting for user input with a bare "OK" as the question.
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

            # Skip bypass: advance directly to the report without a second LLM call.
            # When LangGraph resumes with "skip", interrupt() returns that value here.
            # Returning report_fase immediately avoids the extra structured-output call
            # that would otherwise be needed to re-evaluate the gate with "skip" in context.
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
                    "fase": report_fase,  # go straight to report, no second LLM call
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
                "fase": state["fase"],  # stay in interview phase
            }

        # Quality gate met — route to report node.
        # phase_messages is preserved intact for the report node to read.
        return {
            "messages": [],
            "phase_messages": phase_msgs,
            checklist_key: new_checklist,
            notas_key: new_notas,
            "ingles_erros_acumulados": new_ingles,
            "fase": report_fase,
        }

    node.__name__ = f"interview_{checklist_key}"
    return node


def _make_report_node(system_prompt, next_fase):
    """
    Report node: pauses via interrupt so api.py can stream the report with model.astream().
    api.py resumes with the full text; this node archives it and advances.
    This keeps report generation fast (streaming) without double-calling the LLM.
    """
    def node(state: EntrevistaState) -> dict:
        phase_msgs: list = state.get("phase_messages") or []

        # Interrupt here — api.py will stream the report using model.astream() and
        # resume with the complete text.  We use "[report_ready]" as the signal so
        # api.py can distinguish this from a regular interview-phase interrupt.
        feedback_text = interrupt("[report_ready]")

        new_archive = state.get("archive", []) + phase_msgs + [AIMessage(content=feedback_text)]

        return {
            "messages": [
                AIMessage(content=feedback_text),
                HumanMessage(content="[acknowledged — ready for next phase]"),
            ],
            "phase_messages": [],   # fresh slate for next interview node
            "archive": new_archive,
            "fase": next_fase,
        }

    node.__name__ = f"report_to_{next_fase}"
    return node


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

# Interview nodes
elevator_pitch_interview = _make_interview_node(
    SYSTEM_PITCH_INTERVIEW, PitchInterview,
    checklist_key="checklist_pitch", notas_key="notas_pitch",
    report_fase="elevator_pitch_report",
)

CAR_interview = _make_interview_node(
    SYSTEM_CAR_INTERVIEW, CARInterview,
    checklist_key="checklist_CAR", notas_key="notas_CAR",
    report_fase="CAR_report",
)

technical_interview = _make_interview_node(
    SYSTEM_TECHNICAL_INTERVIEW, TechnicalInterview,
    checklist_key="checklist_technical", notas_key="notas_technical",
    report_fase="technical_report",
)

leadership_interview = _make_interview_node(
    SYSTEM_LEADERSHIP_INTERVIEW, LeadershipInterview,
    checklist_key="checklist_leadership", notas_key="notas_leadership",
    report_fase="leadership_report",
)

motivation_interview = _make_interview_node(
    SYSTEM_MOTIVATION_INTERVIEW, MotivationInterview,
    checklist_key="checklist_motivation", notas_key="notas_motivation",
    report_fase="motivation_report",
)

# Report nodes
elevator_pitch_report = _make_report_node(SYSTEM_PITCH_REPORT,      next_fase="CAR")
CAR_report            = _make_report_node(SYSTEM_CAR_REPORT,         next_fase="technical")
technical_report      = _make_report_node(SYSTEM_TECHNICAL_REPORT,   next_fase="leadership")
leadership_report     = _make_report_node(SYSTEM_LEADERSHIP_REPORT,  next_fase="motivation")
motivation_report     = _make_report_node(SYSTEM_MOTIVATION_REPORT,  next_fase="marcio_questions")


def marcio_questions(state: EntrevistaState) -> dict:
    structured = model.with_structured_output(AvaliacaoMarcioQuestions)
    phase_msgs: list = state.get("phase_messages") or [
        HumanMessage(content="I'm ready to start this phase.")
    ]
    messages = [SystemMessage(content=SYSTEM_MARCIO_Q)] + phase_msgs
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
            "fase": "marcio_questions",
        }

    # Phase complete — archive transcript, advance to scorecard.
    # Only show the closing message if it's meaningful (not a bare "OK" from skip).
    closing_msg = avaliacao.mensagem if avaliacao.mensagem.strip().lower() != "ok" else (
        "Thank you, Marcio. This has been a really good session. "
        "Let me put together your scorecard."
    )
    completed_transcript = phase_msgs + [AIMessage(content=closing_msg)]
    new_archive = state.get("archive", []) + completed_transcript
    return {
        "messages": [AIMessage(content=closing_msg)],
        "phase_messages": [],
        "archive": new_archive,
        "fase": "feedback",
    }


def feedback(state: EntrevistaState) -> dict:
    structured = model.with_structured_output(Scorecard)
    archive = state.get("archive", [])
    phase_msgs = state.get("phase_messages") or []
    full_context = archive + phase_msgs

    # Inject the accumulated English error list as an explicit context message
    # so the scorecard LLM can consolidate patterns across all phases.
    ingles_erros = state.get("ingles_erros_acumulados") or []
    if ingles_erros:
        erros_text = (
            "ACCUMULATED ENGLISH ERRORS — collected across all interview phases:\n"
            + "\n".join(f"- {e}" for e in ingles_erros)
        )
        full_context = full_context + [HumanMessage(content=erros_text)]

    messages = [SystemMessage(content=SYSTEM_SCORECARD)] + full_context
    scorecard: Scorecard = structured.invoke(messages)

    formatted = _format_scorecard(scorecard)
    return {
        "messages": [AIMessage(content=formatted)],
        "fase": "done",
    }


# ---------------------------------------------------------------------------
# Scorecard formatter
# ---------------------------------------------------------------------------

def _format_scorecard(s: Scorecard) -> str:
    def bullets(items: list[str]) -> str:
        return "\n".join(f"  - {item}" for item in items) if items else "  (none identified)"

    def numbered(items: list[str]) -> str:
        return "\n".join(f"  {i+1}. {item}" for i, item in enumerate(items)) if items else "  (none identified)"

    return "\n".join([
        "",
        "============================================",
        "🎯 INTERVIEW SCORECARD — Factored AI Residency",
        "============================================",
        "",
        "PART 1 — Elevator Pitch",
        f"Score: {s.score_pitch}/5 | {s.comentario_pitch}",
        "",
        "PART 2 — CAR Project",
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
        "OVERALL ENGLISH PERFORMANCE",
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
# Graph
# ---------------------------------------------------------------------------

builder = StateGraph(EntrevistaState)

# Register all nodes
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
    ("marcio_questions",      marcio_questions),
    ("feedback",              feedback),
]:
    builder.add_node(name, fn)

builder.add_edge(START, "elevator_pitch")

# Interview nodes: conditional edge — loop to self or advance to report node
_INTERVIEW_ROUTING = [
    ("elevator_pitch",   {"elevator_pitch": "elevator_pitch", "elevator_pitch_report": "elevator_pitch_report"}),
    ("CAR",              {"CAR": "CAR", "CAR_report": "CAR_report"}),
    ("technical",        {"technical": "technical", "technical_report": "technical_report"}),
    ("leadership",       {"leadership": "leadership", "leadership_report": "leadership_report"}),
    ("motivation",       {"motivation": "motivation", "motivation_report": "motivation_report"}),
    ("marcio_questions", {"marcio_questions": "marcio_questions", "feedback": "feedback"}),
]

for node_name, path_map in _INTERVIEW_ROUTING:
    builder.add_conditional_edges(
        node_name,
        lambda state, _m=path_map: _m.get(state["fase"], END),
        path_map,
    )

# Report nodes: unconditional edge to next interview node
builder.add_edge("elevator_pitch_report", "CAR")
builder.add_edge("CAR_report",            "technical")
builder.add_edge("technical_report",      "leadership")
builder.add_edge("leadership_report",     "motivation")
builder.add_edge("motivation_report",     "marcio_questions")

builder.add_edge("feedback", END)

checkpointer = _Checkpointer()
graph = builder.compile(checkpointer=checkpointer)


# ---------------------------------------------------------------------------
# Initial state factory
# ---------------------------------------------------------------------------

def make_initial_state() -> EntrevistaState:
    return {
        "messages": [HumanMessage(content="Hi, I'm ready to start the interview.")],
        "phase_messages": [HumanMessage(content="Hi, I'm ready to start the interview.")],
        "archive": [],
        "fase": "elevator_pitch",
        "checklist_pitch": {
            "apresentacao_pessoal": False,
            "phd_como_forca": False,
            "pesquisa_internacional": False,
            "software_cv": False,
            "transicao_industria": False,
            "venturus_milestone": False,
            "trabalho_atual_negocio": False,
            "closing_demo_producao": False,
            "sem_stack_names": False,
            "sem_metricas": False,
            "ingles_adequado": False,
        },
        "checklist_CAR": {
            "contexto_negocio": False,
            "problema_negocio": False,
            "acoes_pessoais": False,
            "langfuse_observability": False,
            "token_optimization": False,
            "resultado_negocio": False,
            "production_mindset": False,
            "ingles_adequado": False,
        },
        "checklist_technical": {
            "q1_monitoring": False,
            "q2_degradacao": False,
            "q3_rag": False,
            "producao_mindset": False,
            "ingles_adequado": False,
        },
        "checklist_leadership": {
            "data_audit": False,
            "data_como_risco_primario": False,
            "pilot_producao_gap": False,
            "mitigacao_concreta": False,
            "stakeholder_mgmt": False,
            "data_point_usado": False,
            "experiencia_real": False,
            "ingles_adequado": False,
        },
        "checklist_motivation": {
            "especifico_factored": False,
            "conexao_real": False,
            "nao_pode_obter_em_outro_lugar": False,
            "tom_genuino": False,
            "ingles_adequado": False,
        },
        "notas_pitch": "",
        "notas_CAR": "",
        "notas_technical": "",
        "notas_leadership": "",
        "notas_motivation": "",
        "ingles_erros_acumulados": [],
    }
