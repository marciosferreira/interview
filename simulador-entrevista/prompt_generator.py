"""
Generates a personalized interview preparation document from a job description + resume.

The output is a single markdown document that gets injected into every interview phase
system prompt, giving the AI interviewer full context about who the candidate is and
what the role requires.
"""

import os
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

_gen_model = None

def _get_model() -> ChatAnthropic:
    global _gen_model
    if _gen_model is None:
        _gen_model = ChatAnthropic(
            model=os.getenv("GENERATOR_MODEL", "claude-sonnet-4-6"),
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            max_tokens=8192,
        )
    return _gen_model

_SYSTEM = """You are an expert interview designer. Analyze a job description and resume, then produce a concise structured briefing for an AI interviewer named Alex.

Alex is an experienced interviewer who will adapt your notes in real time — do NOT write scripts, long paragraphs, or sample answers. Write short, dense bullets only. Every item should be one line.

Rules:
- Reference actual names, projects, companies, and numbers from the resume/JD.
- Adapt to the role domain — never impose tech framing on non-tech roles.
- Match seniority to the job title.
- Do not invent anything not in the documents.
- Be concise. Alex does the rest."""

_PROMPT_TEMPLATE = """
## Job Posting
**Title:** {job_title}
**Company:** {company}

{job_description}

---

## Candidate Resume
{resume_text}

---

Generate a concise interview briefing. Use short bullets only — no paragraphs, no sample answers, no scripts. Alex will adapt everything in real time.

# CANDIDATE PROFILE
- **Full name:** (from resume, or "Candidate")
- **Current role:** (title + company)
- **Education:** (highest degree, one line)
- **Top 2 achievements:** (specific, concrete, from resume)
- **Domain expertise:** (primary skills/areas relevant to this role)
- **Key differentiator:** (one line — what sets them apart for this role)

# TARGET ROLE ANALYSIS
- **Role domain:** (e.g., Software Engineering / Sales / Finance / Marketing / HR / Operations)
- **Core capability needed:** (the one underlying thing the hiring manager wants — one line)
- **Hard requirements:** (non-negotiable skills/experience)
- **Probe areas:** (2 areas where this candidate will be tested hardest, based on their gaps vs. the JD)
- **Concerns:** (1–2 gaps or risks worth flagging)

# ELEVATOR PITCH GUIDANCE
- **Must-cover elements:** (3–4 specific items from their background directly relevant to this role)
- **What to avoid:** (specific weaknesses or irrelevant items to sidestep)
- **Checklist for evaluation:**
  - personal_intro_clear: introduces name, role, and location
  - background_framed_as_asset: background framed as capability developed, not just credential listed
  - key_achievement_mentioned: most impressive achievement mentioned
  - career_narrative_coherent: progression explained as intentional
  - current_role_in_business_terms: current work described in business impact terms
  - closes_with_differentiator: ends with what makes them uniquely suited for this role
  - english_adequate: English is fluent and professional throughout

# CAR PROJECT GUIDANCE
- **Best project for a CAR story:** (name it — most relevant to this role's hard requirements)
- **Why it works:** (one line connecting it to the JD)
- **Result to emphasize:** (business impact — quantify if possible)
- **Checklist for evaluation:**
  - business_context_clear: business context set (industry, problem, stakeholders)
  - problem_stated_clearly: problem described in business terms
  - personal_ownership: uses "I" not "we" for key decisions
  - specific_actions: concrete actions taken
  - deliberate_choices: key choices explained as deliberate with reasoning
  - result_in_business_terms: result as business impact, not task completion
  - production_mindset: shows awareness of real-world delivery realities
  - english_adequate: English is fluent and professional throughout

# TECHNICAL EVALUATION FOCUS
3 domain questions calibrated to this role and seniority. Adapt to the domain (tech/finance/sales/marketing/HR/ops/legal). Write each question as Alex should ask it.

**Q1:** [foundational — core domain knowledge]
Evaluation criteria:
  - q1_answered: addressed with substance
  - q1_depth: showed real domain knowledge

**Q2:** [applied — realistic scenario requiring real experience]
Evaluation criteria:
  - q2_answered: addressed with substance
  - q2_depth: connected to real experience and applied judgment

**Q3:** [judgment — ambiguous, no single right answer]
Evaluation criteria:
  - q3_answered: addressed with substance
  - q3_depth: demonstrated mature judgment and awareness of tradeoffs

**Common checklist:**
  - answers_show_depth: at least 2 of 3 answers went beyond surface knowledge
  - production_mindset: at least 1 answer included real-world awareness (risks, tradeoffs, measurement)
  - english_adequate: English is fluent and professional throughout

# LEADERSHIP & APPROACH EVALUATION
- **Scenario topic:** (2-sentence description of the situation Alex should present — domain-specific, ambiguous, with time pressure and stakeholder friction; Alex will phrase it in his own words)
- **Key signals to listen for:** (2–3 specific things a strong answer includes for this role)
- **Red flags:** (1–2 weak answer patterns specific to this candidate's profile)
- **Checklist for evaluation:**
  - starts_with_situation_assessment: assesses current state before jumping to execution
  - identifies_primary_risk: names the primary risk clearly and early
  - execution_realism: recognizes gap between plan and real-world delivery
  - concrete_mitigation_plan: offers specific actions to address the risk
  - stakeholder_management: shows proactive communication with stakeholders
  - connects_to_real_experience: connects at least one point to their actual background
  - english_adequate: English is fluent and professional throughout

# FIT & MOTIVATION EVALUATION
- **Company/role elements to probe:** (2 specific things from the JD a motivated candidate would know — not generic)
- **Why this role makes sense for them:** (one line — career logic)
- **Red flags:** (what signals a generic/rehearsed answer for this candidate)
- **Checklist for evaluation:**
  - specific_company_knowledge: references 2+ specific company/role attributes
  - genuine_connection: draws explicit line between their background and company needs
  - unique_fit: names something they can get here they cannot get in current role
  - authentic_tone: sounds specific and genuine, not rehearsed
  - english_adequate: English is fluent and professional throughout

# LANGUAGE & COMMUNICATION NOTES
- **Interview language:** {language}
- **Communication pattern to watch:** (one line — e.g., L2 speaker, over-explains technically, avoids direct answers)
- **Key vocabulary to use:** (3–4 domain-specific terms that signal fluency in this role)
"""


async def generate_interview_context(
    job_title: str,
    company: str,
    job_description: str,
    resume_text: str,
    language: str = "en",
) -> str:
    """Call the LLM to produce a personalized interview preparation document."""
    prompt = _PROMPT_TEMPLATE.format(
        job_title=job_title,
        company=company,
        job_description=job_description,
        resume_text=resume_text,
        language=language,
    )
    messages = [
        SystemMessage(content=_SYSTEM),
        HumanMessage(content=prompt),
    ]
    response = await _get_model().ainvoke(messages)
    return response.content


def extract_candidate_name(interview_context: str) -> str:
    """Parse candidate name from the generated context document."""
    for line in interview_context.splitlines():
        if "**Full name:**" in line or "Full name:" in line:
            name = line.split(":", 1)[-1].strip().lstrip("*").rstrip("*").strip()
            if name and name.lower() not in ("candidate", "unknown", "n/a", "not found", "not mentioned"):
                return name
    return "the candidate"
