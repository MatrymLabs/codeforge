#!/usr/bin/env bash
# CARD: cve_gate -- run pip-audit and say WHICH of three things happened, never two of them at once.
#
# THE FAULT THIS EXISTS TO CLOSE. `pip-audit` exits non-zero for two unrelated reasons: it found a
# vulnerability, or it could not reach the advisory service. The Makefile used to read both as
# "found a vulnerability", and on 2026-08-16 a PyPI `Connection reset by peer` reddened codeforge
# #996, a one-line Makefile change that touches no dependency. A gate that reports on the weather
# is not reporting on the code.
#
# The canary was worse. It ran pip-audit against a known-vulnerable fixture, discarded the output,
# and treated ANY non-zero exit as proof the gate had teeth. During that same outage it would have
# printed "ok: has teeth" while measuring nothing, because a crash is also non-zero. An instrument
# that cannot fail, in the one place whose whole job is proving another instrument can.
#
# FOUR OUTCOMES, NAMED SEPARATELY:
#   CLEAN       the runtime set has no known advisory
#   FAIL        a runtime dependency has a known advisory. This blocks, and is meant to.
#   UNVERIFIED  the advisory service could not be reached. NO claim is made about the code.
#   TOOLCHAIN   pip-audit itself is missing or unrunnable. NO claim is made about anything.
#
# The fourth outcome exists because the FIRST draft of this script did not have it, and reproduced
# the very defect it was written to close. With pip-audit absent the shell returned 127, 127 did
# not match the network signatures, so the classifier called it a FINDING and the canary printed
# "ok: has teeth" while measuring nothing. Caught on 2026-08-16 by running the canary in a shell
# where pip-audit was off PATH. An exit code is not a diagnosis: three different failures were
# wearing one number, and naming only two of them left the third to impersonate a pass.
#
# UNVERIFIED does not block, and that is a deliberate trade with a named cost. Blocking on it puts
# PyPI's uptime on the critical path of every pull request. Not blocking means a sustained outage
# could hide a real advisory for as long as it lasts. The mitigations are that retries make a
# transient blip very unlikely to survive, that the word UNVERIFIED is printed loudly rather than
# folded into a pass, and that `make patch` / `make daily` audit again on their own schedule.
# Silence would be the unacceptable version of this; a labelled gap is not.
set -uo pipefail

RETRIES="${CVE_GATE_RETRIES:-3}"

# Signatures of "the service was unreachable", never of "your dependency is vulnerable".
UNREACHABLE_RE='ConnectionError|Connection aborted|Connection reset|ConnectionResetError|Max retries|Temporary failure in name resolution|Name or service not known|TimeoutError|ReadTimeout|ConnectTimeout|Read timed out|ServiceUnavailable|BadGateway|HTTP 5[0-9][0-9]|502 |503 |504 |RemoteDisconnected|SSLError'

is_unreachable() {
    grep -qEi "${UNREACHABLE_RE}" "$1"
}

usage() {
    echo "usage: $0 audit <requirements-file> | canary <fixture-file>" >&2
    exit 2
}

# Run pip-audit against a file, retrying only when the failure looks like the network.
# Echoes nothing; leaves output in $2 and returns 0 CLEAN / 1 FINDING / 2 UNREACHABLE.
run_audit() {
    _target="$1"
    _out="$2"
    _rc=2
    _i=1
    while [ "${_i}" -le "${RETRIES}" ]; do
        pip-audit -r "${_target}" >"${_out}" 2>&1
        _code=$?
        [ "${_code}" -eq 0 ] && return 0
        # 126/127 mean the shell could not execute it at all. Belt and braces alongside the
        # preflight check: a tool that vanishes mid-run must not be read as a finding either.
        if [ "${_code}" -eq 127 ] || [ "${_code}" -eq 126 ]; then
            return 3
        fi
        if is_unreachable "${_out}"; then
            echo "  advisory service unreachable (attempt ${_i}/${RETRIES})" >&2
            _rc=2
            [ "${_i}" -lt "${RETRIES}" ] && sleep $((_i * 5))
        else
            return 1
        fi
        _i=$((_i + 1))
    done
    return "${_rc}"
}

mode="${1:-}"
target="${2:-}"
if [ -z "${mode}" ] || [ -z "${target}" ]; then
    usage
fi
[ -f "${target}" ] || { echo "cve_gate: no such file: ${target}" >&2; exit 2; }

# TOOLCHAIN check FIRST, before any outcome can be inferred from an exit code. A missing binary
# and a vulnerable dependency are different facts and must never share a verdict.
if ! command -v pip-audit >/dev/null 2>&1; then
    echo "cve_gate: TOOLCHAIN - pip-audit is not on PATH."
    echo "          This is a tooling fault. NOTHING was measured, no CVE claim is made, and this"
    echo "          is NOT evidence that the gate has teeth. Install it: see 'make env'."
    exit 2
fi

out="$(mktemp)"
# shellcheck disable=SC2064  # expand $out now, on purpose: the trap must name this file.
trap "rm -f '${out}'" EXIT

run_audit "${target}" "${out}"
rc=$?
cat "${out}"

case "${mode}" in
    audit)
        case "${rc}" in
            0) echo "audit-runtime: CLEAN - no known advisory in the runtime set" ;;
            1) echo "audit-runtime: FAIL - a runtime dependency has a known advisory"; exit 1 ;;
            3) echo "audit-runtime: TOOLCHAIN - pip-audit could not be executed. Nothing measured."; exit 2 ;;
            *) echo "audit-runtime: UNVERIFIED - the advisory service was unreachable after ${RETRIES} attempts."
               echo "               This is a NETWORK fault. It is NOT a clean audit and claims nothing"
               echo "               about the dependency set. Re-run, or rely on 'make patch' / 'make daily'." ;;
        esac
        ;;
    canary)
        # The canary asserts the gate BLOCKS, and blocks FOR THE RIGHT REASON. A crash is not teeth.
        case "${rc}" in
            0) echo "GATE CANARY FAILED: pip-audit did NOT flag the known-vulnerable fixture."
               echo "                    The CVE gate is toothless."; exit 1 ;;
            1) echo "  ok: the CVE gate flags the known-vulnerable fixture (has teeth)" ;;
            3) echo "GATE CANARY TOOLCHAIN: pip-audit could not be executed, so its non-zero exit says"
               echo "                       nothing about teeth. This is the exact false pass this script"
               echo "                       was written to close; do not read it as a green canary."
               exit 2 ;;
            *) echo "GATE CANARY UNVERIFIED: pip-audit exited non-zero because the advisory service was"
               echo "                        unreachable, NOT because it flagged the fixture. Nothing was"
               echo "                        proved about the gate's teeth either way." ;;
        esac
        ;;
    *) usage ;;
esac
