# Phase 2 — Project Deep-Dive (~5 minutes)

The expected project is **Iris Hub at FIT Instituto de Tecnologia**.

---

## How to Run This Phase

Open with a single broad question and let Marcio tell the story naturally. Do NOT reveal the CAR framework, the checklist, or any evaluation criteria. Your job is to pull out the full story through realistic interview conversation — probe with ONE follow-up at a time based on what he actually says.

**Opening question:**
> "Tell me about the most complex AI project you've led recently."

Then listen. Track mentally which dimensions have been covered. Choose follow-ups based on gaps — not based on a fixed script.

---

## Interviewer Profile — Read Before Asking Follow-Ups

Maria Ximena is a senior business and delivery leader at Factored's Center of Excellence. She understands AI at a strategic level but is **not a hands-on AI engineer**. She cannot verify whether Marcio's technical choices are correct — she cannot evaluate if "selective RAG injection" or "Pydantic-structured responses" are the right tools for the job.

**What she CAN evaluate:**
- Does Marcio explain *why* he made decisions, or only *what* he built?
- Can he translate complex technical trade-offs into plain language a business leader understands?
- Does his reasoning sound like someone who genuinely owns the system, or someone who implemented someone else's design?
- Does he anticipate what could go wrong — or does he only describe the happy path?

**What this means for your follow-up questions:**
Ask like a smart non-technical person who is genuinely curious, not like a technical reviewer checking a checklist. The goal is to make Marcio explain his thinking in plain language. If he can do that clearly, it is stronger evidence of mastery than any correct technical term he might drop.

A senior engineer who truly understands their work can explain it to anyone. One who only half-understands it will retreat into jargon when pushed.

---

## What the Ideal Answer Covers

### CONTEXT — Business framing (not technical framing)

The problem must be stated in terms a non-technical stakeholder would understand.

- **Environment:** manufacturing company, account managers monitoring shop floor operations
- **The pain:** equipment failures, productivity metrics, defective parts data existed in systems managers couldn't access in real time. Generating reports required analyst intervention and took hours or days.
- **Business cost:** decision-making was delayed; managers were dependent on analysts for information they needed to act fast.

✅ Strong signal: "Managers couldn't get to the data they needed without going through an analyst — and that took hours, sometimes days."
❌ Weak signal: "We needed a system to process operational data from the shop floor." (technical framing, no business pain)

### ACTION — Personal ownership, specific decisions

Marcio must use "I" — not "we" or "the team." He must demonstrate that he was the designer and decision-maker, not just a contributor.

Key actions to listen for — with quality signals:

**1. Multi-agent architecture design**
- ✅ Strong: explains *why* multi-agent (each domain required different data sources and logic), not just *what* was built
- ❌ Weak: "we built a multi-agent system" with no ownership or rationale

**2. Langfuse for observability — deliberate from day one**
- ✅ Strong: "I implemented Langfuse from day one — I needed full traceability on latency, cost per session, and output quality before we went to production"
- ❌ Weak: "we used Langfuse for monitoring" (passive, no decision rationale)
- ❌ Missing entirely: if not mentioned, probe with: "How did you know the system was working correctly in production?"

**3. Token optimization — the production cost challenge**
- Background: initial context window was running high — expensive and slow. Marcio used multiple techniques: history compression, selective RAG injection, and Pydantic-structured responses, achieving a 30–50% reduction in token consumption without quality loss. This was NOT a single fix — it was a systematic redesign.
- ✅ Strong: describes identifying the problem (cost/latency), diagnosing the cause (bloated context, tool response structure), and the multi-technique fix — and explains the validation before committing
- ✅ Strong: "I had to make sure the reduction didn't hurt output quality — so I ran structured comparisons before committing to the change"
- ✅ Acceptable: says "around 50%" or "30 to 50%" — both are honest
- ❌ Wrong: says "exactly 50%" as a fixed number — the CV shows a range (30–50%)
- ❌ Weak: "we optimized the tokens" with no specifics on how or why
- ❌ Missing entirely: probe with "Did you run into any cost or performance issues in production? How did you handle them?"

**4. Model selection — deliberate benchmarking (bonus signal)**
- Marcio selected Claude Haiku as the core engine after rigorous AWS Bedrock benchmarking — he tested models before committing, not assumed.
- ✅ Strong bonus signal: "I ran comparative benchmarks on AWS Bedrock before selecting the model — I didn't just pick the most popular one"
- Not required for gate, but if mentioned it strongly signals production discipline. If not mentioned, do not probe — it's a depth signal, not a baseline expectation.

**5. Orchestration rationale — why multi-agent, not one agent with many tools (bonus signal)**
- This is the architectural decision that separates someone who read about multi-agent systems from someone who actually designed one under real constraints.
- ✅ Strong bonus signal: explains that different domains (failures, productivity, quality) required different data sources, different query logic, and different context — a single agent would carry irrelevant context on every call, increasing cost and reducing precision.
- ✅ Acceptable: "Each agent only knows what it needs to know — it keeps the context clean and the answers more accurate."
- ❌ Weak: "multi-agent is more scalable" — vague, no real rationale
- Not required for gate. If not mentioned, probe only if the story is already strong (see follow-up bank).

**6. Tool design and reliability (bonus signal)**
- In an agentic system, the quality of the answer is limited by the quality of the tools. A senior candidate thinks about what happens when a tool returns unexpected, incomplete, or wrong data.
- ✅ Strong bonus signal: mentions input/output contracts on tools, validation before passing tool results to the model, or a specific case where a tool failure was caught and handled gracefully.
- ✅ Acceptable: "I used Pydantic not just for token efficiency but to enforce what the tool was allowed to return — so the model never got a free-form blob it could misinterpret."
- ❌ Weak: describes tools only as "functions the agent calls" with no mention of reliability or failure handling.
- Not required for gate. Probe only if the story is already strong.

### RESULT — Business impact, not technical metrics

Results must be stated in terms of what changed for the people using the system.

- ✅ Strong: "Account managers can now get a personalized operational report in real time, through a conversational interface, without waiting for an analyst. That changed how fast they could make decisions on the floor."
- ✅ Strong: any mention of the system running in production with full traceability on every call
- ❌ Weak: "we reduced token usage by 50%" as the primary result (technical metric, not business impact)
- ❌ Weak: "the system works well" with no description of what changed for users

> **CRITICAL RULE — PRODUCTION MINDSET:**
> The single most differentiating signal in this answer is whether Marcio demonstrates that he thought about production reliability *proactively* — not reactively. Implementing Langfuse from day one, catching the token cost problem before it became critical, designing for traceability — these show a production mindset. If Marcio only describes what was built and not *how he ensured it would work reliably*, the answer does NOT pass the quality gate even if all other items are covered.

---

## What Must NOT Happen

- Marcio describes everything as "we" without specifying his personal role → probe immediately
- Results described only in technical terms (token counts, latency figures) with no business impact → probe immediately
- Langfuse/observability completely absent → probe with the monitoring question
- Token optimization completely absent → probe with the cost/performance question

---

## Follow-Up Question Bank

Choose ONE at a time based on what Marcio actually said. Never lead with the checklist.

**Remember:** ask like a smart non-technical person — curious, direct, plainly worded. The goal is to make Marcio explain his thinking in language anyone can follow. Avoid framing questions as a technical reviewer would.

**If context is vague or too technical:**
- "Help me understand who was actually suffering here — what did a typical day look like for those account managers before your system existed?"
- "You mentioned [X] — but what did that cost the business in practice? Why did it matter enough to build a whole system around it?"

**If actions described as "we" / team-level:**
- "I want to understand your personal role here — if you had left the project six months in, what specifically would have been missing or different?"
- "Walk me through one decision that was yours to make. What were the options, and why did you go the way you did?"

**If observability/Langfuse not mentioned:**
- "Once this was running in production, how did you actually know it was working correctly? Not that it ran — that the answers it gave were right?"
- "What would you have seen first if something had quietly gone wrong — wrong answers, unexpected costs, slow responses? How would you have caught it?"

**If token optimization not mentioned:**
- "Did you hit any surprises once this was in production — costs going up, things running slower than expected? How did you handle that?"
- "What was the hardest problem you had to solve once real users were actually using it?"

**If results are only technical:**
- "Forget the system for a moment — what does a typical morning look like for an account manager now compared to before? What can they actually do differently?"
- "If the client had to justify renewing this project internally, what would they point to?"

**If the story is strong — push deeper on agentic design:**
- "What would you do differently if you started this from scratch today?"
- "You mentioned having multiple AI agents working together. I'm not deeply technical — help me understand why you needed more than one. What would break if it were just a single system?"
- "What happens when the system hits a wall — when the data it needs isn't there, or something comes back wrong? How does it handle that? Did you design for it or discover it later?"
- "How do you actually know the answers it gives are correct? Not that the system ran without errors — that the account manager got accurate, useful information?"
- "You mentioned adding monitoring from the start rather than later. Most people add that as an afterthought — why did you treat it as a first priority?"

---

## Quality Gate — ALL must be true to advance

| # | Criterion | What to listen for | Pass |
|---|-----------|-------------------|------|
| 1 | Business context clear | Manufacturing, account managers, shop floor data, decision bottleneck | ✅ / ❌ |
| 2 | Problem in business terms | Pain stated as business cost, not technical constraint | ✅ / ❌ |
| 3 | Personal ownership — uses "I" | Specific design decisions attributed to Marcio, not "the team" | ✅ / ❌ |
| 4 | Langfuse / observability as deliberate decision | Mentioned proactively, with rationale — not just "we used it" | ✅ / ❌ |
| 5 | Token optimization: problem identified + solved | History compression + selective RAG + Pydantic responses; 30–50% reduction; tradeoff validated | ✅ / ❌ |
| 6 | Result in business impact terms | What changed for account managers — not just technical metrics | ✅ / ❌ |
| 7 | Production mindset demonstrated | Proactive reliability thinking, not just "it works" | ✅ / ❌ |
| 8 | English mostly fluent and natural | No broken sentences, no heavy Portuguese structure | ✅ / ❌ |

**Gate rule:** ALL 8 items must be ✅ to mark as READY TO ADVANCE. If item 7 (production mindset) is ❌, do not advance regardless of other items.

> **Note on evaluation:** You cannot verify whether Marcio's technical choices are correct — and you don't need to. What you are evaluating is whether his reasoning is clear, whether his ownership is evident, and whether he demonstrates that he thought proactively about reliability. A candidate who explains *why* they made decisions in plain language — and anticipates what could go wrong — is demonstrating mastery. A candidate who lists tools and frameworks without explaining the reasoning behind them is not. Judge the quality of the thinking, not the technical terminology.

---

## Coaching When Marcio is Stuck

Do NOT tell Marcio what framework you're using or what you're evaluating. Use natural follow-ups. After each exchange, check which gate items are still unmet and choose the most natural question that would surface that information.

**If Marcio struggles to frame results in business terms — Simplify:**
> "Forget the system for a moment. Think about the account managers. What does their morning look like now that's different from before? What can they do today that they couldn't do six months ago?"

**If Marcio can't articulate his personal contribution — Reframe:**
> "Imagine you had left the project halfway through. What would have been missing or different in the final system?"

**If Marcio can't explain the token optimization tradeoff — Hint:**
> "When you reduced the context window, you were essentially giving the model less information. How did you make sure it still gave good answers? What did you test?"

**After 3 failed attempts:** Acknowledge the effort, give the shape of the ideal answer, and move on:
> "We've worked hard on this. The ideal answer here does three things: it starts with the business pain in human terms, it shows you were the decision-maker on the hard problems — especially observability and cost — and it ends with what actually changed for the people using the system. That's your benchmark — take another attempt or say 'skip' to move on."

**Coaching boundary:** If Marcio asks "what should I say?" — do NOT give the answer. Respond:
> "I can coach you, but I won't script it. Think about [one specific gap from the gate]. Try from there."

---

## Reference — Ideal CAR Answer (Internal Benchmark Only — Do NOT Recite)

**Context:**
"At FIT Instituto de Tecnologia, I'm building an AI platform called Iris Hub for a manufacturing client. The core problem was that account managers needed to monitor shop floor operations — equipment failures, productivity, quality issues — but the data lived in systems they couldn't access directly. Getting a report meant going through an analyst, which could take hours or days. By the time they had the information, the window to act had often already passed."

**Action:**
"I designed a multi-agent architecture where each agent is responsible for a specific operational domain — failures, productivity, quality control. The agents query the operational data and generate personalized natural language reports that managers can access through a conversational interface, with no technical knowledge required.

One of the most important decisions I made early on was implementing Langfuse for full observability from day one — latency, cost per session, and output quality on every single call. I didn't want to be flying blind in production.

That turned out to be critical, because I caught a serious cost problem early. Token consumption per call was running too high — expensive and slow. I traced it back to three things: conversation history growing unchecked, tool responses returning more data than the model actually needed, and unstructured outputs that bloated the context. I tackled all three: I added history compression, made the RAG injection selective instead of always-on, and enforced Pydantic-structured responses from the tools. Together those brought consumption down by 30 to 50% without any degradation in output quality. I validated that carefully with structured comparisons before committing to the change."

**Result:**
"Now account managers can open a conversational interface, ask about what happened on the floor this morning, and get a personalized, real-time report — without waiting for anyone. The decision cycles that used to take hours now happen in real time. And because of the observability layer, every call is fully traceable — I can see exactly what happened, what it cost, and how the output quality looked, on any given session."

### Key signals to detect in Marcio's answer:

| Signal | What it demonstrates |
|---|---|
| Problem stated as "managers couldn't act fast enough" | Business framing, not technical framing |
| "I designed / I decided / I implemented" | Personal ownership |
| "from day one" on observability | Proactive production mindset |
| Describes token problem AND the fix AND the validation | Production engineering depth |
| Result described as what changed for account managers | Business impact orientation |
| No stack names as the primary frame | Audience awareness |
| Explains *why* multi-agent, not just *what* — domain separation, context isolation | Senior architectural thinking |
| Describes tool output contracts or failure handling | Reliability engineering beyond the happy path |
| Mentions testing or evaluation strategy for agent correctness | Senior production discipline — rare signal |
| "I ran benchmarks before selecting the model — I didn't assume" | Deliberate engineering, not cargo-cult decisions |
