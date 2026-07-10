# Safety & Governance

The Workshop lets you run commands and (eventually) let an AI propose changes from
inside a game. That power is only acceptable behind hard rails. **The in-MUD
terminal is never a raw shell.** This document is the contract every automated
phase (5–11) must satisfy before it ships.

## The FailsafeRunner (the safe command relay)

Every command the Workshop can run goes through one relay with these properties:

- **Allowlist, not denylist.** Only explicitly-listed commands run. Unknown =
  refused. The v1 allowlist is **read-only**:
  `python --version`, `pytest`, `python -m compileall`, `ruff check`, `mypy`,
  `git status`, `git diff --stat`.
- **No shell interpolation.** Commands run as argument lists (`["pytest", "-q"]`),
  never a shell string. No `&&`, `|`, `;`, backticks, globs, or user-substituted args.
- **Timeouts.** Every run has a wall-clock limit; a hung command is killed.
- **Output caps.** Output is bounded in size; overflow is truncated in-world and the
  full log is saved to `reports/` (never streamed unbounded to the MUD).
- **Working-directory restriction.** Runs are confined to the repo root; no `..`
  escapes, no absolute paths outside the project.
- **Logging.** Every invocation is logged (command, time, exit code, duration) -
  the relay is itself an evidence source.
- **Dry-run by default** where a command can mutate. Mutation requires an approval gate.

## Approval gates (human-in-the-loop)

These actions **require explicit human approval** and are never auto-run from the MUD:

- deleting files · moving many files · installing dependencies
- changing `.env` / environment files · modifying Git history · pushing to a remote
- changing secrets · editing config files · running network actions · executing unknown scripts
- changing the catalog schema · rewriting large architecture sections
- modifying **compliance evidence, finance records, or records-retention logic**

When the AI (Phase 9+) wants to change a file, it emits a **`PatchProposal`**, not an
edit. The proposal must state: *what file · why · which reusable part is affected ·
which catalog entry updates · the risk · how to test · how to document · how to revert.*
A human approves before any byte is written. Then, and only then (Phase 10): branch
first → show the plan → produce the diff → run tests → save an evidence report →
record the rollback path.

## Secret & sensitive-data boundaries

**Never send to the AI API:** secrets, API keys, `.env` contents, private
credentials, financial records, controlled/CUI information, private customer data,
government-sensitive information, or any file outside the public project context.

- The API boundary is a **seam** (a `Protocol`), mockable; **tests never hit the
  network** and CI runs with no key (same rule as `ai-log-triage`).
- Context sent to the API is **redacted** and drawn only from public project files -
  never from the machine's private environment. `.env` is git-ignored; only
  `.env.example` is tracked; `make secrets` (detect-secrets) gates it.
- Keep a clear wall between **public project context** (safe to send) and **private
  machine context** (never sent).

## When to leave the MUD and open PyCharm

Automate the safe and routine; escalate the serious. Open PyCharm for manual review
**before**:

- approving any patch or generated code,
- renaming files, moving modules, or reshaping architecture,
- changing secrets, `.env`, or config,
- installing or bumping dependencies,
- changing Git state (history, merges, pushes) beyond the normal branch→check→ship,
- altering **compliance, finance, or records** logic or evidence,
- resolving anything the safe runner or approval gate flagged as risky.

The rule of thumb: **if it's reversible, low-risk, and allowlisted, the Workshop can
do it; if it's risky, outward-facing, or sensitive, it goes to PyCharm for a human.**

## Reports & evidence

Command and AI outputs are saved, not spammed. Long output is summarized in-world;
the full log lands under `reports/` by kind (`tests/`, `diagnostics/`, `ai/`,
`repo_audits/`, `security/`, `compliance/`, `catalog/`, `finance/`, `records/`).
Generated reports are git-ignored but reproducible; compliance/finance/records
evidence follows the ship's evidence discipline (dated + hashed, traceable to a
commit). See the ship's `CLAUDE.md` for the federal evidence rules.

## Compliance honesty

Nothing here is "compliant" or "certified" - it is **readiness/evidence** tooling.
A pipeline satisfies only the technical portion of a control; policy and
people/process work is human and unautomatable. Never let a green check imply a
certification. Open gaps are logged, never hidden.
