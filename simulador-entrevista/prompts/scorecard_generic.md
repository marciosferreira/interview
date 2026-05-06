# Final Scorecard

You have the full interview transcript AND the per-phase feedback reports in your context.
Each phase report was generated immediately after that phase ended.
You also have a list of accumulated language errors collected across all phases.

Use all of this to generate a comprehensive, honest, and constructive final scorecard.
Do not re-evaluate from scratch — build on the per-phase reports. Cross-reference them with the raw conversation to add insight the reports may have missed.

---

## Context — What the Role Is Evaluating

Refer to the CANDIDATE & JOB CONTEXT section for what this specific role requires.

The interview ran approximately 35 minutes across 6 phases:
- Phase 1 — Elevator Pitch: ~2 min
- Phase 2 — CAR Project Story: ~5 min
- Phase 3 — Technical Questions: ~10 min
- Phase 4 — Leadership & Project Approach: ~8 min
- Phase 5 — Fit & Motivation: ~5 min
- Phase 6 — Candidate's Questions: ~5 min

The hire signal must reflect whether the candidate is ready for the **real interview today** — not their potential. A candidate with excellent technical content but poor communication is NOT ready for a role where client communication is required. Adjust accordingly.

---

## Scoring Guide

- **5** — Excellent: exceeded expectations, specific, evidence-based, strong communication
- **4** — Good: met all criteria, minor gaps
- **3** — Adequate: covered the basics but lacked depth or had notable language issues
- **2** — Weak: missing key elements or communication significantly impacted clarity
- **1** — Not acceptable: answer did not address the question or was incomprehensible

---

## Field Instructions

**score_pitch / score_CAR / score_technical / score_leadership / score_motivation** (int 1–5)
Integer score using the guide above.

**comentario_pitch / comentario_CAR / comentario_technical / comentario_leadership / comentario_motivation** (str)
One sentence: strongest element + biggest gap. Reference what the candidate actually said.

**oportunidades_pitch / oportunidades_CAR / oportunidades_technical / oportunidades_leadership** (list of str)
2–4 bullet points per phase: things the candidate had the background to mention but didn't.
Start each with "You could have mentioned…". Be specific — reference their real experience from CANDIDATE & JOB CONTEXT.
Draw from the per-phase reports AND any additional gaps you notice in the raw conversation.

**vocabulario_para_praticar** (list of str)
4–6 entries combining all phases.
Format each as: "[term/phrase] → [why it matters]"
Prioritize terms the candidate avoided or weakened across multiple phases.
Draw from the "VOCABULARY & FRAMING" sections in the per-phase reports.

**ingles_rating** (str)
One of: "Fluent" / "Mostly Fluent" / "Needs Work"
Base this on the accumulated language error list AND the language feedback in per-phase reports.

**ingles_padroes** (list of str)
2–3 recurring patterns to fix. Each entry should include a concrete example from the interview.
Consolidate across all phases — focus on patterns that appeared more than once.

**score_total** (int)
Sum of the 5 phase scores.

**hire_signal** (str)
One of: "Strong Yes" / "Yes" / "Borderline" / "Not Yet"
Reflect whether the candidate is ready for the real interview today, not their potential.
Critical: communication quality is a hard gate — a candidate who rates "Needs Work" on language cannot be "Strong Yes" or "Yes" for a role requiring client-facing communication.

**forcas** (list of 2 str)
Top 2 concrete strengths with specific examples from the interview.

**melhorias** (list of 2 str)
Top 2 highest-leverage improvements before the real interview. Actionable, specific.

**insight_chave** (str)
Single most important insight — the one thing that could make or break their real interview.
Be direct and honest.

---

## Instructions

- Be specific — reference actual things the candidate said (or didn't say)
- Be constructive — frame weaknesses as improvement opportunities
- Be honest — do not inflate scores to be encouraging
- The hire signal should reflect readiness today, not potential
- The "oportunidades" fields are the most valuable coaching output — make them concrete
