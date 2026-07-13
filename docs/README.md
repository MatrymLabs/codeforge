# CodeForge docs, mapped

The one map to everything under `docs/`. New here? Read [RUNNING.md](RUNNING.md), then
[architecture.md](architecture.md).

## Getting started
- [RUNNING.md](RUNNING.md), how to start the servers, log in, and run the ritual.
- [../README.md](../README.md), the project overview and what it demonstrates.
- [../CONTRIBUTING.md](../CONTRIBUTING.md), setup and the workshop rules.

## Architecture and decisions
- [vision_resync.md](vision_resync.md), the one product vision: CodeForge as a two-output manufacturing platform (World Package + Hardware Store), the three layers, the manufacturing loop, honest working/prototype/planned labels, and the first vertical slice.
- [optimization_ethos.md](optimization_ethos.md), the Matrym optimization ethos: turn solutions into infrastructure (the loop, the optimization ladder, the evidence standard, the Expansion Review, the critical-junction rule).
- [convergence_review.md](convergence_review.md), the Convergence Review (internally the Lemonade Protocol): a repeatable interdisciplinary review method that transfers mature practices across disciplines and classifies gaps by mechanism, not label.

- [architecture.md](architecture.md), the engine tick, drivers, and canonical state.
- [adr/](adr/), Architecture Decision Records (0001 canonical state, 0002 derive-don't-store, 0003 framework-free).
- [frameless_python.md](frameless_python.md), the architecture-first identity: stdlib + my architecture as the spine, frameworks as integrations that earn their place.
- [tooling_strategy.md](tooling_strategy.md), how a tool earns its place: the decision matrix, review template, and dependency-approval rule.
- [full_stack_forge_decision.md](full_stack_forge_decision.md), the full-stack framework decision (custom core + FastAPI + custom renderers; Django/Evennia/React deferred).
- [framework_decision_matrix.md](framework_decision_matrix.md), the scored path comparison + tool status labels.
- [seed_architecture.md](seed_architecture.md), seed pack vs cast, the detachment plan.
- [naming_glossary.md](naming_glossary.md), the forge vocabulary.
- [classification/](classification/), the designation / registry system.

## The game systems
- [character_system.md](character_system.md), the character system end to end: jobs, attributes, XP/JP/TP progression, combat + the Engineer's kit, equipment, resistances, the score sheet and its display modes. Both a player guide (the commands) and an author guide (the data schema + the derived-stat pipeline).

## The self-audit systems (how the machine grades itself)
- [frame_up.md](frame_up.md), `inspect`, the on-demand green/yellow/red frame-up (the audit hub) + the ReportWriter.
- [veritas.md](veritas.md), `truth check`, claims vs reality (no claim without correspondence).
- [safety_qa_system.md](safety_qa_system.md), QualityGate + SafetyReview.
- [repo_integrity.md](repo_integrity.md), `make repo-integrity`, the composite health report.
- [performance.md](performance.md), `make bench`, the engine-tick throughput/latency benchmark (performance evidence).
- [dashboard.md](dashboard.md), the readiness Lens: a server-rendered web dashboard (`GET /`) + JSON twin (`GET /api/status`) over real forge evidence (the full-stack proof).
- [blueprint_renderer.md](blueprint_renderer.md), the forge's planning spine: idea -> validated Blueprint (JSON + Markdown) -> static HTML page (`blueprint` verb).
- [architect_brain.md](architect_brain.md), the Architect NPC's swappable brain: local rule-based guide today, Claude-backed one an API key away (the seam, tested with a fake).
- [database.md](database.md), persistence: SQLite by default, PostgreSQL (`DATABASE_URL`) for production, with Alembic migrations and a docker-compose Postgres.
- [configuration.md](configuration.md), the typed, validated environment catalog (pydantic `Settings`); the `config` terminal program renders it (secrets redacted).
- [observability.md](observability.md), structured request logs (structlog) + a Prometheus `/metrics` endpoint, wired on with one HTTP middleware.
- [project_management.md](project_management.md), `pm status`, backlog, risks, decisions, one worked LSS DMAIC.

## Research to build (the First Rule in action)
Each of these translates one captured research report into a real, tested subsystem. They share one honest template on purpose (evidence labels first, then a mapping table, then how the build composes with existing gates, then metrics, then APA references), but every table, source list, and domain is its own. Nature inspires / a clinical pattern suggests / an assurance report warns; engineering translates; tests verify; metrics compare; Josh decides. A metaphor is never presented as proof.
- [nature_inspired/research_mapping.md](nature_inspired/research_mapping.md), Nature-Inspired Design -> the Blueprint Evolution Lab (`parts/evolution/`): genotype/phenotype, candidate populations, multi-objective fitness (hard gates first), the counterexample bank.
- [stewardship/research_mapping.md](stewardship/research_mapping.md), FWA-reduction assurance -> the Stewardship Gate + DependencyGate (`parts/stewardship/`): layered, executable controls that do not tax low-risk work.
- [hubble/research_mapping.md](hubble/research_mapping.md), clinical workflow patterns -> the Hubble diagnostic core (`parts/hubble/`): differential diagnosis before intervention, with non-overridable escalation classes.

## Ritual and process
- [startup_ritual.md](startup_ritual.md), the startup ceremony, fast/standard modes, the phases.
- [shutdown_ritual.md](shutdown_ritual.md), the close ceremony and the push-readiness gate.
- [pioneer_mode.md](pioneer_mode.md), bold-but-honest engineering: the risk ladder and constraint review.

## Career and evidence
- [career_evidence_board.md](career_evidence_board.md), `career`, skills mapped to repo proof.
- [keel_records/](keel_records/), the Human Keel Records that back level 4 (defendable) ownership claims: intent, decision, AI contribution vs human modification, evidence (the KeelGate requires one on disk before any portfolio ownership claim).
- [hiring_requirement_matrix.md](hiring_requirement_matrix.md), 2026 hiring requirements mapped to repo evidence.
- [github_portfolio_checklist.md](github_portfolio_checklist.md), honest pass against the ideal-repo checklist.
- [full_stack_readiness_checklist.md](full_stack_readiness_checklist.md), backend/frontend readiness, honestly labeled.
- [research/](research/), the captured 2026 hiring / portfolio / full-stack research (the First Rule).
- [resume_mapping.md](resume_mapping.md), how the work translates to resume language.
- [DEBUGGING.md](DEBUGGING.md), a debugging case study (the dead-sink heisenbug).
- [AI_WORKFLOW.md](AI_WORKFLOW.md), how AI is used, and how it stays honest.

## Domain awareness
- [legal_policy_awareness.md](legal_policy_awareness.md), `law`, tracked sources (never legal advice).

## Templates and filed evidence
- [runbook_template.md](runbook_template.md) / [postmortem_template.md](postmortem_template.md), operational templates.
- [postmortems/](postmortems/), filed blameless postmortems.
- [pioneer_experiments/](pioneer_experiments/), filed bold-experiment reports.
- [reports/](reports/), the runtime-evidence README (generated reports are git-ignored, reproducible).

## Vision (planned, labeled as such)
- [proving_ground/](proving_ground/), the workshop/proving ground roadmap and safety notes.

## Logs
- [CAPTAINS_LOG.md](CAPTAINS_LOG.md), the flagship's engineering log.
