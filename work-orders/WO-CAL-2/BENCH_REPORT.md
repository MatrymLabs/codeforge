packet_id: WO-CAL-2
pr_url: none opened by Codex
status: PARTIAL

## Result

The `bandit-insecure-tls` case now runs through `sys.executable -m bandit`, and its dependency
check validates the `bandit` module through that same repository interpreter. The case preserves
the harness's SKIP behavior when the required tool is unavailable. No other calibration case was
changed.

## Commands run

- Baseline: `make calibrate ONLY=bandit-insecure-tls`
  - exit 0; `[SKIP] bandit-insecure-tls bandit is not on PATH, so this gate cannot be calibrated`
- After repair: `make calibrate ONLY=bandit-insecure-tls`
  - exit 0; `[PASS] bandit-insecure-tls green -> RED on B501 -> green`
- Missing-tool refusal path: with `PATH=C:\\Windows\\System32`,
  `.venv\\Scripts\\python.exe scripts\\calibrate_gates.py --only gitleaks-hardcoded-credential`
  - exit 0; `[SKIP] gitleaks-hardcoded-credential gitleaks is not on PATH...`
- `.venv\\Scripts\\python.exe -m pytest tests/test_calibrate_gates.py -q`
  - exit 0; `5 passed in 0.26s`
- Full `make calibrate` under the bench-required PATH
  - exit 1: 13 calibrated, 1 failed. Bandit and every other case except
    `pytest-filterwarnings-error` passed. That unrelated existing case fails its benign control
    with `ERROR: Unknown config option: timeout`; it was not changed under this allowlist.
- `make check`
  - exit 0; `5427 passed, 57 skipped, 1 xfailed`, 93.38% coverage. All language gates, SAST,
    imports, registry completeness, and type checks passed.

## Files touched

- `scripts/calibrate_gates.py`
- `work-orders/WO-CAL-2/BENCH_REPORT.md`

## Extraction signals

reimplemented: no; the repository-interpreter command/dependency pattern already exists in the
Makefile and was applied only to this case.

recurrence: yes; this repeats the fleet's bare-tool/path divergence class, specifically the same
Windows interpreter routing correction that `make sast` uses.

generalizable: a `python-module:<name>` dependency probe lets a harness preserve honest SKIP
semantics while invoking Python tools through the owning interpreter.

friction: the full harness still contains a pre-existing pytest control that depends on the
`timeout` plugin/configuration path; resolving that would exceed this order's case allowlist.

pattern_shapes: interpreter-bound command, module availability probe, and green/red/green signal
assertion.

## Pattern screen

lane_echo: none observed in Codex's persistence, commands, events, transactions, world-graph, or
integration lane.

catalogue_match: none observed; the relevant pattern is already in the Makefile, not a Store Part.

recurrence_check: bare-tool Windows path divergence is a known recurring fault class.

verdict_note: first occurrence of this exact module-probe form in the calibration harness; no Part
opened.
