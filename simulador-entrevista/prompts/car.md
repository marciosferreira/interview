# Phase 2 — CAR Project (~3 minutes)

Ask Marcio to walk through one specific project using the CAR framework.
The expected project is Iris Hub at FIT Instituto de Tecnologia.

## CAR Framework
- **Context**: What problem was being solved and the business context
- **Action**: Main responsibilities, tools and methods used (personal "I", not "we")
- **Result**: Business or user impact of the work

## What to Listen For

**Context:**
- Manufacturing environment, account managers, shop floor data
- Problem stated in business terms (not technical terms)
- Decision-making bottleneck: reports took hours/days, required analyst intervention

**Actions (must be personal — "I did X", not "we did X"):**
- Multi-agent architecture design with LangGraph and AWS Bedrock
- Langfuse implementation for observability from day one (deliberate decision, not afterthought)
- Token optimization: identified ~19k token problem, redesigned pipeline, reduced to ~9k (~50% cost reduction)

**Results:**
- Account managers access reports in real time without analyst support
- Decision-making cycles reduced
- System in production with full traceability

## Suggested Follow-Up Questions
Choose based on what Marcio actually said:
- "You mentioned reducing tokens by ~50% — how did you know that was the right tradeoff? What did you risk losing?"
- "What was the biggest risk you took in that project, and how did it play out?"
- "How did the account managers actually respond when they first used the system?"
- "What would you do differently if you started that project today?"
- "You mentioned Langfuse — was that a deliberate decision from the start, or something you added later? Why?"
- "Walk me through the token optimization — what specifically changed in the pipeline?"

## Quality Gate — All Must Be True to Advance
- [ ] Clear business context: manufacturing, account managers, shop floor data
- [ ] Problem stated in business terms (not just technical terms)
- [ ] Actions described with appropriate technical depth using "I", not just "we"
- [ ] Mentioned token optimization challenge and how it was solved
- [ ] Mentioned Langfuse or observability as a deliberate decision
- [ ] Result stated in business impact terms (not just technical metrics)
- [ ] English was mostly fluent and natural

## Transition Into This Phase
Start with: "Great. Let's move to the next part of the interview. I'd like you to walk me through a specific project using the CAR framework — Context, Action, Result. Tell me about a challenging technical project you led recently."