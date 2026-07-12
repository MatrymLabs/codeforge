# Repository Maturity Scorecard (and an honest hireability read)

*One honest page, not twenty-two governance documents. This scores CodeForge against the bar a hiring
manager actually applies, names what is genuinely strong, and names the one real risk. It is the
answer to a fleet-hardening research menu: implement the artifact that matters, decline the dump.*

## The hiring bar, scored

| Dimension | Status | Evidence |
|-----------|--------|----------|
| Runs in 5 minutes | **strong** | live Render demo linked in the README; `make check`; browser gateway |
| README (purpose / install / run / test) | **strong** | value prop, demo GIF, badges, quickstart, honest vision labeling |
| CI green + automated tests | **strong** | GitHub Actions all-green; **1111 tests**; property + fuzz markers |
| Coverage | **strong** | ~94% branch coverage, codecov badge (truthful) |
| Lint + types | **strong** | ruff + mypy clean, pinned, in CI |
| Security tooling | **strong** | bandit, pip-audit, CodeQL, detect-secrets, SBOM, OpenSSF Scorecard badge |
| Dependency discipline | **strong** | stdlib-first rule, dependency ledger, `make deps` gate |
| Licensing + provenance | **strong** | MIT, CITATION.cff, per-part provenance (harvested / independent / original) |
| Architecture notes | **strong** | 7 ADRs, C4 doc, naming standard |
| Collaboration signal | **strong** | every change is a branch -> PR -> CI -> merge (solo is fine) |
| Presentation | **good** | pinned repos + portfolio index are UI-only, done outside this repo |
| **Focus / restraint** | **watch** | see the risk below |

By this bar, CodeForge is **hireable now**. The mechanical portfolio work is done.

## What is genuinely strong

A real, playable, tested product with a live demo; a self-auditing engineering stack that actually
runs (`arc`, `harvest`, `clones`, `complexity`, `learnings`); a clean branch->PR->CI->merge history;
and honest evidence everywhere (readiness, never certification). This is not a toy.

## The one real risk: sprawl reading as process-over-product

CodeForge carries **98 docs and 117 parts**, and a growing set of meta-verbs about the codebase
itself. Each was built well and tested, but in aggregate they carry a hireability *cost*: an
interviewer skimming for "can this person ship?" can mistake the volume of governance for an absence
of product. The mitigation is not to delete good work; it is to **stop adding meta-machinery** and
keep the product (the MUD engine + the demo) the loudest thing in the repo.

Maturity is not tool count. It is the right controls, present, understood, tested, maintained, and
evidenced - and CodeForge already has the right ones.

## The down-to-earth verdict on fleet hardening

The 30-priority fleet-hardening research list is a **menu, not a build order** (it says so itself:
"do not tell the AI to apply everything"). Producing 22 fleet-governance documents for a solo
portfolio would deepen the sprawl risk above, not fix it. So:

- **Declined for this repo:** a `FLEET_ENGINEERING_STANDARD.md` and the 21 other baseline documents.
  CodeForge already satisfies the hireable subset of those 30 priorities (security, testing, CI,
  licensing, dependencies, architecture, supply-chain evidence).
- **If pursued at all,** fleet-wide governance belongs **once** at the ship level (the `MatrymLabs`
  repo), not multiplied into every repo, and staged behind evidence - never dumped.
- **Deferred by design** (the plan already says so): Kubernetes, Terraform, multi-language adapters,
  and advanced infra. Adopt them when a repo needs their operating model, not for appearance.

## Next real levers (small, outward-facing)

1. Keep the product the headline: the demo and the engine, not the meta-verbs.
2. Any new work earns its place against this bar, or it does not ship.
3. The remaining presentation items (repo pinning, profile polish) are UI-only and live outside the
   codebase.

The honest bottom line: **CodeForge is already at the hiring bar. The highest-value engineering
decision right now is restraint.**
