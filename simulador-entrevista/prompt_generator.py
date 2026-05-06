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
            model=os.getenv("GENERATOR_MODEL", "claude-haiku-4-5-20251001"),
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            max_tokens=4096,
        )
    return _gen_model

_SYSTEM = """You are an expert interview coach and technical recruiter.
Your job is to analyze a job description and a candidate's resume, then create a comprehensive
interview preparation document used by an AI interviewer named Alex.

Be specific. Reference actual details from the resume and job description.
Do not invent credentials or achievements not mentioned in the resume.
Write in clear, professional English."""

_PROMPT_TEMPLATE = """
## Job Posting
**Title:** {job_title}
**Company:** {company}

{job_description}

---

## Candidate Resume
{resume_text}

---

Generate a comprehensive interview preparation document with EXACTLY these sections:

# CANDIDATE PROFILE
- **Full name:** (from resume, or "Candidate" if not found)
- **Current role:** (title + company)
- **Education:** (highest degree — frame as a cognitive asset, not just a credential)
- **Key achievements:** (2–3 most impressive, specific to this candidate)
- **Technical expertise:** (primary areas, 3–5 bullets)
- **Career narrative:** (1 paragraph — how they evolved from their background to today)
- **Key differentiator:** (what makes them stand out vs. typical candidates for this role)

# TARGET ROLE ANALYSIS
- **What this role really needs:** (beyond the bullet list in the JD)
- **Hard requirements:** (skills/experience that are non-negotiable)
- **Nice-to-haves:** (preferred but not blocking)
- **What the interviewer will probe hardest:** (2–3 areas, based on the JD + candidate profile)
- **Potential concerns about this candidate:** (gaps or risks the interviewer might notice)

# ELEVATOR PITCH GUIDANCE
- **Ideal narrative arc for this candidate + role:** (specific story, not generic advice)
- **Must-cover elements:** (4–6 specific items from their background relevant to this role)
- **What to avoid:** (specific weaknesses, irrelevant items, or red flags to sidestep)
- **Opening hook suggestion:** (one strong opening sentence)
- **Closing signal:** (how to end strongly — their biggest differentiator)
- **Checklist for evaluation:**
  - personal_intro_clear: candidate introduces name, role, and location
  - background_framed_as_asset: academic/professional background framed as cognitive asset, not just credential
  - key_achievement_mentioned: most impressive achievement or differentiator mentioned
  - career_narrative_coherent: progression from background to current role explained as intentional
  - current_role_in_business_terms: current work described in business impact terms, not tech stack
  - closes_with_differentiator: ends with what makes them uniquely suited for this role
  - english_adequate: English is fluent and professional throughout

# CAR PROJECT GUIDANCE
- **Best project from their resume for a CAR story:** (name it explicitly)
- **Why this project works for this role:** (connection to JD requirements)
- **Business context to set:** (industry, problem, stakeholders)
- **Personal ownership signals:** (specific decisions they owned — use "I", not "we")
- **Key actions to highlight:** (2–3 most impressive actions, in business terms)
- **Result to emphasize:** (business impact — not just technical metrics)
- **Production mindset signals:** (what shows they think beyond the demo)
- **Checklist for evaluation:**
  - business_context_clear: business context set (industry, problem, stakeholders)
  - problem_stated_clearly: problem described in business terms, not just technical framing
  - personal_ownership: uses "I" not "we", owns decisions
  - specific_actions: concrete actions taken, not vague descriptions
  - deliberate_choices: key technical/design choices explained as deliberate decisions
  - result_in_business_terms: result described as business impact
  - production_mindset: proactive thinking about production risks, observability, or scale
  - english_adequate: English is fluent and professional throughout

# TECHNICAL EVALUATION FOCUS
List exactly 3 technical questions likely asked for this specific role:

**Q1:** [question text]
Strong answer looks like: [specifics]
Evaluation criteria:
  - q1_answered: question was addressed with substance
  - q1_depth: answer showed depth, not surface-level knowledge

**Q2:** [question text]
Strong answer looks like: [specifics]
Evaluation criteria:
  - q2_answered: question was addressed with substance
  - q2_depth: answer showed depth

**Q3:** [question text]
Strong answer looks like: [specifics]
Evaluation criteria:
  - q3_answered: question was addressed with substance
  - q3_depth: answer showed depth

**Common checklist across all technical questions:**
  - answers_show_depth: answers go beyond definitions to show real understanding
  - production_mindset: answers include production-awareness (observability, failure modes, scale)
  - english_adequate: English is fluent and professional throughout

# LEADERSHIP & APPROACH EVALUATION
- **Key leadership scenario to probe:** (based on candidate's background + role level)
- **What strong answers look like:** (3–4 specific signals)
- **Red flags to watch for:** (based on this candidate's profile)
- **Checklist for evaluation:**
  - starts_with_data_assessment: begins any new project by assessing/auditing the data
  - identifies_primary_risk: identifies the primary project risk early
  - pilot_to_production_awareness: recognizes the gap between a pilot/demo and production
  - concrete_mitigation_plan: offers concrete mitigation strategies, not just acknowledgment
  - stakeholder_management: demonstrates proactive stakeholder communication
  - connects_to_real_experience: connects answers to specific real experience from their background
  - english_adequate: English is fluent and professional throughout

# FIT & MOTIVATION EVALUATION
- **What specific company/role elements to reference:** (2–3 specific things from the JD)
- **Candidate's unique "why":** (what they can get here that they can't get in their current role)
- **What makes their motivation credible:** (specific connections between background and this role)
- **Red flags (generic/rehearsed answers):** (what to watch for)
- **Checklist for evaluation:**
  - specific_company_knowledge: references 2+ specific company/role attributes with understanding
  - genuine_connection: draws explicit line between their background and this company's needs
  - unique_fit: names what they can get here that they cannot get elsewhere
  - authentic_tone: tone feels genuine and specific, not rehearsed or generic
  - english_adequate: English is fluent and professional throughout

# LANGUAGE & COMMUNICATION NOTES
- **Interview language:** {language}
- **Communication patterns to watch for:** (based on candidate's background — e.g., L2 English patterns)
- **Vocabulary they should use:** (5 terms/phrases relevant to this role)
- **Vocabulary to avoid:** (overused buzzwords or red flags for this role)
- **English fluency baseline:** (assessment based on their profile — e.g., likely L2 speaker)
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
