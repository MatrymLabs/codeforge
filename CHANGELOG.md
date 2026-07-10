# Changelog

All notable changes to CodeForge. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); versions are date-stamped while
pre-1.0. Readiness language only - no compliance/OSHA/legal claims.

## [Unreleased]

### Added / Changed
- **CI installs via uv.** The check job now installs dependencies with `uv pip install`
  (Rust parallel resolver) instead of pip: measured install step ~19s -> ~6s (setup 2s +
  install 4s). CI-only tooling, not a runtime/pyproject dependency; build backend stays
  setuptools. Unlike a download cache, the win is deterministic (not hit-dependent).
- **Ritual tuned: parallel tests + PR-aware `make ship`.** The test suite (measured as ~95%
  of `make check`) now runs across cores via pytest-xdist (`coverage` uses `-n auto`): ~19s
  -> ~16s locally, more on CI. And `make ship` was fixed for the protected `main`: it refuses
  to push to main, pushes the current branch, and opens its PR (branch -> PR -> CI -> merge).
  The inner-loop `make test`/`property` stay serial for readable output.
- **CodeQL added to required checks.** `main` now requires `check`, `docker`, and both
  CodeQL analyze jobs to pass before merging. Scorecard stays non-required (no PR trigger;
  requiring it would deadlock PRs) but still scores on schedule.
- **Branch protection on `main` (Scorecard Branch-Protection lever).** Require a PR + the
  `check`/`docker` CI (strict) before merging; force-push and deletion blocked. Solo-friendly
  (0 approvals) and no-lockout (`enforce_admins=false`). Retires the local merge-to-main
  shortcut in favor of the documented branch -> PR -> CI green -> merge flow.
- **Hardware Store: the road not taken.** Each part card now carries an optional
  `experimental` section (`make hardware`) naming the framework/tool path it *could*
  take if CodeForge were not frameless (FastAPI DI, Pydantic, a broker, Jinja2, an LMS)
  and what that trade would cost. Shows the frameless choice was deliberate, not naive.
- **Dependency gate (`make deps`) + SHA-pinned Actions.** The Dependency Approval Rule is
  now machine-checkable: `dependency_ledger.toml` justifies every dependency and
  `parts/dependencies.py` (stdlib `tomllib`) fails loud on any unjustified one; the test
  twin rides `make check`. All GitHub Actions are pinned to full commit SHA (Dependabot
  maintains them), lifting the OpenSSF Scorecard Pinned-Dependencies check. Filed as
  MOD-UM10-S01-N001-012-R0.
- **OpenSSF Scorecard wired.** `.github/workflows/scorecard.yml` scores the repo's
  supply-chain/security posture weekly + on push and publishes the result; a truthful
  badge is on the README. Closes the last open Phase-3 tooling item. No runtime dep.
- **Frameless Python tooling strategy (docs).** Named the frameless identity in
  `docs/frameless_python.md` and the tool-evaluation discipline in `docs/tooling_strategy.md`:
  a current-inventory audit, a decision matrix, a Tool Integration Review template, a
  Dependency Approval Rule, and the phased roadmap. Finding: the repo is already Phase 3;
  OpenSSF Scorecard is the one open low-risk integration. No dependencies added.
- **Terminal sticky note.** A post-it cheat card on the FORGE TERMINAL boot screen shows the
  few commands to drive it (get here: workshop -> north; `terminal`, `terminal <name>`,
  `terminal help`) so the way in is never a memory test.
- **Functions check: full live sweep (7/7).** Filled the remaining parts with real demos,
  so every cataloged part now runs live: `event-ledger` delivers a message to an echo sink,
  `safe-runner` refuses `rm -rf /` (CommandRefused, never ran), `gate-runner` lists the
  doctor's 8 read-only gates. No more `[tested]`/`[manual]` rows -- 7 demonstrated live.
- **The in-game computer (`terminal`).** A read-only FORGE TERMINAL in the Diagnostic
  Console room that WIRES every diagnostic program behind one console: `terminal functions`
  (the functions check), `inspect`, `career`, `pioneer`, `pm`, `truth`, `qa`, `docs`. Each
  dispatches to that system's existing renderer (composition, not duplication), framed like
  a terminal. `parts/terminal.py` + `docs/terminal.md`; the room now points to it. board 86/86.
- **Hardware Store functions check (`functions`).** A live demo of each cataloged reusable
  part, the real call and its real output, so "reusable" is shown, not claimed: `rank-gate`
  refuses a novice and allows an owner, `report-writer` writes "hello world" to a temp file,
  `validated-loader` rejects a bad row and fails loud, `assessment-engine` validates its
  lessons. Parts that need world state cite their test twin (`[tested]`), never a fake demo.
  `parts/functions.py`, filed in the registry (board 84/84).
- **Closed three career-board gaps with real artifacts.** Cataloged the ReportWriter as a
  Hardware Store part with a cross-domain reuse map (`catalog/parts.yaml`); wrote a real
  rollback runbook for the live demo (`docs/runbooks/demo-deploy-rollback.md`); added a
  DOCS IMPACT nudge to the shutdown ritual (warns when code changes without docs). The
  Career board flipped 25 -> 28 proven (honesty test confirms every cited artifact exists).
- **Frame-up consolidation (the Pioneer-path cleanup).** `inspect` became the audit hub:
  `inspect qa` / `inspect truth` / `inspect pm` drill into one system each (reusing that
  system's own renderer, nothing duplicated), and `inspect save` banks the frame-up. A
  shared **ReportWriter** (`parts/reporting.py`) files every dated report under
  `reports/<category>/` through one seam, adopted by both `make repo-integrity` and
  `inspect save`. New **`docs/README.md`** maps every doc for navigation. The standalone
  `qa gate all` / `truth check` / `pm status` commands still work.
- **`inspect` - inspect the forge (on-demand frame-up).** One command that composes every
  self-audit signal - registry validity · QA board · VeritasGate truth · doc presence ·
  overclaim scan, plus career + pioneer status - into a single green/yellow/red frame-up.
  Computed live (nothing stored), REUSES the existing gates (no duplication). The single
  pane of glass over the whole machine. `parts/frameup.py` + `docs/frame_up.md` +
  `tests/test_frameup.py`; filed in the registry (board 81/81). Currently 🟢 GREEN.
- **Pioneer Mode (`pioneer` command).** A disciplined-Maverick engineering framework -
  *bend convention, not truth/safety/trust* - surfaced in the MUD and codified in docs.
  `docs/pioneer_mode.md` (doctrine · Maverick Filter · risk ladder L1-L5 · constraint-review
  + experiment templates), `parts/pioneer.py` + `data/pioneer/risk_ladder.json` (views:
  `pioneer` · `risks` · `plan` · `experiments`), and a **real first filed experiment**
  (`docs/pioneer_experiments/2026-07-10-honest-gpu-split.md` - building a GPU package on a
  GPU-less host, verified CPU / honest GPU). Filed in the registry (board 79/79); the
  framework gives the existing gates bold direction, it does not replace them.
- **Runbook + postmortem discipline (closes a Career-board gap).** Added
  `docs/runbook_template.md`, `docs/postmortem_template.md`, and a real filled blameless
  postmortem (`docs/postmortems/2026-07-09-red-merge-to-main.md`) of the day a bandit gate
  merged red to `main` - with the root cause (local/CI gate asymmetry) and the standing
  rules it produced. Flipped the Career board's `adv.runbook.postmortem` skill from
  `missing` → `proven` (board now 25 proven · 8 partial · 1 missing); the honesty test
  confirms every cited artifact exists.
- **Career Evidence Sign (`career` command).** A data-driven, VeritasGate-honest proof
  board in *The Forge Workshop* that maps CodeForge work to real software-career skills -
  each with the exact repo artifact that proves it, and the honest gaps. Grounded in
  BLS/O*NET research. Views: `career` · `career checklist` · `career gaps` · `career
  evidence` · `career resume` · `career role entry|intermediate|advanced`. `parts/career.py`
  + `data/career/career_evidence_matrix.json` + `docs/{career_evidence_board,resume_mapping}.md`.
  Honesty enforced: `tests/test_career.py` fails if a skill is `proven`/`partial` while its
  cited proof path doesn't exist (no overclaiming). Shipped board: 24 proven · 8 partial ·
  2 missing of 34 skills.
- **ADR-0003: Framework-free by design.** Records the deliberate scope choice to build the
  engine in plain, testable code (world-is-data, one pure-function tick, derive-don't-store,
  small tested parts) rather than on a framework. Framed neutrally - a framework like Evennia
  is a fine tool, simply out of scope for what this portfolio proves - and **revisable**:
  adopting a dependency later remains an open option. Notes the genre-universal conventions
  (`@` admin, account/character split, rooms/exits) as shared MUD vocabulary, not copying.
- **Seed → Cast scaffold (Phase 1).** A **seed pack** is a game's content (`seeds/<name>/`);
  a **cast** is a standalone project poured from the forge - the engine + one seed pack +
  config, detached into its own repo. `parts/cast.py` + `make cast-plan` PLAN a cast (a dry
  run listing what it *would* copy and the manifest it *would* write) and write nothing.
  Honest by construction: `engine_strategy: "vendored-whole"` (module-level selection is
  Phase-2 decoupling work, not claimed now), and the never-copy set covers secrets/state/
  evidence/other-packs. Ships `seed_templates/{blank_mud,fantasy_mud}` + the doctrine in
  `docs/seed_architecture.md`. Real generation, detachment, and standalone boot come later.
- **Ritual audit batch 2 - no double suite run, and a shutdown push-ready gate.**
  `make check` now folds coverage into a **single** suite run (`lint · types · pytest
  --cov · threshold`) instead of running the suite once for `check` and again for
  `coverage`; the startup ritual and CI drop the redundant second run (~15s off each).
  `complete the ritual` gains a **PUSH READINESS** phase: `commit_ready` / `push_ready`
  verdicts that name every blocker (staged `.env` or generated/state files, committed
  secrets, broken imports, red gates) and are banked in the after-action record. It never
  pushes - it makes the unsafe choice loud. `make check` in the gate is change-aware (runs
  only when unpushed commits exist).
- **Ritual modes - `make ritual-fast` (~1s preflight).** Automation Enhancement Audit,
  batch 1 (additive, zero renames/deletions): a read-only fast door for daily coding -
  imports · registry · truth GATE red, lint/types/claims WARN yellow, no suite/network/
  scans (~45s → ~1s). Extracted `scripts/lib.sh` (shared colours + message helpers) to
  dedupe `ritual.sh`/`ritual_down.sh`. Added the missing `docs/shutdown_ritual.md`; the
  startup doc's phase table refreshed to the current 8 phases + a mode table.
- **CodeQL + SBOM (supply-chain evidence).** Added a GitHub-native CodeQL workflow
  (`.github/workflows/codeql.yml`, scanning Python and the workflows) and `make sbom`
  (CycloneDX bill of materials, generated in CI and kept as an artifact). The forge-audit
  scorecard's `ci` dimension now passes at the intermediate stage on two real workflow
  files; the README Evaluation table was regenerated to match.
- **The ritual now asserts what CI asserts, and banks evidence.** IGNITION added the
  coverage-threshold gate (parity with CI); new VERITAS (`truth check`) and SMOKE
  (end-to-end) phases GATE before the forge lights; every run writes a dated after-action
  record under `reports/ritual/`. `make truth` exposes VeritasGate to scripts/CI.
- **The board is green, and it's now a growth gate.** Linked every filed object to its
  real documentation (a doc page for modules/commands, a seed/inline note for
  rooms/items) - `qa gate all` → **72/72 pass**, `pm status` → **GREEN** (closes
  LSS-CF-001). A new test (`test_the_shipped_board_has_no_failures`) enforces the *hard
  bar*: no object may be `active` without a file + tests, so an untested/unfiled object
  turns CI red. `docs/project_management.md` gains a **Growth structure** section: the
  project audits its own maturity as it scales - filed · tested · documented · maturity
  honest - and a system isn't *done* until `pm status` is green for it.

### Performance / Changed
- **Test suite ~2.3× faster (27.7s → 11.8s), measured.** The suite was dominated by
  password tests running pbkdf2 at the production 600k iterations. `conftest` now drops
  the iteration count to 1000 *inside the test process only* - production stays 600k
  (the constant is read at call time). Tests still prove hash/verify/rotate logic; they
  just no longer pay for 600k of deliberately-expensive hashing. Speeds up `make check`,
  the ritual's IGNITION, and CI. (Runtime commands were already fast - `pm status`
  5.7ms - so no premature caching was added.)
- **Ritual WARDS now gates secrets too:** the startup ritual runs `detect-secrets`
  (offline, fast) alongside `bandit` - the forge won't light on a committed secret.

### Added / Changed
- **The self-audit now covers the code** (code-audit Finding 1). Filed 38 `MOD-*`
  designations for every `parts/*.py` module, so `qa gate all` / `pm status` now grade
  the codebase itself, not just rooms/commands/items (72 objects, up from 34). All
  modules pass purpose/file/tests/maturity; docs-link is the pending soft gap.
- **Failure-branch tests** (Finding 3): the previously-untested *failure* paths are now
  pinned - `pm` red/green + recommendation logic (via an injectable `metrics` seam),
  `safety_review` item/prototype branches, `render_*` unknown-designation paths,
  `validate` tests-not-found, and `run_repo_integrity`.
- **Two maturity vocabularies documented** (Finding 2): the catalog's `maturity`
  (reuse-readiness) and the registry's `status` (lifecycle) are deliberately different
  axes - now stated in `catalog/README.md` so they're not mistaken for a duplicate.

### Added
- **Secret scanning** (`make secrets`): detect-secrets gates on any tracked secret not
  in the audited `.secrets.baseline` (verified - passes clean, catches a planted key).
  Folded into `make security` and CI. Closes the RepoIntegrityRitual's own #1 gap:
  its report went `secret scan: not_configured` → `detected`. The repo scanned clean
  (empty baseline).
- **RepoIntegrityRitual** (`parts/integrity.py`, `make repo-integrity`): one honest
  repo-health report - code quality (tool detection), security, license/source origin,
  originality awareness, presentation, and a truth/VeritasGate pass - composed from
  checks the repo already owns, saved dated under `reports/repo_integrity/`.
  Integrity-first: a missing tool is reported `not_configured` (never faked), it never
  uploads code to a third party, and it states plainly that it does **not** prove legal
  originality/security/compliance. It honestly surfaces its own top gap - **secret
  scanning is not_configured** (no `make secrets` yet) - as the recommended next action.
  + `docs/repo_integrity.md`. +7 tests.

### Added / Changed
- **Harvest patterns, not code - made provable.** Hardware Part Cards gain an
  `influence` field recording the *known pattern* each part was rebuilt from (RBAC,
  pub/sub, allowlist-without-a-shell, fail-loud validation). Each part is an original
  implementation *of the pattern* - concept reused, expression ours. `make hardware`
  now shows provenance (`source_status`, `license`) + pattern; a test pins that every
  shipped part is free-to-use and records its pattern, and refuses a non-free status.
- **Branding + provenance polish (truthful).** README gains a "What this demonstrates"
  section (skills tied to evidence); GitHub topics added for discoverability. Hardware
  Part Cards gain `source_status` / `license` fields - the **Free-to-Use rule**: only
  stock parts whose license is clearly free to use (the loader refuses any status
  outside the free-to-use set); every part is `original` MIT code. Catalog maturity
  `production` → `shipped` so the label matches its own definition ("shipped + tested
  on main") - no out-of-context overclaim.

### Added
- **Legal/policy awareness** (`docs/legal_policy_awareness.md` + `law` card): a
  documented boundary - CodeForge provides compliance-*awareness* (source tracking,
  checklists, evidence), **not legal advice**, and never claims compliance. New
  read-only `law` / `law <id>` command renders the tracked sources through that lens
  (jurisdiction · freshness · publication date) and always ends "No legal conclusion.
  Human review required." Reuses the guidance-source registry; jurisdiction is
  unknown by default. Standalone `ApplicabilityMapper`/`ComplianceDesignGate`/`law
  check` remain planned, not built.
- **End-to-end live smoke test** (`scripts/e2e_smoke.py`, `make smoke`): drives the
  whole engine over a real TCP socket in one sequence - start (isolated server) →
  log in → look → check (regs/library/registry/qa/pm/docs) → do (move, `@sg` denied
  for a player, then owner grant + forge + take) → log out → bank the forge. Runs on
  a spare port with an ephemeral DB (the real `:4000` and `codeforge.db` are never
  touched); every step is asserted and timed. 16/16 green.

### Fixed / Performance
- **Gateway latency ~40ms → ~1ms per command.** The TCP gateway never set
  `TCP_NODELAY`, so every one-line reply stalled ~40ms on Nagle + delayed-ACK - a
  fixed per-command lag for every client (Mudlet, telnet, browser gate). Disabled
  Nagle in the connection setup. Measured via the smoke test: per-command round-trips
  dropped from ~44ms to ~0-3ms (~20-40×).

### Added
- **Ritual READINESS phase + `make readiness`**: the startup ritual now runs a global
  self-audit - the classification registry validates (no duplicates/orphans; GATES
  the forge) and the project dashboard (`pm status`) prints as a readiness report.
  `make readiness` is the reusable one-button version. `docs/startup_ritual.md`
  documents all six phases (IGNITION · WARDS · READINESS · MIRROR · FORGE · GATE).
- **PM control panel** (`parts/pm.py`): `pm status` / `pm metrics` - the project
  dashboard is *computed* from the registry + QualityGate (part + part + part), not
  stored. `docs/project_management.md` holds the charter, milestone status, backlog,
  risk register, decision log, and one worked DMAIC. Scope control: this prompt's
  full PMO + Lean-Six-Sigma/ADDIE systems were *deferred as backlog*, not built.
- **Safety + QA spine** (`parts/qualitygate.py`): `QualityGate` grades any filed
  object (purpose · file · tests · docs · maturity-honesty → `pass|watch|fail`),
  `SafetyReview` rates risk, `DocumentationImpactSweep` sweeps the key docs. New
  read-only MUD commands `qa gate [all|<id>]`, `safety review <id>`, `docs check`.
  Proof of composition: `qa gate all` audits the whole registry (part + part).
- **`docs/safety_qa_system.md`** - the Safety + QA architecture.
- **`@sg item <pattern>`** - admin (wizard+) item generator on the command spine;
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
