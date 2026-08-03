"""CARD: color -- an ANSI color-markup renderer for MUD text.

Turns terminal-friendly markup tags (`|r`, `|G`, `|500`, `|n`) into ANSI
escape codes, strips them for no-color clients and logs, and measures the
visible length of a marked-up string for column alignment.

Pattern harvested clean-room (pattern-not-code) from Evennia's
`utils/ansi.py` and `utils/hex_colors.py` (BSD-3-Clause). No source lines
were copied; only the markup convention (a leading pipe, single-letter
foreground codes, an `xterm-256` RGB cube, `|n` reset, `||` literal pipe)
was reused.

Markup grammar:
- `|r |g |b |y |c |m |w |x`      normal foreground (x is grey)
- `|R |G |B |Y |C |M |W`         bright foreground
- `|n`                           reset all attributes
- `||`                           a literal pipe character
- `|500` style (three digits 0-5) a point in the 6x6x6 RGB cube -> xterm-256

Any other `|<char>` sequence is a malformed tag and raises ColorError loud.
A colorized string that used any color always ends with a reset, so a
renderer can never leave a terminal stuck in a color (no dangling escape).
"""

from __future__ import annotations

import re

# Public entry points.
__all__ = ["ColorError", "colorize", "render", "strip", "visible_len"]

# ANSI control pieces.
_ESC = "\033["
_RESET = _ESC + "0m"

# Normal foreground colors: tag letter -> SGR color number (30-37).
_NORMAL_FG = {
    "x": 30,  # grey / black
    "r": 31,
    "g": 32,
    "y": 33,
    "b": 34,
    "m": 35,
    "c": 36,
    "w": 37,
}

# Bright foreground colors: tag letter -> SGR bright color number (90-97).
_BRIGHT_FG = {
    "R": 91,
    "G": 92,
    "Y": 93,
    "B": 94,
    "M": 95,
    "C": 96,
    "W": 97,
}

# A single markup token: an escaped pipe, an RGB cube triple, or a single
# code character. The pipe itself is matched first so `||` never splits.
_TOKEN = re.compile(r"\|(\|)|\|([0-5]{3})|\|(.)", re.DOTALL)


class ColorError(ValueError):
    """Raised loud when the markup contains a malformed or unknown tag."""


def _cube_escape(triple: str) -> str:
    """Turn a three-digit `rgb` cube tag (each 0-5) into an xterm-256 escape."""
    red, green, blue = (int(digit) for digit in triple)
    index = 16 + 36 * red + 6 * green + blue
    return f"{_ESC}38;5;{index}m"


def _fg_escape(code: str) -> str:
    """Turn a single foreground code character into an ANSI escape, or reset."""
    if code == "n":
        return _RESET
    if code in _NORMAL_FG:
        return f"{_ESC}{_NORMAL_FG[code]}m"
    if code in _BRIGHT_FG:
        return f"{_ESC}{_BRIGHT_FG[code]}m"
    raise ColorError(f"unknown color tag: |{code}")


def colorize(text: str) -> str:
    """Replace markup tags with ANSI escapes.

    `||` becomes a literal pipe, `|n` resets, `|<letter>` and `|<rgb>` become
    color escapes. An unknown tag raises ColorError. If any color escape was
    emitted the result ends with a reset, so no dangling escape can leak.
    """
    used_color = False
    out: list[str] = []
    last = 0
    for match in _TOKEN.finditer(text):
        out.append(text[last : match.start()])
        last = match.end()
        literal_pipe, cube, code = match.group(1), match.group(2), match.group(3)
        if literal_pipe is not None:
            out.append("|")
        elif cube is not None:
            out.append(_cube_escape(cube))
            used_color = True
        else:
            escape = _fg_escape(code)
            out.append(escape)
            if escape != _RESET:
                used_color = True
    tail = text[last:]
    _guard_trailing_pipe(tail)
    out.append(tail)
    if used_color and not "".join(out).endswith(_RESET):
        out.append(_RESET)
    return "".join(out)


def strip(text: str) -> str:
    """Remove all markup tags, leaving clean text (for no-color clients, logs)."""
    out: list[str] = []
    last = 0
    for match in _TOKEN.finditer(text):
        out.append(text[last : match.start()])
        last = match.end()
        literal_pipe, cube, code = match.group(1), match.group(2), match.group(3)
        if literal_pipe is not None:
            out.append("|")
        elif cube is None and code not in _NORMAL_FG and code not in _BRIGHT_FG and code != "n":
            raise ColorError(f"unknown color tag: |{code}")
    tail = text[last:]
    _guard_trailing_pipe(tail)
    out.append(tail)
    return "".join(out)


def render(text: str, *, color: bool = True) -> str:
    """One entry point: colorize when `color` is true, otherwise strip."""
    return colorize(text) if color else strip(text)


def visible_len(text: str) -> int:
    """Length of the text with all tags stripped (for column alignment)."""
    return len(strip(text))


def _guard_trailing_pipe(tail: str) -> None:
    """A lone trailing `|` is a truncated tag: fail loud, never emit it raw."""
    if tail.endswith("|"):
        raise ColorError("dangling pipe: markup ends with an unterminated tag")
