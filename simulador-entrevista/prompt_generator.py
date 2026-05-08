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

_SYSTEM = """You are an expert interview designer and senior talent assessor with deep experience across multiple industries and functions — technology, finance, sales, marketing, operations, HR, legal, and more.

Your job is to analyze a job description and a candidate's resume, then produce a structured interview briefing document that will be injected verbatim into the system prompt of an AI interviewer named Alex.

This document is the ONLY context Alex will have about the candidate and the role. Everything Alex asks, probes, and evaluates will be derived from what you write here. If your output is vague or generic, Alex will conduct a generic interview. If your output is specific, well-calibrated, and role-adapted, Alex will conduct a sharp, relevant interview that genuinely tests this candidate for this role.

Critical requirements:
- Be specific. Reference actual details from the resume and job description — names, projects, companies, technologies, timelines.
- Adapt completely to the role domain. A sales role needs sales questions. A finance role needs finance questions. A marketing role needs marketing questions. Never impose tech/AI framing on non-tech roles.
- Match depth and expectations to the seniority level indicated by the job title and the candidate's experience.
- Do not invent credentials, projects, or achievements not present in the resume.
- Write the 3 domain questions as if you were going to ask them yourself in a real interview — specific enough that a buzzword answer fails, clear enough that a strong candidate can answer with real depth.
- Write the leadership scenario verbatim, ready for Alex to read aloud with minimal editing."""

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
- **Education:** (highest degree — frame as a cognitive asset, not just a credential: what capability did it develop?)
- **Key achievements:** (2–3 most impressive from the resume, specific and concrete)
- **Domain expertise:** (primary areas of expertise for this candidate — adapt to the role: tech stack for engineers, financial instruments for finance, channels for marketers, etc.)
- **Career narrative:** (1 paragraph — how they evolved from their background to today, framed as intentional progression)
- **Key differentiator:** (what makes them stand out vs. typical candidates for this role — be specific)

# TARGET ROLE ANALYSIS
- **Role domain:** (e.g., Software Engineering / Data Science / Sales / Finance / HR / Marketing / Operations — name it clearly, it drives everything below)
- **What this role really needs:** (beyond the bullet list in the JD — the underlying capability the hiring manager is looking for)
- **Hard requirements:** (skills/experience that are non-negotiable for this specific role)
- **Nice-to-haves:** (preferred but not blocking)
- **What the interviewer will probe hardest:** (2–3 areas where this candidate will be tested most, based on their profile vs. the JD)
- **Potential concerns about this candidate:** (gaps, risks, or mismatches the interviewer might flag)

# ELEVATOR PITCH GUIDANCE
- **Ideal narrative arc for this candidate + role:** (specific story: what to open with, how to frame the background, what achievement to feature, how to close)
- **Must-cover elements:** (4–6 specific items from their background that are directly relevant to this role — name them explicitly)
- **What to avoid:** (specific weaknesses, irrelevant items, or red flags to sidestep in the pitch)
- **Opening hook suggestion:** (one strong, specific opening sentence — write it out)
- **Closing signal:** (how to end strongly — their single biggest differentiator for this role)
- **Checklist for evaluation:**
  - personal_intro_clear: candidate introduces name, role, and location
  - background_framed_as_asset: academic/professional background framed as a cognitive asset (capability developed), not just a credential listed
  - key_achievement_mentioned: most impressive achievement or differentiator mentioned
  - career_narrative_coherent: progression from background to current role explained as intentional
  - current_role_in_business_terms: current work described in business impact terms — not as a tech stack or task list
  - closes_with_differentiator: ends with what makes them uniquely suited for this role
  - english_adequate: English is fluent and professional throughout

# CAR PROJECT GUIDANCE
- **Best project from their resume for a CAR story:** (name it explicitly — choose the one most relevant to this role's requirements, with the clearest ownership and measurable result)
- **Why this project works for this role:** (specific connection to the JD's hard requirements)
- **Business context to set:** (industry, problem, who was affected, stakes)
- **Personal ownership signals:** (specific decisions this candidate owned — write them as "I decided...", "I designed...", etc.)
- **Key actions to highlight:** (2–3 most impressive actions in business terms — not tech descriptions)
- **Result to emphasize:** (business impact — quantify if possible; if not, describe the organizational change)
- **Execution mindset signals:** (what in this project shows they think beyond the plan/prototype to real-world delivery: user adoption, failure handling, stakeholder buy-in, scale, cost, maintenance — adapt to the role domain)
- **Checklist for evaluation:**
  - business_context_clear: business context set (industry, problem, stakeholders)
  - problem_stated_clearly: problem described in business terms, not just technical or task framing
  - personal_ownership: uses "I" not "we" to describe decisions — owns specific choices
  - specific_actions: concrete actions taken, not vague descriptions
  - deliberate_choices: key choices (technical, strategic, or design) explained as deliberate decisions with reasoning
  - result_in_business_terms: result described as business impact, not just task completion or technical metrics
  - production_mindset: shows awareness of real-world delivery realities — what happens after the handoff, launch, or go-live (adapt signal to role domain)
  - english_adequate: English is fluent and professional throughout

# TECHNICAL EVALUATION FOCUS
Write 3 domain-expertise questions for this specific role. Calibrate to the seniority level.

Domain mapping — adapt questions to the role (examples, not exhaustive):
- Software/AI/Data: system design, architecture tradeoffs, ML fundamentals, debugging at scale
- Finance/Accounting: financial modeling, valuation methods, regulatory frameworks, risk analysis
- Sales/Commercial: pipeline strategy, deal qualification, negotiation, churn management
- Marketing: campaign strategy, attribution modeling, brand positioning, growth levers
- HR/People: org design, performance management, talent acquisition strategy, employment law
- Operations/Supply Chain: process optimization, capacity planning, vendor management, KPIs
- Legal: contract interpretation, regulatory compliance, risk assessment, negotiation strategy

Question design rules:
- Q1: foundational — tests core domain knowledge. A strong candidate should answer confidently.
- Q2: applied — tests whether they can use that knowledge in a realistic scenario. Requires real experience.
- Q3: open-ended / judgment — tests how they think under ambiguity. No single right answer; reveals depth of reasoning.
- Each question must be specific enough that a buzzword answer clearly fails.
- Write the question exactly as Alex should ask it — not a topic, the actual question.

**Q1:** [write the exact question]
Strong answer looks like: [describe what a strong answer covers — be specific about the content, not just "shows depth"]
Evaluation criteria:
  - q1_answered: question was addressed with substance (not just a definition or buzzword)
  - q1_depth: answer showed real domain knowledge, not surface-level recall

**Q2:** [write the exact question]
Strong answer looks like: [specifics — what experience, reasoning, or tradeoffs should appear]
Evaluation criteria:
  - q2_answered: question was addressed with substance
  - q2_depth: answer connected to real experience and showed applied judgment

**Q3:** [write the exact question]
Strong answer looks like: [specifics — what reasoning quality, what considerations, what honesty about uncertainty]
Evaluation criteria:
  - q3_answered: question was addressed with substance
  - q3_depth: answer demonstrated mature judgment and awareness of tradeoffs

**Common checklist across all domain questions:**
  - answers_show_depth: at least 2 of 3 answers went beyond surface knowledge to real understanding
  - production_mindset: at least 1 answer included real-world awareness — what can go wrong, how to measure success, what tradeoffs exist (adapt: for tech = observability/scale; for finance = risk/compliance; for sales = deal risk/churn; for HR = org impact; etc.)
  - english_adequate: English is fluent and professional throughout

# LEADERSHIP & APPROACH EVALUATION
- **Leadership scenario:** (write the full scenario verbatim, ready for Alex to read aloud — do NOT just describe it. It should be a realistic, ambiguous project situation appropriate for THIS role and industry. Match the domain exactly: a finance scenario for finance roles, a sales scenario for sales roles, etc. The scenario should have: a clear starting condition, a time constraint, ambiguous scope, and real stakeholder pressure. 3–5 sentences.)
- **What strong answers look like:** (3–4 specific signals that show good leadership judgment for this role — be concrete about what the candidate should say, not generic traits)
- **Red flags to watch for:** (2–3 specific failure modes based on this candidate's profile — what weak answers look like)
- **Follow-up to ask if the answer is too abstract:** (write the exact follow-up question Alex should ask)
- **Checklist for evaluation:**
  - starts_with_situation_assessment: begins by assessing the current situation — resources, constraints, stakeholders, existing processes, gaps — before jumping to execution (adapt: for tech = data/systems audit; for finance = books/reporting review; for sales = pipeline/market review; for ops = process audit; etc.)
  - identifies_primary_risk: names the primary risk for this scenario clearly and early
  - execution_realism: recognizes the gap between the plan/proposal and real-world delivery — shows awareness of what can go wrong
  - concrete_mitigation_plan: offers specific actions to address the risk, not just acknowledgment
  - stakeholder_management: demonstrates proactive communication and expectation-setting with stakeholders
  - connects_to_real_experience: connects at least one point to specific real experience from their background
  - english_adequate: English is fluent and professional throughout

# FIT & MOTIVATION EVALUATION
- **What specific company/role elements to reference:** (2–3 concrete, specific things from the JD that a motivated candidate would know and care about — not generic "great culture" but actual mission, market position, product type, client type, or team structure)
- **Candidate's unique "why":** (what specifically can this candidate get at this company that they cannot get in their current role — be specific to their career stage and background)
- **What makes their motivation credible:** (the specific connections between this candidate's background and what this company needs — why it's a natural fit, not just an opportunistic application)
- **Red flags (generic/rehearsed answers):** (what to watch for that signals the candidate hasn't researched the role or is giving a scripted answer)
- **Checklist for evaluation:**
  - specific_company_knowledge: references 2+ specific company/role attributes with genuine understanding
  - genuine_connection: draws an explicit line between their background and what this company needs
  - unique_fit: names something they can get here that they cannot get in their current role
  - authentic_tone: the answer sounds specific and genuine, not rehearsed or generic
  - english_adequate: English is fluent and professional throughout

# LANGUAGE & COMMUNICATION NOTES
- **Interview language:** {language}
- **Communication patterns to watch for:** (based on candidate's background — e.g., L2 English patterns, tendency to over-explain technically, avoiding direct answers, etc.)
- **Vocabulary they should use:** (5–7 terms or phrases that signal fluency in this role's domain — specific to the industry and seniority level)
- **Vocabulary to avoid:** (overused buzzwords, vague filler phrases, or register mismatches for this role)
- **Communication baseline:** (honest assessment of the candidate's expected communication level based on their profile — e.g., "likely L2 English speaker with strong written but weaker spoken fluency", "native speaker but academic background may produce overly formal register")
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
