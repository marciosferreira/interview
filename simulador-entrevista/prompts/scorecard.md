# Final Scorecard

You have the full interview transcript AND the per-phase feedback reports in your context.
Each phase report (📋 CONTENT FEEDBACK … ✅ PHASE SUMMARY) was generated immediately after that phase ended.
You also have a list of accumulated English errors collected across all phases.

Use all of this to generate a comprehensive, honest, and constructive final scorecard.
Do not re-evaluate from scratch — build on the per-phase reports. Cross-reference them with the raw conversation to add insight the reports may have missed.

---

## Context — What Factored Is Actually Evaluating

The real Factored interview evaluates four pillars. Your scorecard must reflect all four — not just technical content:

| Pillar | What it means |
|---|---|
| **Technical Coding** | Real understanding of production AI systems — not just tool names |
| **Business Acumen** | Big picture thinking, business impact framing, alignment with client needs |
| **Communication** | Fluency, coherence, confident delivery, active listening |
| **English** | Grammatical accuracy, vocabulary, natural fluency — hard requirement for global client work |

The interview ran ~35 minutes total across 6 phases:
- Phase 1 — Elevator Pitch: 2 min
- Phase 2 — CAR Project: ~5 min (3 min answer + follow-ups)
- Phase 3 — Technical Questions: ~10 min
- Phase 4 — Leadership & Project Approach: ~8 min
- Phase 5 — Fit & Motivation: ~5 min
- Phase 6 — Marcio's Questions: ~5 min

The hire signal must reflect whether Marcio is ready for the **real Factored interview today** — not his potential. A candidate with excellent technical content but weak English is **not ready** for a role where global client communication is a hard requirement.

---

## Scoring Guide

- **5** — Excellent: exceeded expectations, specific, evidence-based, strong English
- **4** — Good: met all criteria, minor gaps
- **3** — Adequate: covered the basics but lacked depth or had notable English issues
- **2** — Weak: missing key elements or English significantly impacted clarity
- **1** — Not acceptable: answer did not address the question or was incomprehensible

## Field Instructions

Fill each field as described. These fields will be assembled into the final formatted scorecard.

**score_pitch / score_CAR / score_technical / score_leadership / score_motivation** (int 1–5)
Integer score using the guide above.

**comentario_pitch / comentario_CAR / comentario_technical / comentario_leadership / comentario_motivation** (str)
One sentence: strongest element + biggest gap. Reference what Marcio actually said.

**oportunidades_pitch / oportunidades_CAR / oportunidades_technical / oportunidades_leadership** (list of str)
2–4 bullet points per phase: things Marcio had the background to mention but didn't.
Start each with "You could have mentioned…". Be specific — reference his real experience.
Draw from the per-phase reports AND any additional gaps you notice in the raw conversation.

**vocabulario_para_praticar** (list of str)
4–6 entries combining all phases.
Format each as: "[term/phrase] → [why it matters]"
Prioritize terms Marcio avoided or weakened across multiple phases.
Draw from the "VOCABULARY & FRAMING" sections in the per-phase reports.

**ingles_rating** (str)
One of: "Fluent" / "Mostly Fluent" / "Needs Work"
Base this on the accumulated English error list AND the English feedback in the per-phase reports.

**ingles_padroes** (list of str)
2–3 recurring patterns to fix. Each entry should include a concrete example from the interview.
Consolidate across all phases — focus on patterns that appeared more than once.
Use the accumulated English error list as your primary source.

**score_total** (int)
Sum of the 5 phase scores.

**hire_signal** (str)
One of: "Strong Yes" / "Yes" / "Borderline" / "Not Yet"
Reflect whether Marcio is ready for the real Factored interview today, not his potential.
**Critical:** English is a hard gate for this role — global client communication is non-negotiable. A candidate who scores well on content but rates "Needs Work" on English cannot be "Strong Yes" or "Yes". Adjust accordingly.

**forcas** (list of 2 str)
Top 2 concrete strengths with specific examples from the interview.

**melhorias** (list of 2 str)
Top 2 highest-leverage improvements before the real interview. Actionable, specific.

**insight_chave** (str)
Single most important insight — the one thing that could make or break his real interview.
Be direct and honest.

## Instructions

- Be specific — reference actual things Marcio said (or didn't say)
- Be constructive — frame weaknesses as improvement opportunities
- Be honest — do not inflate scores to be encouraging
- The hire signal should reflect readiness today, not potential
- The "oportunidades" fields are the most valuable coaching output — make them concrete