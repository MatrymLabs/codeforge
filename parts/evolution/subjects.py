"""CARD: evolution.subjects -- the first bake-off subject: a fixed-width column formatter.

The first vertical slice (per the nature-inspired report) needs ONE small, well-contracted
component with several honest candidate implementations. We use `fit_column(text, width)` --
the primitive the ScoreSheetRenderer is built on: clip long text to the column, pad short
text with spaces, always return exactly `width` characters.

The shipped behavior is the CORRECTNESS ORACLE and the elite baseline. Three candidates
compete: two preserve the contract (they differ only in how), one (`extensible`) changes
observable behavior on truncation -- a real, caught defect that becomes a counterexample.
No autonomous mutation: these three strategies are hand-authored, exactly as v1 requires.
"""

from __future__ import annotations

from collections.abc import Callable

Formatter = Callable[[str, int], str]

# The oracle inputs: ordinary, exact-width, over-width (truncation), and empty. Hostile cases
# included on purpose (an all-happy-path oracle hides the very defect this lab exists to catch).
ORACLE_INPUTS: tuple[tuple[str, int], ...] = (
    ("hi", 5),
    ("hello", 5),  # exact width
    ("hello!", 5),  # over width -> truncates
    ("abcdef", 3),  # over width -> truncates
    ("", 3),  # empty -> all spaces
    ("x", 1),
)


def oracle_fit(text: str, width: int) -> str:
    """The reference contract (the shipped behavior): clip to width, else left-pad to width.
    Always returns exactly `width` characters. This is the elite baseline."""
    return text[:width].ljust(width)


def candidate_minimal(text: str, width: int) -> str:
    """Minimal / readable: the obvious one-liner. Preserves the contract."""
    return text[:width].ljust(width)


def candidate_performance(text: str, width: int) -> str:
    """Performance-oriented: pad by exact slice arithmetic, no method dispatch. Preserves it."""
    clipped = text[:width]
    return clipped + " " * (width - len(clipped))


def candidate_extensible(text: str, width: int) -> str:
    """Extensibility-oriented: marks truncation with a '>' so a reader sees text was cut.

    This is a DELIBERATE contract break: on over-width input it returns 'ab>' where the oracle
    returns 'abc'. The correctness gate must catch it -> counterexample -> rejected. It shows
    the lab refusing a candidate that changes observable behavior, however nice its intent.
    """
    if len(text) > width:
        return text[: width - 1] + ">"
    return text.ljust(width)
