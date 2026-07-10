# Career Evidence Board

*CodeForge's proof board: real software-career skills, the exact repo artifact that proves
each, and the honest gaps. Not decoration - a proof board.*

## In the MUD

The **Career Evidence Sign** hangs in *The Forge Workshop*. Render it with `career`:

| Command | Shows |
|---------|-------|
| `career` | Overview: readiness-at-a-glance counts + how to use |
| `career checklist` | Full board - every skill, all levels |
| `career gaps` | Only the partial/missing items - the next-proof-task list |
| `career evidence` | Skills with their repo proof paths |
| `career resume` | Resume-translation language (generated from proven skills) |
| `career role entry\|intermediate\|advanced` | One level's checklist |

## The data

The board is data-driven: `data/career/career_evidence_matrix.json` holds levels → target
roles → skills, each with `status`, `repo_proof[]`, `why_it_matters`, and `next_proof_task`.
`parts/career.py` loads and renders it; `docs/resume_mapping.md` is the prose companion.

## The honesty rule (VeritasGate)

A skill is only `proven` or `partial` if at least one cited `repo_proof` path **actually
exists on disk**. `tests/test_career.py` enforces this - mark something proven without the
artifact and the suite goes red. Status vocabulary: `proven · partial · missing · planned
· needs_update · human_review_required`. The board says **readiness, never certification**,
and it names its own gaps.

## Research basis

Grounded in BLS 2024 medians (Software Developers $133,080 · QA/Testers $102,610 ·
Technical Writers $91,670; ~317,700 CS/IT openings/yr through 2034), O*NET work styles, and
current public postings (Roblox, Extreme Networks, Wyetech, Veeva, BioIntelliSense, PlayOn,
Xsolla). CodeForge's strongest overlap: **internal tools · release/build · DevOps/SRE · QA
automation · technical documentation.**

## Maintaining it

Manually maintained for now: when you ship an artifact that closes a gap, flip that skill's
`status` and add the `repo_proof` path. A future `career scan` command could suggest updates
by scanning the repo - but it must **never auto-mark a skill proven without human review.**
