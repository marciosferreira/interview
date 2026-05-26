"""
Generates an interview preparation document from required role title plus optional
job/company details and optional candidate background.

The output is a single markdown document that gets injected into every interview phase
system prompt, giving the AI interviewer the best available context about who the
candidate is and what the role may require.
"""

import os
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

_gen_model_cache: dict = {}

def _get_model(model_name: str | None = None) -> ChatAnthropic:
    key = model_name or os.getenv("GENERATOR_MODEL", "claude-sonnet-4-6")
    if key not in _gen_model_cache:
        _gen_model_cache[key] = ChatAnthropic(
            model=key,
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            max_tokens=8192,
        )
    return _gen_model_cache[key]

_SYSTEM = """You are an expert interview designer. Create a concise structured briefing for an AI interviewer named Alex from the information available.

Alex is an experienced interviewer who will adapt your notes in real time — do NOT write scripts, long paragraphs, or sample answers. Write short, dense bullets only. Every item should be one line.

Rules:
- The job title is always available and is the minimum source of truth.
- Job description and company name are optional. If provided, use them to create a focused interview for that exact role/company; if missing or thin, create a solid generic interview calibrated to the job title.
- Candidate background/resume is optional. If provided, use it to suggest specific follow-ups about their experience; if missing or thin, create generic role-appropriate questions and ask the candidate to connect answers to their own experience during the interview.
- Reference actual names, projects, companies, and numbers only when they are explicitly provided.
- Adapt to the role domain — never impose tech framing on non-tech roles.
- Match seniority to the job title.
- Do not invent anything not in the documents.
- When details are missing, say "Not provided" or "Use a generic role-based probe" instead of fabricating specifics.
- Be concise. Alex does the rest.
- The CANDIDATE PROFILE section is critical: Alex reads it before the interview. Fill known fields with exact facts; mark unknown fields as "Not provided" so Alex knows what he may need to learn through the interview."""

_PROMPT_TEMPLATE = """
## Target Role
**Title:** {job_title}
**Company:** {company}

## Job Details
{job_description}

---

## Candidate Background
{resume_text}

---

Generate a concise interview briefing. Use short bullets only — no paragraphs, no sample answers, no scripts. Alex will adapt everything in real time.

IMPORTANT ADAPTATION RULES:
- If Job Details are provided, tailor role analysis, technical/domain questions, leadership scenario, and motivation probes to those details.
- If Company is provided, include company-aware motivation probes; if Company is not provided, use role/industry motivation probes and do not pretend Alex works at a named company.
- If Candidate Background is provided, include specific follow-up angles tied to their experience, projects, achievements, gaps, and vocabulary.
- If Candidate Background is missing or thin, do not make assumptions about experience. Design questions that let the candidate supply examples, and coach Alex to ask generic follow-ups such as "Can you connect that to something you've done before?"
- Always produce a complete interview plan even with only the job title.

# CANDIDATE PROFILE
IMPORTANT: Fill these with exact facts only when provided. Alex will NOT ask the candidate for information already listed here, but may ask for missing background when fields say "Not provided".

- **Name:** (from resume, or "Candidate")
- **Location:** (city/country from resume, or "Not mentioned")
- **Current role:** (exact title + company name, or "Not provided")
- **Years of experience:** (total professional experience, or "Not provided")
- **Education:** (highest degree + field, or "Not provided")
- **Top 2 achievements:** (specific, concrete, from background, or "Not provided")
- **Domain expertise:** (provided skills/areas relevant to this role, or "Not provided")
- **Key differentiator:** (provided differentiator for this role, or "Not provided")
- **Context quality:** (one of: "role title only", "role + partial job details", "role + candidate background", "role + job + candidate background")

# TARGET ROLE ANALYSIS
- **Role domain:** (e.g., Software Engineering / Sales / Finance / Marketing / HR / Operations)
- **Core capability needed:** (the one underlying thing the hiring manager wants — one line)
- **Hard requirements:** (from the JD if provided; otherwise infer common requirements from the job title and mark as role-based)
- **Probe areas:** (2 areas to test; candidate-specific if background exists, otherwise generic for this job title)
- **Concerns:** (1–2 gaps or risks; if candidate background is missing, say "insufficient candidate background to assess")

# ELEVATOR PITCH GUIDANCE
- **Must-cover elements:** (3–4 specific items from their background if provided; otherwise role-relevant themes the candidate should address)
- **Suggested follow-ups:** (2 specific follow-ups from candidate background if provided; otherwise generic prompts to elicit relevant background)
- **What to avoid:** (specific weaknesses/irrelevant items if known; otherwise generic vague-answer patterns)
- **Checklist for evaluation:**
  - personal_intro_clear: introduces name, role, and location
  - background_framed_as_asset: background framed as capability developed, not just credential listed
  - key_achievement_mentioned: most impressive achievement mentioned
  - career_narrative_coherent: progression explained as intentional
  - current_role_in_business_terms: current work described in business impact terms
  - closes_with_differentiator: ends with what makes them uniquely suited for this role
  - english_adequate: English is fluent and professional throughout

# CAR PROJECT GUIDANCE
- **Best project for a CAR story:** (name a provided project if available; otherwise ask candidate to choose a relevant project for the job title)
- **Why it works:** (one line connecting it to the JD/details if provided, otherwise to the job title's core capability)
- **Result to emphasize:** (business impact — quantify if possible)
- **If answer is too generic:** (one coaching prompt asking the candidate to connect the story to their own experience)
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
3 domain questions calibrated to this role and seniority. Adapt to the domain (tech/finance/sales/marketing/HR/ops/legal). Use JD/company specifics when provided; otherwise create strong generic questions for the job title. Write each question as Alex should ask it.

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
- **Experience-based follow-up:** (specific follow-up from candidate background if provided; otherwise ask them to connect the scenario to a past situation)
- **Red flags:** (1–2 weak answer patterns specific to this candidate's profile if known; otherwise generic weak patterns for the role)
- **Checklist for evaluation:**
  - starts_with_situation_assessment: assesses current state before jumping to execution
  - identifies_primary_risk: names the primary risk clearly and early
  - execution_realism: recognizes gap between plan and real-world delivery
  - concrete_mitigation_plan: offers specific actions to address the risk
  - stakeholder_management: shows proactive communication with stakeholders
  - connects_to_real_experience: connects at least one point to their actual background
  - english_adequate: English is fluent and professional throughout

# FIT & MOTIVATION EVALUATION
- **Company/role elements to probe:** (2 specific things from the company/JD if provided; otherwise role/industry elements a motivated candidate should reference)
- **Why this role makes sense for them:** (one line using candidate background if provided; otherwise ask candidate to explain their career logic)
- **Red flags:** (what signals a generic/rehearsed answer for this candidate if known; otherwise generic vague motivation)
- **Checklist for evaluation:**
  - specific_company_knowledge: references 2+ specific company/role attributes when available, otherwise 2+ role/industry attributes
  - genuine_connection: draws explicit line between their background and company/role needs, or explains career logic if background is missing
  - unique_fit: names something they can get from this opportunity/type of role that they cannot get in their current situation
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
    model_name: str | None = None,
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
    response = await _get_model(model_name).ainvoke(messages)
    return response.content


def extract_candidate_name(interview_context: str) -> str:
    """Parse candidate name from the generated context document."""
    for line in interview_context.splitlines():
        if "**Name:**" in line or "Name:" in line:
            name = line.split(":", 1)[-1].strip().lstrip("*").rstrip("*").strip()
            if name and name.lower() not in ("candidate", "unknown", "n/a", "not found", "not mentioned"):
                return name
    return "the candidate"
