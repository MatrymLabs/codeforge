# CodeForge Safety + QA System

*A global operating layer: every important object is named, classified, tested,
risk-rated, and provable - or it's honestly flagged as not-yet-ready.*

This is **OSHA-informed**, not OSHA-certified. It reports **readiness**, never
compliance. It makes no OSHA / ISO / CMMC / legal / financial / audit claim - those
require verified evidence and qualified human review. Where it cannot prove
something, it says so (`watch`, `fail`, "manual review recommended").

## The idea (and the proof of concept)

CodeForge already files every object in the **Classification Registry** (a *part*).
The Safety + QA spine is a second *part* that **plugs into the first**:

```
QualityGate ∘ registry  =  a self-audit
```

`qa gate all` reads every filed designation and grades each one. That composition -
**part + part = a new capability** - is the whole thesis: the engine can take the
pieces it already has and assemble a system that checks its own work, without
hand-writing a bespoke auditor. See it: type `qa gate all` in the MUD.

## The four questions (the readiness model)

| Lens | Asks |
|------|------|
| **Safety** | Can this hurt someone, expose risk, or create unsafe behavior? |
| **QA** | Did this meet the standard? |
| **Documentation** | Can someone understand and maintain it? |
| **Evidence** | Can we prove what happened? |
| **The Ritual** | Is the system still healthy today? |

## The parts (Hardware Store components)

| Part | File | What it does | Maturity |
|------|------|--------------|----------|
| **QualityGate** | `parts/qualitygate.py` | grades one object (purpose · file · tests · docs · maturity-honesty) → `pass \| watch \| fail` | active |
| **SafetyReview** | `parts/qualitygate.py` | rates risk from type/tags → `low \| medium \| high \| critical`, flags approval | active |
| **DocumentationImpactSweep** | `parts/qualitygate.py` (`docs_check`) | which key docs exist vs. missing | active |
| *(planned)* EvidenceLedger | - | dated proof of tests/reviews/approvals | prototype |
| *(planned)* NonconformanceLog / CorrectiveActionTracker / SafetyHazardLog | - | track QA failures, fixes, hazards | prototype |

### QualityGate checklist

| ID | Requirement | Kind |
|----|-------------|------|
| QG01 | Has a clear purpose | soft |
| QG02 | Source file exists (n/a for prototypes) | **hard** |
| QG03 | Has tests (n/a for prototypes) | **hard** |
| QG04 | Has documentation (a docs path or notes) | soft |
| QG05 | Evidence supports the declared maturity (`active`/`hardened` ⇒ file + tests exist) | **hard** |

A **hard** gap fails; a **soft** gap watches. A `prototype` is exempt from build
checks - it's honestly marked "not built yet," never failed for it.

### SafetyReview risk model

Admin/system objects (`@`-verbs, `SYS`) → **medium**, human approval flagged
(enforced in code by `min_rank`). Item generation → player-state category.
Prototypes → untested-behavior. Read-only objects → **low**. High/critical would
require human approval *before* implementation.

## MUD commands (read-only, on the command spine)

```
qa gate all            grade every filed object (the self-audit)
qa gate <designation>  one object's full checklist
safety review <id>     one object's risk rating
docs check             sweep the key docs for gaps
```

Each command is itself filed as a `CMD-*` designation, so `registry type CMD` lists
the QA verbs alongside every other command.

## Boundaries (hard rules)

- No OSHA/ISO/CMMC/legal/financial/audit **compliance** claims - readiness only.
- AI summaries are **not** source truth; stored source documents are.
- No secrets to external APIs; no unapproved file edits; no auto-deletion of records.
- Never overwrite an official PDF without archiving the old copy.

## Staircase (what's built vs. next)

- **Built (MVP spine):** QualityGate, SafetyReview, DocumentationImpactSweep, the four
  MUD commands, this doc, and `qa gate all` proven over the real registry.
- **Next:** EvidenceLedger (save dated gate/review results under `reports/qa/`),
  the ritual's global readiness report (fold `qa gate all` + `docs check` into
  `start the ritual`), NCR/CAPA/Hazard logs, and filing the reusable parts (`PRT`)
  and modules (`MOD`) so the audit covers code, not just rooms/commands/items.
