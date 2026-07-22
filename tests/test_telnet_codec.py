"""Tests for the telnet_codec card: command bytes, IAC escaping, stripping, negotiation reading.

Pure and socket-free. The hostile cases are the point: a literal 255 in a body, a subnegotiation
frame glued to input, an unterminated frame, a truncated negotiation, and a near-miss option must
all be handled without corrupting a command line or raising.
"""

from parts.shelf.telnet_codec import (
    DO,
    DONT,
    IAC,
    SB,
    SE,
    WILL,
    WONT,
    escape_iac,
    read_negotiation,
    strip_iac,
)

ECHO, GMCP = 1, 201


# --- constants -------------------------------------------------------------


def test_command_bytes_are_the_rfc_values():
    assert (IAC, SB, SE) == (255, 250, 240)
    assert (WILL, WONT, DO, DONT) == (251, 252, 253, 254)


# --- escape_iac ------------------------------------------------------------


def test_escape_doubles_a_literal_iac_byte():
    assert escape_iac(bytes([IAC])) == bytes([IAC, IAC])
    assert escape_iac(b"a" + bytes([IAC]) + b"b") == b"a" + bytes([IAC, IAC]) + b"b"


def test_escape_leaves_ordinary_bytes_untouched():
    assert escape_iac(b"Char.Vitals {}") == b"Char.Vitals {}"


# --- strip_iac (inbound decode) --------------------------------------------


def test_strip_removes_a_three_byte_negotiation_verb():
    assert strip_iac(bytes([IAC, DO, ECHO]) + b"north") == b"north"


def test_strip_keeps_an_escaped_literal_iac():
    assert strip_iac(b"a" + bytes([IAC, IAC]) + b"b") == b"a" + bytes([IAC]) + b"b"


def test_strip_skips_a_whole_subnegotiation_frame():
    # IAC SB NAWS 0 80 0 24 IAC SE glued to a secret must not leak its body into the input.
    frame = bytes([IAC, SB, 31, 0, 80, 0, 24, IAC, SE]) + b"swordfish"
    assert strip_iac(frame) == b"swordfish"


def test_strip_drops_an_unterminated_subnegotiation_to_the_end():
    assert strip_iac(bytes([IAC, SB, 31, 0, 80]) + b"leak") == b""


def test_strip_passes_plain_text_through_unchanged():
    assert strip_iac(b"look\r\n") == b"look\r\n"


# --- read_negotiation (option replies) -------------------------------------


def test_do_and_will_enable():
    assert read_negotiation(bytes([IAC, DO, GMCP]), GMCP) is True
    assert read_negotiation(bytes([IAC, WILL, GMCP]), GMCP) is True


def test_dont_and_wont_disable():
    assert read_negotiation(bytes([IAC, DONT, GMCP]), GMCP) is False
    assert read_negotiation(bytes([IAC, WONT, GMCP]), GMCP) is False


def test_no_negotiation_for_the_option_is_none():
    assert read_negotiation(b"look\r\n", GMCP) is None
    assert read_negotiation(bytes([IAC, DO, ECHO]), GMCP) is None  # different option


def test_the_last_matching_verb_wins():
    chunk = bytes([IAC, WILL, GMCP]) + bytes([IAC, DONT, GMCP])
    assert read_negotiation(chunk, GMCP) is False


def test_a_truncated_negotiation_does_not_raise():
    assert read_negotiation(bytes([IAC, DO]), GMCP) is None  # option byte never arrived
