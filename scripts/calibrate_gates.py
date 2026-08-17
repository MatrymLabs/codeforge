#!/usr/bin/env python3
"""Calibrate a gate: prove it reddens for the bad state it claims to catch, then greens again.

The Workshop's rule is that an instrument is trusted only once it has been SHOWN to fail
(canon 13). Until this file existed that proof was done by hand, one gate at a time, and hand
calibration has two failure modes: it is slow enough to skip under pressure, and it leaves no
artifact, so the next session cannot tell a calibrated gate from an asserted one.

The tag-team rule adds the other half: the bench that WRITES a config must not calibrate it. This
harness is the calibrating bench's tool. It never edits a config; it plants a violation in a
throwaway file, runs the gate, and demands a specific signal in the output.

A case passes only if ALL of:
  1. the gate is GREEN before the plant       (else the tree was already dirty; nothing is proven)
  2. the gate is RED after the plant           (a gate that cannot fail is decoration)
  3. the RED output contains the expected signal (it failed for the RIGHT reason, not a syntax
     error in the probe or an unrelated pre-existing break)
  4. the gate is GREEN again after cleanup     (the probe left nothing behind)

Point 3 is the one that matters most and the one hand calibration usually skips. A gate that goes
red for the wrong reason looks identical to a gate that works.

Usage:
    python scripts/calibrate_gates.py              # every case whose gate exists
    python scripts/calibrate_gates.py --only ruff  # substring filter on case name
    python scripts/calibrate_gates.py --list
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"


@dataclass(frozen=True)
class Case:
    """One gate, one planted defect, one signal that proves it was caught for the right reason."""

    name: str
    gate: list[str]
    """The gate command. Run from the repo root."""
    probe: str
    """Path, relative to the repo root, of a file this case creates and then deletes."""
    violation: str
    """The contents of the probe file: a defect the gate is claimed to catch."""
    signal: str
    """A string that MUST appear in the red output. This is what proves the right reason."""
    needs: tuple[str, ...] = ()
    """Tools that must be on PATH. A missing tool is SKIP, never PASS."""
    appends_to: str | None = None
    """If set, append `violation` to this existing file instead of creating `probe`."""
    extra_note: str = field(default="")


_HEAD = '"""Calibration probe."""\n'
_ARG = _HEAD + "\n\ndef forge(spark: int, unused_relic: str) -> int:\n    return spark\n"
_SHELL_TRUE = _HEAD + '\nimport subprocess\n\nsubprocess.run("ls", shell=True)\n'
_BROAD = (
    _HEAD + "\n\ndef trace() -> None:\n    try:\n        pass\n"
    "    except Exception:\n        pass\n"
)
_UNQUOTED = '#!/usr/bin/env bash\nfoo=$1\nif [ $foo = "x" ]; then echo hi; fi\n'
_TF_DRIFT = 'variable   "calib_probe"   {\n  type=string\n    default="x"\n}\n'
_C_UNUSED = "\nstatic int _calib_probe(int unused_arg) { return 0; }\n"
_GO_IGNORED = '\nfunc calibProbe() {\n\tos.Setenv("CALIB_PROBE", "1")\n}\n'
_RUST_UNWRAP = (
    "\npub fn calib_probe() -> i32 {\n    let v: Option<i32> = None;\n    v.unwrap()\n}\n"
)

# The battery. Each case names a defect class the Workshop has actually shipped or expects from
# an AI bench, per the toolkit reference's agent-defect table.
#
# Go and Rust APPEND to an existing compiled file rather than dropping a loose one. A loose .rs is
# never compiled without a `mod` declaration, and a loose .go file in package main still has to be
# reached by the build. Both looked GREEN in the first run of this harness, which would have read
# as "the gate does not catch unwrap" when the truth was "the probe was never compiled". A
# calibration harness that mis-reports WHY a gate stayed green is worse than none.
CASES: list[Case] = [
    Case(
        name="ruff-ARG-unused-argument",
        gate=["make", "lint-python"],
        probe="_calib_probe_arg.py",
        violation=_ARG,
        signal="ARG001",
        extra_note="ARG catches the unused-argument class agents produce constantly.",
    ),
    Case(
        name="ruff-S-subprocess-shell",
        gate=["make", "lint-python"],
        probe="_calib_probe_shell.py",
        violation=_SHELL_TRUE,
        signal="S602",
        extra_note="Bandit-style S rules; shell=True is the server-platform defect class.",
    ),
    Case(
        name="ruff-BLE-broad-except",
        gate=["make", "lint-python"],
        probe="_calib_probe_except.py",
        violation=_BROAD,
        signal="BLE001",
        extra_note="Over-broad except: the most common agent exception defect.",
    ),
    Case(
        name="shellcheck-unquoted-variable",
        gate=["make", "lint-shell"],
        probe="scripts/_calib_probe.sh",
        violation=_UNQUOTED,
        signal="SC2086",
        needs=("shellcheck",),
    ),
    Case(
        name="terraform-fmt-drift",
        gate=["make", "lint-terraform"],
        probe="deploy/terraform/_calib_probe.tf",
        violation=_TF_DRIFT,
        signal="_calib_probe.tf",
        needs=("terraform",),
    ),
    Case(
        name="c-unused-parameter",
        gate=["make", "lint-c"],
        probe="native/textkernel/src/textkernel.c",
        appends_to="native/textkernel/src/textkernel.c",
        violation=_C_UNUSED,
        signal="unused-parameter",
        needs=("gcc",),
        extra_note="gcc and clang word this differently; the signal matches both.",
    ),
    Case(
        name="go-errcheck-ignored-error",
        gate=["make", "lint-go"],
        probe="native/edge/edge.go",
        appends_to="native/edge/edge.go",
        violation=_GO_IGNORED,
        signal="Setenv",
        needs=("golangci-lint", "go"),
        extra_note="Needs `os` imported by edge.go already.",
    ),
    Case(
        name="rust-clippy-unwrap",
        gate=[
            "cargo",
            "clippy",
            "--manifest-path",
            "native/codeforge_nav/Cargo.toml",
            "--all-targets",
        ],
        probe="native/codeforge_nav/src/lib.rs",
        appends_to="native/codeforge_nav/src/lib.rs",
        violation=_RUST_UNWRAP,
        signal="unwrap",
        needs=("cargo",),
        extra_note="Green until ORDER 3 lands unwrap_used. That is the point.",
    ),
]


def _tool_missing(case: Case) -> str | None:
    for tool in case.needs:
        if shutil.which(tool) is None:
            return tool
    return None


def _run(cmd: list[str]) -> tuple[int, str]:
    done = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
    return done.returncode, done.stdout + done.stderr


def _plant(case: Case) -> bytes | None:
    """Write the violation. Returns the original bytes when appending, so it can be restored.

    A NEW probe is registered with `git add -N`. Several gates here enumerate their inputs with
    `git ls-files` rather than a filesystem glob, so an untracked probe is INVISIBLE to them. The
    first run of this harness reported "shellcheck does not catch SC2086" for exactly that reason.
    The gate was fine; the probe was never handed to it. An intent-to-add keeps the file out of a
    real commit while making it visible to git.
    """
    target = REPO / (case.appends_to or case.probe)
    if case.appends_to:
        original = target.read_bytes()
        target.write_bytes(original + case.violation.encode())
        return original
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(case.violation, encoding="utf-8", newline="\n")
    _run(["git", "add", "-N", case.probe])
    return None


def _clean(case: Case, original: bytes | None) -> None:
    target = REPO / (case.appends_to or case.probe)
    if original is not None:
        target.write_bytes(original)
        return
    _run(["git", "rm", "--cached", "--quiet", "--force", case.probe])
    target.unlink(missing_ok=True)


def calibrate(case: Case) -> tuple[str, str]:
    missing = _tool_missing(case)
    if missing:
        return SKIP, f"{missing} is not on PATH, so this gate cannot be calibrated (not a pass)"

    before_rc, _ = _run(case.gate)
    if before_rc != 0:
        return FAIL, f"gate was ALREADY red before planting (exit {before_rc}); nothing is proven"

    original = _plant(case)
    try:
        red_rc, red_out = _run(case.gate)
    finally:
        _clean(case, original)

    if red_rc == 0:
        return FAIL, "gate stayed GREEN with the violation planted: it does not catch this"
    if case.signal not in red_out:
        head = " | ".join(line.strip() for line in red_out.splitlines() if line.strip())[:160]
        return FAIL, f"went red but WITHOUT the expected signal {case.signal!r}. Saw: {head}"

    after_rc, _ = _run(case.gate)
    if after_rc != 0:
        return FAIL, "gate did not return GREEN after cleanup; the probe left something behind"

    return PASS, f"green -> RED on {case.signal} -> green"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", help="substring filter on the case name")
    ap.add_argument("--list", action="store_true", help="list cases and exit")
    args = ap.parse_args()

    cases = [c for c in CASES if not args.only or args.only in c.name]
    if args.list:
        for case in cases:
            print(f"  {case.name:<32} gate: {' '.join(case.gate)}")
        return 0

    print(f"Gate calibration  ({len(cases)} case(s))\n")
    tally = {PASS: 0, FAIL: 0, SKIP: 0}
    for case in cases:
        verdict, detail = calibrate(case)
        tally[verdict] += 1
        print(f"  [{verdict}] {case.name:<32} {detail}")

    print(
        f"\n{tally[PASS]} calibrated, {tally[FAIL]} FAILED, "
        f"{tally[SKIP]} skipped (toolchain absent)"
    )
    if tally[FAIL]:
        print("A gate that will not redden is UNTRUSTED. Do not report green over it.")
    return 1 if tally[FAIL] else 0


if __name__ == "__main__":
    raise SystemExit(main())
