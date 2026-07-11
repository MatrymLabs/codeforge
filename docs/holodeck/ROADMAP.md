# Holodeck Roadmap - the staircase

A staircase, not a cliff. Each phase is a shippable slice with a **definition of
done**. Don't build the dragon before the workshop door opens; don't build advanced
industry systems before the catalog can track simple parts. Every phase runs behind
the guarantees in [`SAFETY.md`](SAFETY.md).

Legend: ✅ done · 🔨 next · 📋 planned · 🧭 later (gated/advanced)

## Phases

| # | Phase | State | Done looks like |
|---|-------|-------|-----------------|
| 1 | **Startup ritual** | ✅ | `make ritual` checks env, gates, lights the forge, opens the MUD; `ritual-down` secures it. |
| 2 | **Workshop room** | ✅ | The `workshop` room (off the cellar) is furnished as the engineering cockpit; walk in after login. |
| 3 | **Workshop command menu** | ✅ | The `workshop` cockpit now advertises its real live tools: `catalog`/`hardware`/`parts`, `reuse <term>`, `blueprint` (browse/show/render/draft), `ai <prompt>`, and `console`/`diagnostics`/`security`. Only `patch proposal` and `arch` remain "coming" (the file-editing phases). |
| 4 | **Hardware catalog** | ✅ | `catalog/parts.yaml` + `parts/hardware.py`; `make hardware` lists parts with cross-domain reuse; ≥4 real parts stocked. |
| 5 | **AI NPC (read-only)** | 🟡 | `parts/architect.py`: `ai <prompt>` in-world. A **local rule-based** Architect navigates you to the right command/part today, behind a swappable `Advisor` seam; a Claude-backed brain drops in next (same interface, redacted context, key from env, mocked in tests). Advisory only - no edits, no execution. |
| 6 | **Diagnostic console** | ✅ | `parts/console.py` (`FailsafeRunner`) runs an **allowlisted, read-only** set as argument lists (no shell), under a timeout + output cap, each run logged. In-world: `console`, `run <check>`, `diagnostics`. Refuses anything off the list. |
| 7 | **Report system** | ✅ | `parts/reporting.py` (`write_report`) files dated evidence under `reports/<kind>/`; used by the bench, frame-up, repo-integrity, and blueprint renderers. |
| 8 | **AI planning mode** | ✅ | `blueprint` drafts a structured plan: `blueprint draft <idea>` uses the Claude Architect (schema-enforced `messages.parse`) to author a Blueprint, re-validated through the same gate and always a Tier-4 draft. `parts/blueprint_ai.py`, no direct edits. |
| 9 | **Safe patch proposal** | 🧭 | The NPC emits a `PatchProposal`: file, why, affected part, catalog update, risk, test, revert. **Human approval required.** |
| 10 | **Controlled generation** | 🧭 | Only now may the system write files - always: branch first → plan → diff → tests → evidence → rollback path. |
| 11 | **Full engineering loop** | 🧭 | Request → search parts → clarify → blueprint → approve → generate → test → diagnose → fix → document → catalog → commit summary → evidence, all from the Workshop. |
| 12 | **Industry expansion** | 🧭 | The catalog's `reuse` tags grow into tracks (gov / finance / compliance / records) - the *framework* for it exists; parts opt in over time. |

**Discipline:** phases 8-11 are where the AI touches files. They are deliberately
last and each is gated by [`SAFETY.md`](SAFETY.md). We do not skip ahead.

## Command plan

In-world (MUD) commands and the terminal commands they front. Early commands are
**display-only**; anything that acts goes through the safe runner (Phase 6) and, if
it mutates, an approval gate (Phase 9).

| In-world | Does | Fronts / becomes |
|----------|------|------------------|
| `workshop` | Enter/describe the Workshop | - |
| `status` | Repo + env snapshot | `git status`, env check (read-only) |
| `catalog` / `hardware` / `parts` | Browse reusable parts | `parts/hardware.py` |
| `reuse <need>` | Find parts matching a need | catalog search (Phase 3+) |
| `diagnostics` / `tests` | Run gates | `CommandRelay` → `pytest`/`ruff`/`mypy` (Phase 6) |
| `repo` | Repo health | `git diff --stat`, `make doctor` (read-only) |
| `ai <prompt>` | Ask the Architect | `ArchitectNPC` (Phase 5, redacted) |
| `blueprint` | Draft a plan | AI planning (Phase 8) |
| `evidence` | View saved reports | `reports/` (Phase 7) |

## First 10 tasks (start here)

Repo-safe, low-risk, high-signal - the base of the climb:

1. ✅ Catalog card + `catalog/parts.yaml` + `make hardware` + tests. *(done)*
2. ✅ This blueprint (`docs/holodeck/`). *(done)*
3. ✅ Furnish the `workshop` room as the cockpit (it already existed off the cellar). *(done)*
4. ✅ `parts/workshop.py` - the `workshop` menu command, wired in the tick with an engine-tick test. **Display only.** *(done)*
5. ✅ Wire `catalog`/`hardware`/`parts` + `reuse <term>` in-world to `parts/hardware.py` (read-only). *(done)*
6. 📋 Stock 2-3 more real parts in the catalog as they prove reusable.
7. 📋 `reports/` scaffold + a tiny `save_report()` helper (write + summarize).
8. 📋 `parts/console.py` - the `CommandRelay` skeleton with the allowlist (Phase 6), tests first, **no execution of anything not on the list**.
9. 📋 `parts/architect.py` - the AI seam as a `Protocol` (mockable), read-only, context **redacted**; tests use a fake, never the network.
10. 📋 Document a first `PatchProposal` shape (no implementation) so Phase 9 has a target.

Tasks 1-2 are done. 3-5 are the next shippable slices (each: branch → `make check`
→ merge → push).

## Definition of done (per phase)

A phase is done when, for that slice:
- it works end-to-end from the Workshop (or `make` for infra phases),
- `make check` is green and the new card has a test twin,
- nothing risky runs without the Safety layer,
- and there's a one-line entry in the CHANGELOG / captain's log a stranger can follow.

## Portfolio translation

Each phase is also employer-facing proof. What to show, and what test proves it:

| Phase | Skill it demonstrates | Employer signal | Show (README/screenshot) | Test that proves it |
|-------|-----------------------|-----------------|--------------------------|---------------------|
| 4 Catalog | Data modeling, validation, reuse thinking | "designs for reuse, not one-offs" | `make hardware` output | `test_hardware.py` (loads + fails loud) |
| 5 AI NPC | LLM-as-component behind a seam | "uses AI as a dependable part, mocked in tests" | an in-world `ai` exchange | fake-backed NPC test, no network |
| 6 Console | Safe command execution, allowlisting | "security-minded automation" | the allowlist + a blocked command | test that a non-allowlisted command is refused |
| 7 Reports | Observability, evidence discipline | "produces auditable evidence" | a saved report under `reports/` | test that a run writes + summarizes |
| 9 Patch proposal | Change safety, review discipline | "AI never edits blindly" | a `PatchProposal` diff + approval gate | test that no write happens without approval |
| 12 Industry tracks | Domain modeling, compliance awareness | "reusable across gov/finance/compliance" | the `reuse` map in the catalog | catalog tests per domain tag |

Each of these is also a **case study**: "I built X for a game, then reused the same
tested part for a government/finance/compliance job - here's the catalog entry, the
tests, and the evidence."
