# Resume Mapping - CodeForge → the job market

*How the work in CodeForge translates to resume language and target roles. Evidence-based:
every claim maps to a repo artifact (see the [Career Evidence Sign](#the-career-evidence-sign)).*

## One-line thesis

> CodeForge demonstrates the ability to design and run Python software systems using
> automation, documentation, testing, AI-assisted development, reusable tooling, and
> evidence-based engineering discipline.

## The three market narratives (from the BLS/O*NET-grounded research)

CodeForge's strongest overlap is **not** generic "junior coder" work - it's the
intersection of **internal tools · release/build · DevOps/SRE · QA automation · technical
docs**. Lead with these three, in your own words:

1. *"I build reusable Python tooling and automation that reduce manual work."*
2. *"I improve release/testing reliability through checklists, diagnostics, and CI discipline."*
3. *"I can document complex systems clearly enough for other engineers to use and maintain them."*

## Key evidence areas (each backed in-repo)

| Resume phrase | Repo proof |
|---|---|
| Python project structure & testing | `parts/`, `tests/`, 90%+ coverage, `make check` |
| Command automation / internal tooling | `Makefile`, `scripts/ritual*.sh`, the `career`/`pm`/`truth` commands |
| Diagnostic ritual design (fast/standard modes) | `docs/startup_ritual.md`, `scripts/ritual_fast.sh`, saved after-action records |
| Release/readiness discipline | shutdown push-ready gate, CI-green-before-merge |
| Testing & verification | test twins, coverage gate, `make smoke` |
| CI/CD & security tooling | `.github/workflows/ci.yml` + `codeql.yml`, bandit · pip-audit · SBOM |
| Technical documentation | `docs/` (ADRs, architecture, ritual, debugging case study) |
| Reusable-part cataloging | `catalog/`, the hardware store |
| Software architecture / decisions | `docs/adr/`, `docs/architecture.md`, `docs/seed_architecture.md` |
| QA & safety thinking | QualityGate, VeritasGate, allowlisted console (never raw shell) |
| Truth between docs & code | `truth check` (VeritasGate), this evidence board |
| AI-assisted development, reviewed | `docs/AI_WORKFLOW.md` - AI as force multiplier, gated by tests |

## Target role clusters (from current public postings)

- **Entry:** Entry Software Engineer · Junior Python Developer · Software Tools Engineer 1 ·
  Associate Test Engineer · Technical Writer.
- **Intermediate:** Release Engineer · DevOps Engineer · QA Automation Engineer · Software
  Engineer in Test · Python Automation Developer.
- **Advanced (aspirational):** Senior SRE · Lead Tools Engineer · Platform/Systems Engineer.

## The Career Evidence Sign

In the MUD, `career` (in The Forge Workshop) renders this board live from
`data/career/career_evidence_matrix.json`. `career gaps` shows exactly what to build next.
The board obeys VeritasGate: a skill is only `proven` when a cited repo artifact actually
exists - so it can name its own gaps honestly. **Readiness, never certification.**
