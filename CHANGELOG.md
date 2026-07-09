# Changelog

All notable changes to CodeForge. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); versions are date-stamped while
pre-1.0. Readiness language only — no compliance/OSHA/legal claims.

## [Unreleased]

### Added
- **PM control panel** (`parts/pm.py`): `pm status` / `pm metrics` — the project
  dashboard is *computed* from the registry + QualityGate (part + part + part), not
  stored. `docs/project_management.md` holds the charter, milestone status, backlog,
  risk register, decision log, and one worked DMAIC. Scope control: this prompt's
  full PMO + Lean-Six-Sigma/ADDIE systems were *deferred as backlog*, not built.
- **Safety + QA spine** (`parts/qualitygate.py`): `QualityGate` grades any filed
  object (purpose · file · tests · docs · maturity-honesty → `pass|watch|fail`),
  `SafetyReview` rates risk, `DocumentationImpactSweep` sweeps the key docs. New
  read-only MUD commands `qa gate [all|<id>]`, `safety review <id>`, `docs check`.
  Proof of composition: `qa gate all` audits the whole registry (part + part).
- **`docs/safety_qa_system.md`** — the Safety + QA architecture.
- **`@sg item <pattern>`** — admin (wizard+) item generator on the command spine;
  data-driven patterns (`catalog/items.yaml`), traced to `ITM-*`, refuses the unknown.
- **Command spine** (`parts/commands.py`): namespaced (`CORE` / `ADMIN @` / `SEED`),
  rank-gated `Command` + `CommandSet`; `registry` verbs proven on it.
- **Classification Registry** (`parts/registry.py` + `registry/`): designations
  (`TYPE-UM-SEC-NODE-SEQ-REV`), 18 rooms + commands + items filed, schema + rules doc.
- **In-game Library** (`parts/library.py`): `library` / `library <id>` read FGL's
  document store read-only; the Archivist NPC.
- **Ritual WARDS**: the startup ritual now runs SAST (bandit gates) + dependency-CVE
  scan (pip-audit warns) before lighting the forge. `.github/dependabot.yml` added.

### Notes
- Designations are additive backend metadata keyed to frozen runtime labels; labels,
  CLI verbs, DB columns, and YAML keys are never renamed.
