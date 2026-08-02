"""Fuzz / property tests: the telnet codec on the network trust boundary must never crash.

`strip_iac` decodes RAW bytes off the socket: a connecting client's answer to our option
negotiation, often glued to the client's input line (Mudlet et al. once broke logins this way). That
is an untrusted-input parser at a network trust boundary, so it must terminate and never raise on
ANY byte sequence -- a malformed or hostile IAC stream (a dangling IAC, an SB with no SE, all-IAC,
oversized) is a normal thing a broken client or an attacker sends. The prompt prioritizes fuzzing
exactly this boundary (Phase 17: telnet negotiation, GMCP, MSDP).

Framework evidence (implementation + test, NOT a compliance claim; verified against, not certified
to): NIST SSDF PW.8 (fuzzing) and SI-16; OWASP Top 10:2025 A10 (mishandling exceptional conditions);
NIST SP 800-53 SI-10 (input validation). Runs under `make fuzz`.
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from kernel.shelf.telnet_codec import IAC, SB, SE, escape_iac, read_negotiation, strip_iac

# Arbitrary bytes, plus an IAC-heavy strategy so hostile telnet framing (IAC, SB, SE, the WILL/WONT/
# DO/DONT verbs) appears often, not once in 256 -- the sequences a fuzzer must actually reach.
_arbitrary = st.binary(max_size=400)
_iac_heavy = st.lists(
    st.sampled_from([IAC, SB, SE, 251, 252, 253, 254, 1, 0, 65]), max_size=60
).map(bytes)
_telnet_bytes = st.one_of(_arbitrary, _iac_heavy)


@pytest.mark.fuzz
@given(_telnet_bytes)
@settings(max_examples=400, deadline=None)
def test_strip_iac_never_crashes_and_never_grows(data):
    # The core abuse case: any byte stream off the socket is decoded without raising or hanging, and
    # stripping only removes (a secret is never lengthened by an injected IAC sequence).
    out = strip_iac(data)
    assert isinstance(out, bytes)
    assert len(out) <= len(data)


@pytest.mark.fuzz
@given(_arbitrary)
@settings(max_examples=400, deadline=None)
def test_escape_then_strip_round_trips_any_payload(payload):
    # escape doubles every literal IAC; strip collapses IAC-IAC back to one. After escaping, no lone
    # IAC remains, so strip never mistakes a payload byte for a command: escape and strip are exact
    # inverses. A password containing byte 255 therefore survives intact -- no corruption, no leak.
    assert strip_iac(escape_iac(payload)) == payload


@pytest.mark.fuzz
@given(_telnet_bytes, st.integers(min_value=0, max_value=255))
@settings(max_examples=200, deadline=None)
def test_read_negotiation_never_crashes(data, option):
    # Reading a client's WILL/DO/WONT/DONT reply must tolerate arbitrary bytes for any option.
    result = read_negotiation(data, option)
    assert result is None or isinstance(result, bool)
