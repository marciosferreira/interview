import os
from pathlib import Path
from typing import Annotated
from typing_extensions import TypedDict

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.types import interrupt, Command
from pydantic import BaseModel

load_dotenv()

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


# Composed system prompts — each node gets only the context it needs
SYSTEM_PITCH       = load_prompt("persona.md", "context_marcio.md", "elevator_pitch.md")
SYSTEM_CAR         = load_prompt("persona.md", "context_marcio.md", "car.md")
SYSTEM_TECHNICAL   = load_prompt("persona.md", "context_marcio.md", "technical.md")
SYSTEM_LEADERSHIP  = load_prompt("persona.md", "context_marcio.md", "leadership.md")
SYSTEM_MOTIVATION  = load_prompt("persona.md", "context_marcio.md", "motivation.md")
SYSTEM_MARCIO_Q    = load_prompt("persona.md", "marcio_questions.md")
SYSTEM_SCORECARD   = load_prompt("context_marcio.md", "scorecard.md")


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

class EntrevistaState(TypedDict):
    messages: Annotated[list, add_messages]
    fase: str  # elevator_pitch | CAR | technical | leadership | motivation | marcio_questions | feedback | done

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

    ingles_erros_acumulados: list  # cross-phase English error accumulation


# ---------------------------------------------------------------------------
# Structured outputs
# ---------------------------------------------------------------------------

class AvaliacaoPitch(BaseModel):
    apresentacao_pessoal: bool
    phd_como_forca: bool
    pesquisa_internacional: bool
    software_cv: bool
    transicao_industria: bool
    sem_detalhes_tecnicos: bool
    ingles_adequado: bool
    mensagem: str           # full conversational reply from Maria Ximena
    fase_completa: bool
    observacoes: str        # internal notes, not shown to candidate
    oportunidades_perdidas: list[str]   # things Marcio knew but didn't mention
    vocabulario_sugerido: list[str]     # stronger terms/framings he could have used
    ingles_erros: list[str]             # specific English issues this turn


class AvaliacaoCAR(BaseModel):
    contexto_negocio: bool
    acoes_pessoais: bool
    token_optimization: bool
    langfuse_observability: bool
    resultado_negocio: bool
    ingles_adequado: bool
    mensagem: str
    fase_completa: bool
    observacoes: str
    oportunidades_perdidas: list[str]
    vocabulario_sugerido: list[str]
    ingles_erros: list[str]


class AvaliacaoTechnical(BaseModel):
    q1_monitoring: bool
    q2_degradacao: bool
    q3_rag: bool
    producao_mindset: bool
    ingles_adequado: bool
    mensagem: str
    fase_completa: bool
    observacoes: str
    oportunidades_perdidas: list[str]
    vocabulario_sugerido: list[str]
    ingles_erros: list[str]


class AvaliacaoLeadership(BaseModel):
    data_audit: bool
    pilot_producao_gap: bool
    stakeholder_mgmt: bool
    data_point_usado: bool
    ingles_adequado: bool
    mensagem: str
    fase_completa: bool
    observacoes: str
    oportunidades_perdidas: list[str]
    vocabulario_sugerido: list[str]
    ingles_erros: list[str]


class AvaliacaoMotivation(BaseModel):
    especifico_factored: bool
    producao_focus: bool
    conexao_real: bool
    ingles_adequado: bool
    mensagem: str
    fase_completa: bool
    observacoes: str
    oportunidades_perdidas: list[str]
    vocabulario_sugerido: list[str]
    ingles_erros: list[str]


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
    # What Marcio didn't say but should have — per phase
    oportunidades_pitch: list[str]
    oportunidades_CAR: list[str]
    oportunidades_technical: list[str]
    oportunidades_leadership: list[str]
    # Vocabulary to practice — terms/framings Marcio avoided or weakened
    vocabulario_para_praticar: list[str]   # each entry: "term → why it matters"
    ingles_rating: str
    ingles_padroes: list[str]
    score_total: int
    hire_signal: str
    forcas: list[str]
    melhorias: list[str]
    insight_chave: str


# ---------------------------------------------------------------------------
# Generic node factory
# ---------------------------------------------------------------------------

def _phase_messages(all_messages: list) -> list:
    """Return only the messages that belong to the current phase.

    Each phase transition appends a HumanMessage("[acknowledged — ready for
    next phase]") sentinel.  Everything *before* the last such sentinel belongs
    to a completed phase and must not bleed into the current evaluation —
    otherwise the LLM sees the elevator-pitch history while evaluating a CAR
    answer and generates stale feedback.

    On the very first invocation of a new phase the slice is empty (the
    sentinel is the last message).  In that case return a neutral opener so
    the API call always has at least one human message.
    """
    last_ack = max(
        (i for i, m in enumerate(all_messages)
         if isinstance(m, HumanMessage) and "[acknowledged" in m.content),
        default=-1,
    )
    phase_msgs = all_messages[last_ack + 1:]
    if not phase_msgs:
        phase_msgs = [HumanMessage(content="I'm ready to start this phase.")]
    return phase_msgs


def _make_node(system_prompt: str, output_class, checklist_key: str, notas_key: str, next_fase: str):
    """
    Returns a node function that:
    1. Calls the model with structured output (current-phase context only)
    2. Accumulates checklist booleans (only grows — never unsets)
    3. If incomplete: interrupt() → wait for user, then return updated messages
    4. If complete: add transition and advance fase
    """
    def node(state: EntrevistaState) -> dict:
        structured = model.with_structured_output(output_class)
        # Use only messages from the current phase to avoid prior-phase contamination
        phase_msgs = _phase_messages(state["messages"])
        messages = [SystemMessage(content=system_prompt)] + phase_msgs
        avaliacao = structured.invoke(messages)

        # Merge checklist — fields that are already True stay True
        old_checklist = state[checklist_key]
        new_checklist = {
            k: old_checklist.get(k, False) or getattr(avaliacao, k, False)
            for k in old_checklist
        }

        # Accumulate internal notes
        old_notas = state[notas_key]
        new_notas = (old_notas + "\n" + avaliacao.observacoes).strip() if avaliacao.observacoes else old_notas

        # Accumulate English errors across phases
        old_ingles_erros = state.get("ingles_erros_acumulados", [])
        new_ingles_erros = old_ingles_erros + (avaliacao.ingles_erros or [])

        if not avaliacao.fase_completa:
            user_response = interrupt(avaliacao.mensagem)
            return {
                "messages": [
                    AIMessage(content=avaliacao.mensagem),
                    HumanMessage(content=user_response),
                ],
                checklist_key: new_checklist,
                notas_key: new_notas,
                "ingles_erros_acumulados": new_ingles_erros,
                "fase": state["fase"],  # stay in current phase
            }

        # Phase complete — transition.
        # The AIMessage(feedback) is sent to the client via api.py.
        # A trailing HumanMessage is required so the next node's LLM call
        # does not receive a conversation ending in an AIMessage (Anthropic rejects that).
        return {
            "messages": [
                AIMessage(content=avaliacao.mensagem),
                HumanMessage(content="[acknowledged — ready for next phase]"),
            ],
            checklist_key: new_checklist,
            notas_key: new_notas,
            "ingles_erros_acumulados": new_ingles_erros,
            "fase": next_fase,
        }

    node.__name__ = f"node_{checklist_key}"
    return node


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

elevator_pitch = _make_node(
    SYSTEM_PITCH, AvaliacaoPitch,
    checklist_key="checklist_pitch", notas_key="notas_pitch",
    next_fase="CAR",
)

CAR = _make_node(
    SYSTEM_CAR, AvaliacaoCAR,
    checklist_key="checklist_CAR", notas_key="notas_CAR",
    next_fase="technical",
)

technical = _make_node(
    SYSTEM_TECHNICAL, AvaliacaoTechnical,
    checklist_key="checklist_technical", notas_key="notas_technical",
    next_fase="leadership",
)

leadership = _make_node(
    SYSTEM_LEADERSHIP, AvaliacaoLeadership,
    checklist_key="checklist_leadership", notas_key="notas_leadership",
    next_fase="motivation",
)

motivation = _make_node(
    SYSTEM_MOTIVATION, AvaliacaoMotivation,
    checklist_key="checklist_motivation", notas_key="notas_motivation",
    next_fase="marcio_questions",
)


def marcio_questions(state: EntrevistaState) -> dict:
    structured = model.with_structured_output(AvaliacaoMarcioQuestions)
    phase_msgs = _phase_messages(state["messages"])
    messages = [SystemMessage(content=SYSTEM_MARCIO_Q)] + phase_msgs
    avaliacao = structured.invoke(messages)

    if not avaliacao.fase_completa:
        user_response = interrupt(avaliacao.mensagem)
        return {
            "messages": [
                AIMessage(content=avaliacao.mensagem),
                HumanMessage(content=user_response),
            ],
            "fase": "marcio_questions",
        }

    return {
        "messages": [AIMessage(content=avaliacao.mensagem)],
        "fase": "feedback",
    }


def feedback(state: EntrevistaState) -> dict:
    structured = model.with_structured_output(Scorecard)
    messages = [SystemMessage(content=SYSTEM_SCORECARD)] + state["messages"]
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
        "These are things Marcio had the experience to mention but did not use.",
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
        "Terms and framings a senior production AI engineer uses naturally.",
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

FASE_TO_NODE = {
    "elevator_pitch":   "elevator_pitch",
    "CAR":              "CAR",
    "technical":        "technical",
    "leadership":       "leadership",
    "motivation":       "motivation",
    "marcio_questions": "marcio_questions",
    "feedback":         "feedback",
}

builder = StateGraph(EntrevistaState)

for name, fn in [
    ("elevator_pitch",   elevator_pitch),
    ("CAR",              CAR),
    ("technical",        technical),
    ("leadership",       leadership),
    ("motivation",       motivation),
    ("marcio_questions", marcio_questions),
    ("feedback",         feedback),
]:
    builder.add_node(name, fn)

builder.add_edge(START, "elevator_pitch")

# Each node routes back to itself (loop) or forward (transition), except feedback → END
for node_name in ["elevator_pitch", "CAR", "technical", "leadership", "motivation", "marcio_questions"]:
    builder.add_conditional_edges(
        node_name,
        lambda state, _n=node_name: FASE_TO_NODE.get(state["fase"], END),
    )

builder.add_edge("feedback", END)

checkpointer = MemorySaver()
graph = builder.compile(checkpointer=checkpointer)


# ---------------------------------------------------------------------------
# Initial state factory
# ---------------------------------------------------------------------------

def make_initial_state() -> EntrevistaState:
    return {
        "messages": [HumanMessage(content="Hi, I'm ready to start the interview.")],
        "fase": "elevator_pitch",
        "checklist_pitch": {
            "apresentacao_pessoal": False,
            "phd_como_forca": False,
            "pesquisa_internacional": False,
            "software_cv": False,
            "transicao_industria": False,
            "sem_detalhes_tecnicos": False,
            "ingles_adequado": False,
        },
        "checklist_CAR": {
            "contexto_negocio": False,
            "acoes_pessoais": False,
            "token_optimization": False,
            "langfuse_observability": False,
            "resultado_negocio": False,
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
            "pilot_producao_gap": False,
            "stakeholder_mgmt": False,
            "data_point_usado": False,
            "ingles_adequado": False,
        },
        "checklist_motivation": {
            "especifico_factored": False,
            "producao_focus": False,
            "conexao_real": False,
            "ingles_adequado": False,
        },
        "notas_pitch": "",
        "notas_CAR": "",
        "notas_technical": "",
        "notas_leadership": "",
        "notas_motivation": "",
        "ingles_erros_acumulados": [],
    }
