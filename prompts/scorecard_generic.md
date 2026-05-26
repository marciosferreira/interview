# Final Scorecard

You will receive a compact evaluation package — NOT the raw interview transcript. It contains:

1. **Per-Phase Reports** — one distilled report per phase, generated immediately after each phase ended by a specialist evaluator. These are your primary source.
2. **Observer Notes** — structured observations accumulated in real time during each phase.
3. **Evaluation Checklists** — boolean pass/fail criteria checked during each phase.
4. **Accumulated Language Errors** — English errors flagged across all phases.

Build the scorecard from this package. Do not attempt to reconstruct the raw conversation — work from what the evaluators already captured.

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
Integer score using the guide above. Base on the phase report score and checklist.

**comentario_pitch / comentario_CAR / comentario_technical / comentario_leadership / comentario_motivation** (str)
One sentence: strongest element + biggest gap. Reference what the phase report captured.

**oportunidades_pitch / oportunidades_CAR / oportunidades_technical / oportunidades_leadership** (list of str)
2–4 bullet points per phase: things the candidate had the background to mention but didn't, or role-relevant points they should have covered.
Start each with "You could have mentioned…". Be specific — reference their real experience from CANDIDATE & JOB CONTEXT when available.
If no background was provided in CANDIDATE & JOB CONTEXT, base opportunities on concrete details the candidate shared during the interview and role-relevant expectations instead.
Draw from the per-phase reports and observer notes.

**vocabulario_para_praticar** (list of str)
4–6 entries combining all phases.
Format each as: "[term/phrase] → [why it matters]"
Prioritize terms the candidate avoided or weakened across multiple phases.
Draw from the "VOCABULARY & FRAMING" sections in the per-phase reports.

**ingles_rating** (str)
One of: "Fluent" / "Mostly Fluent" / "Needs Work"
Base this on the accumulated language error list AND the language feedback in per-phase reports.

**ingles_padroes** (list of str)
2–3 recurring patterns to fix. Each entry should include a concrete example.
Consolidate across all phases — focus on patterns that appeared more than once.

**score_total** (int)
Sum of the 5 phase scores.

**hire_signal** (str)
One of: "Strong Yes" / "Yes" / "Borderline" / "Not Yet"
Reflect whether the candidate is ready for the real interview today, not their potential.
Critical: communication quality is a hard gate — a candidate who rates "Needs Work" on language cannot be "Strong Yes" or "Yes" for a role requiring client-facing communication.

**forcas** (list of 2 str)
Top 2 concrete strengths with specific examples from the phase reports.

**melhorias** (list of 2 str)
Top 2 highest-leverage improvements before the real interview. Actionable, specific.

**insight_chave** (str)
Single most important insight — the one thing that could make or break their real interview.
Be direct and honest.

---

## Instructions

- Be specific — reference actual observations from the phase reports and notes
- Be constructive — frame weaknesses as improvement opportunities
- Be honest — do not inflate scores to be encouraging
- The hire signal should reflect readiness today, not potential
- The "oportunidades" fields are the most valuable coaching output — make them concrete
