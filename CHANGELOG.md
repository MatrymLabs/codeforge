# Changelog

All notable changes to CodeForge. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); versions are date-stamped while
pre-1.0. Readiness language only — no compliance/OSHA/legal claims.

## [Unreleased]

### Added / Changed
- **ADR-0003: Framework-free — why CodeForge is not Evennia.** Codifies the clean-room
  divergence from the Evennia/Django/Twisted predecessor as law (world-is-data not
  typeclasses, one pure-function tick not CmdSets, derive-don't-store not ORM Attributes),
  and names the genre-universal conventions (`@` admin, account/character split, rooms/
  exits) as *not* copying. Enforced, not just documented: `tests/test_framework_free.py`
  fails CI if any `evennia`/`django`/`twisted` import or dependency is reintroduced
  (honest prose lineage notes still allowed). Verified zero contamination 2026-07-10.
- **Seed → Cast scaffold (Phase 1).** A **seed pack** is a game's content (`seeds/<name>/`);
  a **cast** is a standalone project poured from the forge — the engine + one seed pack +
  config, detached into its own repo. `parts/cast.py` + `make cast-plan` PLAN a cast (a dry
  run listing what it *would* copy and the manifest it *would* write) and write nothing.
  Honest by construction: `engine_strategy: "vendored-whole"` (module-level selection is
  Phase-2 decoupling work, not claimed now), and the never-copy set covers secrets/state/
  evidence/other-packs. Ships `seed_templates/{blank_mud,fantasy_mud}` + the doctrine in
  `docs/seed_architecture.md`. Real generation, detachment, and standalone boot come later.
- **Ritual audit batch 2 — no double suite run, and a shutdown push-ready gate.**
  `make check` now folds coverage into a **single** suite run (`lint · types · pytest
  --cov · threshold`) instead of running the suite once for `check` and again for
  `coverage`; the startup ritual and CI drop the redundant second run (~15s off each).
  `complete the ritual` gains a **PUSH READINESS** phase: `commit_ready` / `push_ready`
  verdicts that name every blocker (staged `.env` or generated/state files, committed
  secrets, broken imports, red gates) and are banked in the after-action record. It never
  pushes — it makes the unsafe choice loud. `make check` in the gate is change-aware (runs
  only when unpushed commits exist).
- **Ritual modes — `make ritual-fast` (~1s preflight).** Automation Enhancement Audit,
  batch 1 (additive, zero renames/deletions): a read-only fast door for daily coding —
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
  rooms/items) — `qa gate all` → **72/72 pass**, `pm status` → **GREEN** (closes
  LSS-CF-001). A new test (`test_the_shipped_board_has_no_failures`) enforces the *hard
  bar*: no object may be `active` without a file + tests, so an untested/unfiled object
  turns CI red. `docs/project_management.md` gains a **Growth structure** section: the
  project audits its own maturity as it scales — filed · tested · documented · maturity
  honest — and a system isn't *done* until `pm status` is green for it.

### Performance / Changed
- **Test suite ~2.3× faster (27.7s → 11.8s), measured.** The suite was dominated by
  password tests running pbkdf2 at the production 600k iterations. `conftest` now drops
  the iteration count to 1000 *inside the test process only* — production stays 600k
  (the constant is read at call time). Tests still prove hash/verify/rotate logic; they
  just no longer pay for 600k of deliberately-expensive hashing. Speeds up `make check`,
  the ritual's IGNITION, and CI. (Runtime commands were already fast — `pm status`
  5.7ms — so no premature caching was added.)
- **Ritual WARDS now gates secrets too:** the startup ritual runs `detect-secrets`
  (offline, fast) alongside `bandit` — the forge won't light on a committed secret.

### Added / Changed
- **The self-audit now covers the code** (code-audit Finding 1). Filed 38 `MOD-*`
  designations for every `parts/*.py` module, so `qa gate all` / `pm status` now grade
  the codebase itself, not just rooms/commands/items (72 objects, up from 34). All
  modules pass purpose/file/tests/maturity; docs-link is the pending soft gap.
- **Failure-branch tests** (Finding 3): the previously-untested *failure* paths are now
  pinned — `pm` red/green + recommendation logic (via an injectable `metrics` seam),
  `safety_review` item/prototype branches, `render_*` unknown-designation paths,
  `validate` tests-not-found, and `run_repo_integrity`.
- **Two maturity vocabularies documented** (Finding 2): the catalog's `maturity`
  (reuse-readiness) and the registry's `status` (lifecycle) are deliberately different
  axes — now stated in `catalog/README.md` so they're not mistaken for a duplicate.

### Added
- **Secret scanning** (`make secrets`): detect-secrets gates on any tracked secret not
  in the audited `.secrets.baseline` (verified — passes clean, catches a planted key).
  Folded into `make security` and CI. Closes the RepoIntegrityRitual's own #1 gap:
  its report went `secret scan: not_configured` → `detected`. The repo scanned clean
  (empty baseline).
- **RepoIntegrityRitual** (`parts/integrity.py`, `make repo-integrity`): one honest
  repo-health report — code quality (tool detection), security, license/source origin,
  originality awareness, presentation, and a truth/VeritasGate pass — composed from
  checks the repo already owns, saved dated under `reports/repo_integrity/`.
  Integrity-first: a missing tool is reported `not_configured` (never faked), it never
  uploads code to a third party, and it states plainly that it does **not** prove legal
  originality/security/compliance. It honestly surfaces its own top gap — **secret
  scanning is not_configured** (no `make secrets` yet) — as the recommended next action.
  + `docs/repo_integrity.md`. +7 tests.

### Added / Changed
- **Harvest patterns, not code — made provable.** Hardware Part Cards gain an
  `influence` field recording the *known pattern* each part was rebuilt from (RBAC,
  pub/sub, allowlist-without-a-shell, fail-loud validation). Each part is an original
  implementation *of the pattern* — concept reused, expression ours. `make hardware`
  now shows provenance (`source_status`, `license`) + pattern; a test pins that every
  shipped part is free-to-use and records its pattern, and refuses a non-free status.
- **Branding + provenance polish (truthful).** README gains a "What this demonstrates"
  section (skills tied to evidence); GitHub topics added for discoverability. Hardware
  Part Cards gain `source_status` / `license` fields — the **Free-to-Use rule**: only
  stock parts whose license is clearly free to use (the loader refuses any status
  outside the free-to-use set); every part is `original` MIT code. Catalog maturity
  `production` → `shipped` so the label matches its own definition ("shipped + tested
  on main") — no out-of-context overclaim.

### Added
- **Legal/policy awareness** (`docs/legal_policy_awareness.md` + `law` card): a
  documented boundary — CodeForge provides compliance-*awareness* (source tracking,
  checklists, evidence), **not legal advice**, and never claims compliance. New
  read-only `law` / `law <id>` command renders the tracked sources through that lens
  (jurisdiction · freshness · publication date) and always ends "No legal conclusion.
  Human review required." Reuses the guidance-source registry; jurisdiction is
  unknown by default. Standalone `ApplicabilityMapper`/`ComplianceDesignGate`/`law
  check` remain planned, not built.
- **End-to-end live smoke test** (`scripts/e2e_smoke.py`, `make smoke`): drives the
  whole engine over a real TCP socket in one sequence — start (isolated server) →
  log in → look → check (regs/library/registry/qa/pm/docs) → do (move, `@sg` denied
  for a player, then owner grant + forge + take) → log out → bank the forge. Runs on
  a spare port with an ephemeral DB (the real `:4000` and `codeforge.db` are never
  touched); every step is asserted and timed. 16/16 green.

### Fixed / Performance
- **Gateway latency ~40ms → ~1ms per command.** The TCP gateway never set
  `TCP_NODELAY`, so every one-line reply stalled ~40ms on Nagle + delayed-ACK — a
  fixed per-command lag for every client (Mudlet, telnet, browser gate). Disabled
  Nagle in the connection setup. Measured via the smoke test: per-command round-trips
  dropped from ~44ms to ~0–3ms (~20–40×).

### Added
- **Ritual READINESS phase + `make readiness`**: the startup ritual now runs a global
  self-audit — the classification registry validates (no duplicates/orphans; GATES
  the forge) and the project dashboard (`pm status`) prints as a readiness report.
  `make readiness` is the reusable one-button version. `docs/startup_ritual.md`
  documents all six phases (IGNITION · WARDS · READINESS · MIRROR · FORGE · GATE).
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
