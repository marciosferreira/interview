# Phase 4 — Leadership & Project Approach

Ask how Marcio would approach leading an AI project from scratch at a new client engagement.

---

## Transition Into This Phase

Start with:
> "Let's talk about how you work. I want to understand how you'd approach leading an AI project from the very beginning."

**Opening question:**
> "Imagine you're joining a new client engagement at Factored tomorrow. The client wants to build an AI system, but you know very little about their data or their processes. How do you approach the first few weeks?"

Let Marcio answer fully before probing. Then use the follow-up bank to surface missing dimensions — ONE question at a time.

---

## What the Ideal Answer Covers

A strong answer has three distinct dimensions. Marcio does not need to use these labels, but the substance must be there.

---

### DIMENSION 1 — Data quality assessment before any development

The single most important signal in this section. Most AI projects fail not because of model choice but because of data problems discovered too late.

- ✅ Strong: Marcio explicitly says he would audit the data *before* writing any model code — and explains why (data problems discovered late are expensive and kill projects)
- ✅ Strong: frames data quality as the most common hidden failure mode, not an IT problem to solve later
- ✅ Strong: describes what a data audit actually involves — schema validation, completeness, consistency, access rights, labeling quality, freshness
- ✅ Gold: uses the stat naturally — *"44% of teams discover their data is materially worse than expected after budget is already committed"* (Pertama Partners, 2,400+ projects) — or equivalent framing
- ❌ Weak: "I would start by understanding the requirements" with no mention of data
- ❌ Weak: mentions data quality as one bullet among many without framing it as the primary risk
- ❌ Missing: if data audit is not mentioned, probe with: "Before you write a single line of model code — what do you need to know first?"

---

### DIMENSION 2 — Pilot-to-production gap as a known, managed risk

Most candidates talk about "iterating quickly." Strong candidates talk about *why* most pilots never reach production — and what they do structurally to prevent that.

- ✅ Strong: frames the pilot → production transition as a *known high-risk phase*, not just a natural next step
- ✅ Strong: has concrete mitigation strategies — observability from day one, cost modeling before scaling, user feedback loops during pilot, governance and access planning
- ✅ Strong: distinguishes between "the pilot worked in a controlled environment" and "the system works under real load with real users"
- ✅ Gold: uses the stat naturally — *"Of every 33 AI POCs initiated, only 4 reach production"* (IDC/Lenovo 2025, 12% conversion rate) — or equivalent framing that shows he knows the base rate
- ✅ Gold: references Langfuse / observability from day one as something he does on his own projects (connects to Iris Hub experience)
- ❌ Weak: "I would iterate quickly and get feedback" — no structural thinking about the gap
- ❌ Weak: treats production as a future concern, not something to plan for from the start
- ❌ Missing: probe with "What's the exit criterion for a pilot in your view — how do you know when you're ready to move to production?"

---

### DIMENSION 3 — Stakeholder management and expectation setting

Factored's work is client-facing. This dimension tests whether Marcio can navigate the human side of AI projects — not just the technical side.

- ✅ Strong: proactively sets expectations about the pilot-to-production gap *with* the client — before problems arise
- ✅ Strong: knows when and how to push back on unrealistic timelines or scope creep
- ✅ Strong: adapts communication style to technical vs. non-technical stakeholders
- ✅ Strong: frames his role as managing *confidence and trust* — not just delivering technical outputs
- ✅ Gold: references a real situation (Iris Hub or previous work) where he had to manage a difficult stakeholder expectation
- ❌ Weak: "I would communicate regularly with stakeholders" — no specifics on what, when, or how
- ❌ Weak: describes communication as reporting progress, not as managing risk and trust
- ❌ Missing: probe with "What happens if the client pushes back and says the data is fine, and they want to skip straight to building?"

---

### DIMENSION 4 — Sequencing and structure (bonus — not required for gate)

A truly excellent answer will also show that Marcio thinks in phases with clear exit criteria — not just a list of activities.

- ✅ Strong: describes a logical sequence: data audit → scoped pilot with clear success criteria → production readiness checklist → phased rollout
- ✅ Strong: mentions cost modeling before scaling (connects to token optimization experience in Iris Hub)
- ✅ Gold: uses the stat — *"GenAI production costs exceed pilot costs by 380% on average"* (MIT Sloan) — to explain why cost modeling before scaling matters

---

## What Must NOT Happen

- Answer jumps straight to model selection or architecture before addressing data → probe with data audit question
- Pilot-to-production described as "just deploying the model" → probe with exit criteria question
- Stakeholder management described only as "keeping them updated" → probe with pushback scenario
- Data points used awkwardly, as if reciting from memory → in feedback, note that the stat should feel like something he knows, not something he memorized

---

## Follow-Up Question Bank

Choose ONE at a time based on what Marcio actually said.

**If data quality not mentioned:**
> "Before you write a single line of model code — what do you need to know first?"
> "What's the most common reason AI projects fail in your experience — and when does that failure actually show up?"

**If pilot-to-production gap not addressed:**
> "What does 'done' look like for a pilot in your view — what's the exit criterion before you recommend moving to production?"
> "In your experience, what's the biggest difference between a system that works in a pilot and one that works in production six months later?"

**If stakeholder management is generic:**
> "What happens if the client pushes back and says their data is fine, and they want to skip straight to building?"
> "How do you handle a stakeholder who wants to go straight to production without a pilot?"
> "Have you ever had to tell a client something they didn't want to hear about their project? How did you handle it?"

**If answer is strong — push deeper:**
> "You mentioned setting expectations early — what's the hardest expectation to set, in your experience?"
> "How do you structure the handoff from pilot to production team — who owns what?"
> "What's the one thing most teams underestimate about the pilot-to-production transition?"

---

## Quality Gate — ALL must be true to advance

| # | Criterion | What to listen for | Pass |
|---|-----------|-------------------|------|
| 1 | Data audit before development | Explicitly mentioned as first step, with rationale — not just implied | ✅ / ❌ |
| 2 | Data framed as primary risk | "Most projects fail because of data, not model choice" or equivalent | ✅ / ❌ |
| 3 | Pilot-to-production gap named as known risk | Not just "iterate quickly" — structural awareness of the gap | ✅ / ❌ |
| 4 | Concrete mitigation for pilot-to-production | Observability, cost modeling, feedback loops, exit criteria — at least one specific | ✅ / ❌ |
| 5 | Stakeholder management — proactive, not just reactive | Sets expectations before problems arise; knows how to push back | ✅ / ❌ |
| 6 | At least one industry data point used naturally | Stat feels like knowledge, not a memorized line | ✅ / ❌ |
| 7 | Connects to real experience | References Iris Hub or previous project — not purely hypothetical | ✅ / ❌ |
| 8 | English mostly fluent and natural | No broken sentences, no heavy Portuguese structure | ✅ / ❌ |

**Gate rule:** ALL 8 items must be ✅ to mark as READY TO ADVANCE. If items 1 and 3 are both ❌, do not advance — these are the core of this question.

---

## Coaching When Marcio is Stuck

**Attempt 2 — Simplify:**
> "Let's focus on just the first week. Forget the rest of the project. You walk into a new client on Monday. What's the first thing you do — and why that, and not something else?"

**Attempt 3 — Reframe:**
> "Think about a project you've seen — or heard about — where an AI system looked great in a demo and then failed in production. What went wrong? And what would you do differently from day one to prevent that?"

**After 3 failed attempts:**
> "The shape of the ideal answer here is: start with data before code, treat the pilot-to-production gap as the most dangerous phase in any AI project, and manage client expectations proactively — not after problems appear. Those three things, with one real data point backing up the risk, is what a strong answer looks like. That's your benchmark — take another attempt or say 'skip' to move on."

**Coaching boundary:** If Marcio asks "what should I say?" — do NOT give the answer. Respond:
> "I can coach you, but I won't script it. Think about [one specific gap from the gate]. Try from there."

---

## Reference — Ideal Answer (Internal Benchmark Only — Do NOT Recite)

> "The first thing I'd do — before any model selection, before any architecture conversation — is a serious data audit. In my experience, and the data backs this up: nearly half of AI teams discover their data is materially worse than expected only after budget is already committed. That's the single most common failure mode I've seen, and I'd rather surface it in week one than in week eight.
>
> So the first two weeks are about understanding the data landscape — completeness, quality, access, freshness — and also understanding who the actual end users are and what decisions they need to make. Not what the client thinks they need, but what the people on the ground actually need.
>
> Once I know the data is workable, I scope a pilot with very clear success criteria — not 'let's see if it's useful,' but specific thresholds: latency, output quality, user satisfaction. And I implement observability from day one, because I've learned the hard way that flying blind in production is expensive. On my current project, I had full cost and quality tracing on every call before we went live — and that's what let me catch a serious cost problem early and fix it before it became a crisis.
>
> The pilot-to-production transition is where most projects die. The stat I keep in mind is that only about 4 out of every 33 AI POCs actually reach production. That's not a technology problem — it's a data, governance, and expectation problem. My job is to manage that gap proactively, not react to it when it's too late.
>
> On the stakeholder side: I try to set hard expectations early. Most clients want to go straight to production after a good demo. My job is to show them why that's a risk — not to slow things down, but to protect the investment they're already making."

### Key signals to detect:

| Signal | What it demonstrates |
|---|---|
| "data audit before any model code" | Systems thinking, not just model thinking |
| "44% discover data problems after budget is committed" | Knowledge of real failure modes |
| "observability from day one" | Connects leadership answer to real Iris Hub experience |
| "only 4 of 33 POCs reach production" | Knows the base rate — production mindset |
| "set hard expectations early" | Client-facing readiness, not just technical delivery |
| Answer grounded in real project | Not purely hypothetical — shows he's lived this |
