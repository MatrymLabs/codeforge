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

EVERY CASE MUST INVOKE THE GATE, NOT THE BARE TOOL. This sounds pedantic and is not. Two proven
examples from this repo:

  - `cargo clippy --all-targets` exits 0 on the nav crate. `make lint-rust` runs the same clippy
    with `-D warnings` and exits 101 on the same code. A case built on the bare tool reported the
    lane calibrated while the actual gate was failing.
  - a mypy probe at the repository ROOT is invisible to `make typecheck-python`, because
    pyproject pins `files = ["kernel", "adapters", ...]`. The bare `python -m mypy <file>` caught
    it every time and the gate never saw the file at all.

Where a case still runs a tool directly it is because no make target wraps it yet, and that is
recorded on the case. Any such case proves the TOOL works; it does not prove the Workshop's gate
would catch it.

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
    insert_before: str | None = None
    """With `appends_to`, insert before the first line containing this marker instead of at the end.

    WHERE a probe lands can trip a different lint than the one under test. Appending to the end of
    a Rust lib.rs puts it after `#[cfg(test)] mod tests`, which fires
    `clippy::items_after_test_module` on every run: the gate reddens, but never for the reason the
    case is measuring, so the case can never pass no matter how the config changes.
    """
    benign: str | None = None
    """Clean contents for `probe`, used when the gate is pointed AT the probe file.

    Without this, the green-before check runs the gate against a file that does not exist yet:
    mypy exits 2, pytest exits 4, and the case reports "already red before planting" when nothing
    is wrong. For those gates the honest control is the SAME file holding clean contents, so the
    only variable between green and red is the defect itself.
    """
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
# The Option is a PARAMETER, not a literal `None`, and that detail is the whole case.
#
# The first version bound `let v: Option<i32> = None;` and unwrapped it. That reddens the gate,
# and the signal "unwrap" matched, so the case reported PASS on a branch where `unwrap_used` was
# not configured at all. The lint that actually fired was `clippy::unnecessary_literal_unwrap`,
# a DEFAULT lint about unwrapping a known-None literal, and "unwrap" also appears in clippy's echo
# of the offending source line. Loose signal plus a probe that trips a default lint equals a false
# PASS: the exact failure this harness exists to prevent, in the harness itself.
#
# Unwrapping a parameter is invisible to the default set and visible only to the opt-in
# restriction lint, so this now measures the setting it claims to measure.
# The trailing blank line is load-bearing: `make lint-rust` runs `cargo fmt --check` BEFORE
# clippy, so a probe that is merely unformatted fails the gate on formatting and never reaches
# the lint under test. The probe has to be clean by every gate it passes through, not just the
# one it is aimed at.
_RUST_UNWRAP = "pub fn calib_probe(v: Option<i32>) -> i32 {\n    v.unwrap()\n}\n\n"

# A test that raises a DeprecationWarning. Harmless until pytest's `filterwarnings = ["error"]`
# lands, at which point it must FAIL. That setting is the single highest-ROI line in the toolkit
# reference, and it is also the one most likely to be quietly reverted the first time it is
# inconvenient, so it gets a permanent probe.
_PY_WARNS = (
    _HEAD + "\nimport warnings\n\n\ndef test_calib_probe_emits_a_warning() -> None:\n"
    '    warnings.warn("calibration probe", DeprecationWarning, stacklevel=2)\n'
)

# B501, requests with TLS verification disabled: HIGH severity, HIGH confidence.
#
# The first probe here was subprocess(shell=True). Bandit DOES flag that, but rates a literal
# command string LOW, so a gate set to `--severity-level medium` filtered it out and this case
# reported the gate as broken. The gate was correct; the probe sat below its threshold. A
# calibration probe has to clear the bar the gate is actually set to, or it measures nothing.
_BANDIT_INSECURE = _HEAD + "\nimport requests\n\nrequests.get('https://x', verify=False)\n"

# A credential gitleaks must catch. ASSEMBLED AT RUN TIME, never written as one literal, because
# this file is itself scanned: a whole fake key sitting in the harness would make the repo's own
# secret gate red forever and teach everyone to ignore it. The prefix and body are joined below.
_LEAK_PREFIX = "AKIA"
# FLY002 wants this collapsed into one literal. It must NOT be: a whole credential-shaped string
# sitting in this file makes the repo's own secret gate red forever, and a permanently red secret
# gate is one everybody learns to ignore. The join is the point.
_LEAK_BODY = "".join(["QYLPZ3M7", "RTKW", "9XVB"])  # noqa: FLY002  # 16 chars, not the AWS example
_GITLEAKS = _HEAD + f'\nAWS_KEY = "{_LEAK_PREFIX}{_LEAK_BODY}"\n'

# Two defects that strict alone does NOT both catch. The type error is caught by strict; the
# unreachable line needs `warn_unreachable`, which strict does not include. Keeping them as
# separate cases is the point, because it proves the extra setting is doing work.
#
# Do NOT begin this comment with the word "mypy" followed by a colon. That form is an INLINE
# CONFIG DIRECTIVE, and mypy parsed the prose as options: "Unrecognized option: two defects
# strict alone does not both catch... = True". A comment that silently becomes configuration.
_MYPY_TYPE = _HEAD + "\n\ndef forge(spark: int) -> str:\n    return spark\n"
_MYPY_DEAD = (
    _HEAD + "\n\ndef forge() -> int:\n    return 1\n    print('unreachable')  # noqa: T201\n"
)


# Clean counterparts to the probes above. Same file, no defect: the only variable between
# the green run and the red run is the violation itself.
_OK_PYTEST = _HEAD + "\n\ndef test_calib_probe_is_quiet() -> None:\n    assert True\n"
_OK_BANDIT = _HEAD + "\nimport requests\n\nrequests.get('https://x')\n"
_OK_LEAK = _HEAD + '\nAWS_KEY = ""\n'
# These are deliberately a DIFFERENT LENGTH from the violations above, not just different text.
# mypy's incremental cache keys on mtime plus size, and `-> int` versus `-> str` is a same-size
# edit: written inside one second, the second run served the first run's verdict. Running the gate
# through `make` means no place to pass --no-incremental, so the probes defeat the cache by size.
_OK_MYPY = (
    _HEAD
    + "\n\n# calibration control, no defect\ndef forge(spark: int) -> int:\n    return spark\n"
)
_OK_DEAD = _HEAD + "\n\n# calibration control, no defect\ndef forge() -> int:\n    return 1\n"

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
        gate=["make", "lint-rust"],
        probe="native/codeforge_nav/src/lib.rs",
        appends_to="native/codeforge_nav/src/lib.rs",
        insert_before="#[cfg(test)]",
        violation=_RUST_UNWRAP,
        signal="unwrap_used",
        needs=("cargo",),
        extra_note=(
            "Was `cargo clippy --all-targets`, which exits 0 where `make lint-rust` exits 101, "
            "because the gate adds -D warnings. The bare tool called the lane calibrated while "
            "the real gate was failing."
        ),
    ),
    Case(
        name="pytest-filterwarnings-error",
        gate=["python", "-m", "pytest", "tests/test_calib_probe.py", "-q", "--no-header"],
        probe="tests/test_calib_probe.py",
        violation=_PY_WARNS,
        signal="DeprecationWarning",
        benign=_OK_PYTEST,
        extra_note="Runs one file, not the suite: calibration must stay cheap enough to run.",
    ),
    Case(
        name="bandit-insecure-tls",
        gate=[
            "bandit",
            "-c",
            "pyproject.toml",
            "-q",
            "--severity-level",
            "medium",
            "--confidence-level",
            "medium",
            "_calib_probe_bandit.py",
        ],
        probe="_calib_probe_bandit.py",
        violation=_BANDIT_INSECURE,
        signal="B501",
        benign=_OK_BANDIT,
        needs=("bandit",),
        extra_note="Separate pass from ruff S; the two can disagree and both are wired.",
    ),
    Case(
        name="gitleaks-hardcoded-credential",
        gate=["gitleaks", "dir", "--no-banner", "--redact", "_calib_probe_leak.py"],
        probe="_calib_probe_leak.py",
        violation=_GITLEAKS,
        signal="leaks found",  # --redact suppresses the rule id; this is the verdict line
        benign=_OK_LEAK,
        needs=("gitleaks",),
        extra_note="The highest-severity, least-reversible defect class: a secret in history.",
    ),
    Case(
        name="mypy-strict-type-error",
        gate=["make", "typecheck-python"],
        probe="kernel/_calib_probe_mypy.py",
        violation=_MYPY_TYPE,
        signal="Incompatible return value",
        benign=_OK_MYPY,
        extra_note="Caught by strict alone.",
    ),
    Case(
        name="mypy-warn-unreachable",
        gate=["make", "typecheck-python"],
        probe="kernel/_calib_probe_dead.py",
        violation=_MYPY_DEAD,
        signal="unreachable",
        benign=_OK_DEAD,
        extra_note="NOT in --strict. Proves warn_unreachable is doing work on its own.",
    ),
]


def _tool_missing(case: Case) -> str | None:
    for tool in case.needs:
        if shutil.which(tool) is None:
            return tool
    return None


def _run(cmd: list[str]) -> tuple[int, str]:
    # check=False is explicit and load-bearing: a NON-ZERO exit is the result this harness is
    # looking for, not an error. Letting subprocess raise would turn every successful calibration
    # into a crash.
    # S603 is acknowledged rather than suppressed blindly: every `cmd` here comes from the CASES
    # table in this file, never from input, and the gate commands are exactly the ones the
    # Makefile already runs.
    done = subprocess.run(  # noqa: S603
        cmd, cwd=REPO, capture_output=True, text=True, check=False
    )
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
        if case.insert_before:
            text = original.decode()
            marker = text.find(case.insert_before)
            if marker == -1:
                msg = f"{case.name}: marker {case.insert_before!r} not found in {case.appends_to}"
                raise RuntimeError(msg)
            head = text.rfind("\n", 0, marker) + 1
            target.write_bytes((text[:head] + case.violation + text[head:]).encode())
        else:
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

    def _control() -> int:
        """Run the gate against the clean state: an empty tree, or the benign probe."""
        if case.benign is None:
            return _run(case.gate)[0]
        target = REPO / case.probe
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(case.benign, encoding="utf-8", newline="\n")
        _run(["git", "add", "-N", case.probe])
        try:
            return _run(case.gate)[0]
        finally:
            _run(["git", "rm", "--cached", "--quiet", "--force", case.probe])
            target.unlink(missing_ok=True)

    if (before_rc := _control()) != 0:
        why = "the benign probe is already red" if case.benign else "the gate was ALREADY red"
        return FAIL, f"{why} before planting (exit {before_rc}); nothing is proven"

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

    if (after_rc := _control()) != 0:
        return FAIL, f"gate did not return GREEN after cleanup (exit {after_rc})"

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
