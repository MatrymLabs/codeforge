# WO-CAL-1 Bench Report

packet_id: WO-CAL-1
repository: codeforge
branch: codex/verify-wo-rev-1043
status: complete_awaiting_founder_merge

## Changed

scripts/calibrate_gates.py now refuses an --only value that matches no case. It exits 2, names
the unresolved value, and lists the available cases. Unfiltered empty selection and honest
toolchain skips retain exit 0. Added tests/test_calibrate_gates.py with five contract tests.

## Failure before repair

Required baseline command:

    make calibrate ONLY=zzz-no-such-case-exists
    .venv/Scripts/python.exe scripts/calibrate_gates.py --only zzz-no-such-case-exists
    Gate calibration  (0 case(s))

    0 calibrated, 0 FAILED, 0 skipped (toolchain absent)
    EXIT=0

The unmatched name silently passed.

## Repair proof

    .venv/Scripts/python.exe -m pytest tests/test_calibrate_gates.py -q -p no:randomly
    5 passed in 0.26s

    make calibrate ONLY=zzz-no-such-case-exists
    No calibration case matches 'zzz-no-such-case-exists'.
    Available cases: detekt-TooGenericExceptionCaught, ruff-ARG-unused-argument,
    ruff-S-subprocess-shell, ruff-BLE-broad-except, shellcheck-unquoted-variable,
    terraform-fmt-drift, c-unused-parameter, go-errcheck-ignored-error, rust-clippy-unwrap,
    pytest-filterwarnings-error, bandit-insecure-tls, gitleaks-hardcoded-credential,
    mypy-strict-type-error, mypy-warn-unreachable
    UNKNOWN_EXIT=2

    make calibrate ONLY=mypy-strict-type-error
    [PASS] mypy-strict-type-error green -> RED on Incompatible return value -> green
    1 calibrated, 0 FAILED, 0 skipped (toolchain absent)
    REAL_EXIT=0

## Full proof run

make check passed end to end:

    ruff format --check .: 1144 files already formatted
    ruff check .: All checks passed!
    Contracts: 4 kept, 0 broken.
    mypy: Success: no issues found in 404 source files
    coverage: 93.39%
    5420 passed, 55 skipped, 1 xfailed in 39.70s

Rust, Go, Terraform, C, import, native typecheck, Bandit, and secret-scan lanes also passed.

## Reusable Part signals

reimplemented: none observed; this is a narrow empty-selection guard using the existing case list.

recurrence: empty filters reporting success recur across gate wrappers and scanners; this is the
third observed instance of an instrument answering a question it could not ask.

generalizable: every user-supplied selector must distinguish an empty valid result from an
unresolvable name and must expose the available domain when refusing.

friction: the Windows patch helper required direct invocation of Codex apply-patch mode; no source
scope was changed.

## Pattern screen

lane_echo: commands and integration were screened through the Make target and CLI exit behavior;
no persistence, event, transaction, or world-graph behavior changed.

catalogue_match: the Certified Tier and Working Shelf searches recorded in the Build Sheet found
no applicable CLI-filter or empty-selection Part.

recurrence_check: this confirms the same misclassification shape as the lint-go and missing-path
scanner findings, now with an explicit refusal contract.

verdict_note: complete and ready for independent review. The calibrator now calibrates its own
selector failure instead of reporting a false green.

## Boundary

Only scripts/calibrate_gates.py and tests/test_calibrate_gates.py changed for this order.
WO-CAL-1's Bench Report is the only other authored file. No Makefile or existing case behavior was
changed.

IN PLAIN TERMS
- I made a typo in the calibration selector fail loudly instead of pretending it calibrated something.
- That matters because a green result for a nonexistent case is no evidence at all.
- The durable concept is fail-closed selection: an empty answer caused by an unknown name is an error, not success.
