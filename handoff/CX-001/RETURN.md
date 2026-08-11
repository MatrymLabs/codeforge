# RETURN CX-001

```yaml
packet_id: CX-001
pr_url: https://github.com/MatrymLabs/codeforge/pull/908
status: COMPLETE
commands_run:
  - command: git fetch origin
    exit_code: 0
    output_excerpt: origin/main verified at 027ce5ce
  - command: make claims
    exit_code: 0
    output_excerpt: "Claims board :: 2 file(s), 6 claim(s); VERDICT: PASS (0 failing)"
  - command: PATH="$PWD/.venv/bin:$PATH" pytest -q tests/test_exit_integrity.py
    exit_code: 0
    output_excerpt: "12 passed in 0.51s"
  - command: PATH="$PWD/.venv/bin:$PATH" pytest -q tests/test_exit_integrity.py tests/test_seed.py
    exit_code: 0
    output_excerpt: "87 passed in 0.87s"
  - command: PATH="$PWD/.venv/bin:$PATH" ruff format --check ... && ruff check ... && mypy ...
    exit_code: 0
    output_excerpt: "3 files already formatted; All checks passed; Success: no issues found in 3 source files"
  - command: PATH="$PWD/.venv/bin:$PATH" python -c '<undeclared cellar west sabotage>'
    exit_code: 0
    output_excerpt: "ACCIDENTAL one-way exits: - cellar --west--> workshop"
  - command: PATH="$PWD/.venv/bin:$PATH" make exit-integrity
    exit_code: 0
    output_excerpt: "Declared one-way exits: 6"
  - command: PATH="$PWD/.venv/bin:$PATH" make check
    exit_code: UNVERIFIED
    output_excerpt: >
      Started this session. Lint, import contracts, mypy, and the exit-integrity gate passed;
      coverage then entered the known network-isolated sandbox hang and was terminated after more
      than three silent minutes. The live board directs focused tests, lint, and typecheck as the
      local proof in this environment. CI must run the full gate.
tests_passing: "yes, focused suite: 87 passed"
files_touched:
  - kernel/world/exit_integrity.py
  - tests/test_exit_integrity.py
  - kernel/world/seed.py
  - content/seeds/first-forge/rooms.yaml
  - content/seeds/aethryn/rooms.yaml
  - registry/designations/modules.json
  - Makefile
  - handoff/CX-001/RETURN.md
blockers: none

store_search:
  command: >
    python3 -m hardware_store.store_search "graph traversal" --repo codeforge;
    python3 -m hardware_store.store_search "bidirectional edge validation" --repo codeforge
  result: >
    No catalogued graph-traversal part exists. The bidirectional query found only CANDIDATE
    lexicon-gate by prose text, not a graph-validation capability. No part was consumed.
  log: hardware-store/intake/search_log.jsonl, two codeforge entries, 2026-08-11

# EXTRACTION SIGNALS
reimplemented: >
  No certified Store part was reimplemented. The Store search found none for graph traversal or
  bidirectional edge validation.
recurrence: >
  Second graph-validation shape in CodeForge: callings.prerequisite_cycles() validates a directed
  prerequisite graph, while exit_integrity validates reverse edges in the room graph. The traversal
  predicates differ, so no abstraction was extracted.
generalizable: >
  The ExitVerdict and declared-asymmetry shape could serve any data-declared directed graph with
  reversibility rules, but this is only its first external consumer. Flag for R&D, do not extract.
friction: >
  None observed in a certified Store part. The Store has no graph-validation part to consume.
pattern_shapes:
  - "directed graph edge -> inverse-edge validation -> structured verdict"
  - "data declaration -> loader type/value gate -> visible exception report"
dissent: >
  The prescribed fleet worktree guard, `MATRYM_AGENT=codex make worktree`, is absent at the verified
  remote tip and exits `make: *** No rule to make target 'worktree'. Stop.` The founder explicitly
  assigned this dedicated codeforge-codex worktree and agent/codex/station branch, which was used as
  the bench proof. Restore the guard before treating that command as an enforceable control.
adjudication: >
  Aethryn settlement `out` exits are clean because their region hubs return through named settlement
  entrances. The four remaining Aethryn non-inverse routes and First Forge's two non-inverse routes
  are explicitly declared one-way. Their destination inverse directions are already occupied by
  different world routes; changing them would rewrite unrelated navigation. The declarations make
  those directional travel decisions visible rather than silently trapping players.
```
