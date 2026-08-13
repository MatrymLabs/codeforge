# RETURN WO-S4

```yaml
packet_id: WO-S4
pr_url: UNVERIFIED - GitHub network is unavailable in this sandbox; push failed
status: PARTIAL
tests_passing: "yes - 20 passed in 0.62s (tests/test_engine_seam_differential.py)"
commands_compared: "old 8 -> new 14"
verdict: "AGREED - 14 comparisons across 5 categories; no real divergence"
files_touched:
  - kernel/engine_seam.py
  - tests/test_engine_seam_differential.py
  - handoff/WO-S4/RETURN.md
blockers: >
  Whole-instrument make check is UNVERIFIED [environment]. Exact output after formatting and static
  checks passed:
  lint-go: native/edge UNVERIFIED - it does not build. Generated code absent?
            run `make proto` (ADR-0012: the bindings are git-ignored).
  make: *** [Makefile:72: lint-go] Error 1
  The command that resolves this is `make proto` with protoc-gen-go installed, followed by
  `PATH=.venv/bin:$PATH make check` on a host with the Go toolchain. Push also remains unverified;
  `git push -u origin codex/wo-s4` failed with `ssh: Could not resolve hostname github.com`.

commands_run:
  - command: "pytest -q tests/test_engine_seam_differential.py"
    exit_code: 0
    output: "20 passed in 0.62s"
  - command: "ruff check kernel/engine_seam.py tests/test_engine_seam_differential.py"
    exit_code: 0
    output: "All checks passed!"
  - command: "mypy kernel/engine_seam.py tests/test_engine_seam_differential.py"
    exit_code: 0
    output: "Success: no issues found in 2 source files"
  - command: "PATH=/home/josh/Projects/MatrymLabs/codeforge/.venv/bin:$PATH make check"
    exit_code: 2
    output: |
      ruff format --check .
      1079 files already formatted
      ruff check .
      All checks passed!
      lint-go: native/edge UNVERIFIED - it does not build. Generated code absent?
                run `make proto` (ADR-0012: the bindings are git-ignored).
      make: *** [Makefile:72: lint-go] Error 1
  - command: "GIT_SSH_COMMAND='ssh -F /dev/null' git push -u origin codex/wo-s4"
    exit_code: 128
    output: "ssh: Could not resolve hostname github.com: Temporary failure in name resolution"
  - command: "git diff --stat"
    exit_code: 0
    output: |
      kernel/engine_seam.py                  | 75 ++++++++++++++++++++++++++++++++-
      tests/test_engine_seam_differential.py | 49 +++++++++++++++++++++
      2 files changed, 122 insertions(+), 2 deletions(-)

calibration_transitions:
  permission:
    broken: "WrongRoom Engine2D reports grand_library; differential returns a permission divergence"
    restored: "real Engine2D reports forge; differential has no divergences"
  persistence:
    broken: "WrongRoom Engine2D reports courtyard during save/restore; differential returns a persistence divergence"
    restored: "real Engine2D reports forge; differential has no divergences"
  coverage:
    derived: "the all_overlay_rooms probe loads the generated overlay and enters all 12 entries"

old_battery: "8 commands, inventory 3, progression 3, permission 1, persistence 1"
new_battery: "14 commands, inventory 3, progression 3, permission 4, persistence 3, coverage 1"
engine_protocol: unchanged
spatial_comparisons: none

# EXTRACTION SIGNALS
reimplemented: "none observed"
recurrence: "differential battery and planted-divergence calibration recur from WO-S1/WO-S3"
generalizable: "a probe battery can derive population coverage from an immutable generated artifact"
friction: "whole gate requires unavailable native Go/protobuf tooling"

# PATTERN SIGNALS
pattern_shapes: "multi-probe differential battery, planted wrong-room calibration, artifact-derived coverage"

# PATTERN SCREEN
lane_echo: "none observed in Codex persistence/commands/events/transactions/world/integration lane"
catalogue_match: "none observed; applied-once and contract-jig are adjacent shapes, not consumable mechanisms"
recurrence_check: "differential battery recurrence is intentional and recorded above"
verdict_note: "wider battery remains AGREED; no founder divergence gate triggered"
```
