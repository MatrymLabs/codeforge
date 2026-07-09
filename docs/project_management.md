# CodeForge — Project Management

*The control panel that keeps CodeForge climbing the stairs. One file, on purpose —
we don't build a PMO before the workshop door opens.*

Live status is **computed, not stored**: type `pm status` in the MUD (it reads the
registry + runs the QualityGate). This doc holds the narrative plan the code can't
derive: charter, milestones, backlog, risks, decisions.

---

## Project charter

- **Vision:** a Python-native MUD-shaped engineering holodeck + reusable-code
  hardware store, built as a portfolio-grade, self-auditing engine.
- **Primary constraint:** beginner-safe development with professional engineering
  discipline (branch → `make check` green → CI green → merge).
- **Current phase:** the *engine spine is composing* — registry + command spine +
  QualityGate + PM dashboard all plug together. (`pm status` for the live number.)
- **Success criterion:** a vertical slice that launches, enters the Workshop, reads
  stored guidance, files every object, audits itself, and reports readiness — done.

---

## Milestone status (mapped to what is actually filed)

| Milestone | State | Evidence |
|-----------|-------|----------|
| M0 Project control | **done** | this doc + registry + `pm status` |
| M1 MUD spine | **done** | 18 rooms filed; player moves the spine |
| M2 Workshop MVP | **done** | workshop/observatory/vault/console rooms + commands |
| M3 Library + Classroom | **done** | `library`/`library <id>`, Professor Codex, lesson loop |
| M4 Hardware Store MVP | *partial* | `catalog/parts.yaml` exists; `PRT` parts not yet filed |
| M5 Safety + QA spine | **done** | QualityGate, SafetyReview, DocumentationImpactSweep |
| M6 AI NPC advisory | *partial* | local Architect NPC (`ai`); no external API |
| M7 Portfolio-ready | *in progress* | README, live demo, CI badges; CHANGELOG new |

---

## This prompt's two systems — scoped, not built (scope control)

The PM + Lean-Six-Sigma/ADDIE prompt describes two large systems. Per the prompt's
own rule ("prevent building the dragon before the door opens"), only the **PM
dashboard MVP** was built. The rest is filed backlog:

| Backlog item | Track | Priority | Depends on | Effort |
|--------------|-------|----------|-----------|--------|
| `pm status` / `pm metrics` (computed dashboard) | 11 | **P0 — DONE** | registry, QualityGate | S |
| Charter/milestones/risks doc (this file) | 11 | **P0 — DONE** | — | S |
| File `PRT`/`MOD` code parts in the registry | 4/5 | P1 | registry | M |
| Link `docs` paths on records (close QG04) | 8 | P1 | — | S |
| EvidenceLedger (save gate/review results to `reports/`) | 8 | P1 | QualityGate | M |
| ADDIE lesson template + 1 Python lesson (registry validator) | 7 | P2 | AssessmentEngine | M |
| Quiz quit/pause/resume hardening | 7 | P2 | classroom | S |
| Lean Six Sigma DMAIC/SIPOC records + `lss` verbs | 8 | P3 | metrics | L |
| Full PMO (WBS/Gantt/sprints/change-control files) | 11 | P3 | — | L |
| Master Kaizen NPC, `pm`/`addie`/`lss` command families | 7/8 | P4 | above | L |

**Rule in force:** no new track starts until the current milestone's gaps close.

## Recommendations captured 2026-07-09 (saved, not yet built)

A big prompt-driven session. These are the open recommendations, honestly prioritized.
Several big-sounding prompts turned out to be **mostly already built** — the note says so.

| # | Recommendation | Why / origin | Priority | Effort |
|---|----------------|--------------|----------|--------|
| R1 | **Secret scanning** — add `make secrets` (detect-secrets, baselined) + a `.secrets.baseline`; optional gitleaks | the RepoIntegrityRitual's own #1 action — closes the one honest gap it surfaces (`not_configured`); other ship repos already carry it | **P1** | S–M |
| R2 | **Close QG04 → green board** — link `docs` paths on registry records so `pm status`/`qa gate` go green | the dashboard is literally asking for it (LSS-CF-001 DMAIC) | **P1** | S |
| R3 | **Ritual modes + saved reports** — `make ritual-start-fast/deep`, a structured startup/shutdown report saved under `reports/ritual/`, a shutdown **commit/push-readiness** gate | the Startup/Shutdown prompt's *real delta*; the ritual **spine already exists** (ritual.sh WARDS/READINESS + ritual_down MUSTER) — this is modes + evidence, NOT the 19-phase Python CLI / workshop-lock cathedral (deferred) | P2 | M |
| R4 | **VeritasGate `truth check`** command — automate the manual truth audit (README/docs/registry claims) | truth prompt; composes `docs_check` + registry validate | P2 | S |
| R5 | **forge-audit MVP** — run the gates on a *target* repo behind a mockable GitHub-API seam, emit a JSON scorecard | the `DEVELOPMENT_PLAN`'s one net-new flagship build | P2 | **L** |
| R6 | **Portfolio index page (GitHub Pages)** — link flagship + live demo + a case study | presentation is a hiring gate | P2 | M |
| R7 | **Build one prototype city room real** (e.g. City Square) | advances the game/world; seeds-are-data | P3 | S |

Still open from the earlier backlog table: EvidenceLedger, ADDIE lesson #1, LSS DMAIC
records, filing `PRT`/`MOD` parts. **Recommended first move:** R2 (green board) or R1
(secret scanning) — both small, both close a gap a tool already flagged.

---

## Risk register (top 3)

| ID | Risk | P×I | Mitigation |
|----|------|-----|-----------|
| RISK-CF-001 | **Scope creep** — building many systems at once | high×high | milestones + "no new track" rule; this prompt's two towers were *deferred*, not built |
| RISK-CF-002 | Undocumented objects (31 watch on QG04) | med×med | see the DMAIC below; `pm status` surfaces it every run |
| RISK-CF-003 | Overclaiming (OSHA/compliance/certification) | low×high | readiness language only; enforced in `qualitygate.py` copy + these docs |

---

## Decision log (key, this session)

- **DEC-CF-010** Designations are additive backend metadata keyed to frozen labels
  (never a rename). *Consequence:* save files/seeds/CLI stay stable.
- **DEC-CF-011** Admin sigil is `@`; seeds own bare-word verbs; `guard_seed_verbs`
  blocks shadowing. *Consequence:* `forge` stays free for every seed.
- **DEC-CF-012** PM state is *computed* from the registry + QualityGate, not stored.
  *Consequence:* no second source of truth to drift.

---

## One Lean Six Sigma DMAIC (a real finding, worked)

**LSS-CF-001 — Reduce undocumented filed objects.**

- **Define:** filed objects have code + tests + a purpose, but no linked docs page.
- **Measure:** `qa gate all` → **31/31 objects `watch` on QG04** (docs link missing).
- **Analyze (5 Whys):** no docs field populated at filing → filing script didn't set
  it → the schema made `docs` optional → docs weren't a gate at creation time.
- **Improve:** populate `docs` on records (point rooms at a world-map page, parts at
  their card), and/or write the missing `docs/*.md` pages.
- **Control:** `qa gate all` (QG04) + `pm status` surface the gap on every run; a
  future ritual step can print it at startup.

This is the template: every `lss` improvement is Define→Measure→Analyze→Improve→
Control, with the metric coming from `pm metrics` and the control from the QA gate.

---

## Definition of Done (every task)

Code/content exists · registry entry if applicable · tested or manually verified ·
docs impact checked (`docs check`) · relevant docs updated · CHANGELOG updated if
behavior changed · risks updated if needed · next dependency clear. No compliance
claims — readiness only.
