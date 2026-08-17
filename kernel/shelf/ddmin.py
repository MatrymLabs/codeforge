"""CARD: ddmin -- delta debugging: minimize a failing input to its smallest reproducer.

The second rung of the R&D Debugging Lab (from the "Automating Debugging, Fixing,
Optimization" research brief, which lists delta debugging as "mature, practical, safe -
deterministic, reversible"). Given a failing input and an oracle that says whether a
subset still reproduces the failure, `ddmin` shrinks the input to a 1-MINIMAL subset:
removing any single remaining element makes the failure go away.

This is the honest, deterministic triage tool the brief prefers over opaque LLM repair:
every step is a real oracle call, the result is reproducible, and nothing is guessed.

The oracle is INJECTED (a seam) - `ddmin` never runs a test suite itself; the caller
supplies `still_fails(subset) -> bool`. That keeps it pure, testable, and framework-free.

Clean-room, stdlib only.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field


class DeltaError(ValueError):
    """Raised when the full input does not actually reproduce the failure."""


@dataclass(frozen=True)
class Reduction:
    """The result of delta-debugging: the smallest still-failing input found."""

    minimal: tuple[object, ...]
    original_size: int
    oracle_calls: int
    is_one_minimal: bool  # verified: removing any single element makes it pass
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def reduced_size(self) -> int:
        return len(self.minimal)


def _split[T](seq: list[T], n: int) -> list[list[T]]:
    """Split a list into n contiguous, roughly-equal, non-empty chunks."""
    k, m = divmod(len(seq), n)
    chunks: list[list[T]] = []
    start = 0
    for i in range(n):
        size = k + (1 if i < m else 0)
        if size:
            chunks.append(seq[start : start + size])
        start += size
    return chunks


def ddmin[T](  # noqa: PLR0912, PLR0915
    sequence: Sequence[T],
    still_fails: Callable[[list[T]], bool],
    *,
    max_calls: int = 100_000,
) -> Reduction:
    """Minimize `sequence` to a 1-minimal subset that still satisfies `still_fails`.

    still_fails(subset) must return True when the subset reproduces the failure. The full
    sequence MUST fail (else there is nothing to minimize) - that is validated up front.
    max_calls caps oracle calls (the brief warns to bound iteration); on hitting the cap
    the best reduction so far is returned with a note.
    """
    seq: list[T] = list(sequence)
    calls = 0

    def oracle(subset: list[T]) -> bool:
        nonlocal calls
        calls += 1
        return still_fails(subset)

    if not oracle(seq):
        raise DeltaError("the full input does not reproduce the failure (nothing to minimize)")  # noqa: TRY003

    notes: list[str] = []
    capped = False
    n = 2
    while len(seq) >= 2:  # noqa: PLR2004
        if calls >= max_calls:
            capped = True
            break
        chunks = _split(seq, min(n, len(seq)))
        reduced = False

        # phase 1: does any single chunk still fail? -> shrink hard, reset granularity
        for chunk in chunks:
            if calls >= max_calls:
                capped = True
                break
            if oracle(chunk):
                seq = chunk
                n = 2
                reduced = True
                break
        if capped:
            break
        if reduced:
            continue

        # phase 2: does removing any chunk still fail? -> drop it, lower granularity
        offset = 0
        for chunk in chunks:
            complement = seq[:offset] + seq[offset + len(chunk) :]
            offset += len(chunk)
            if not complement or len(complement) == len(seq):
                continue
            if calls >= max_calls:
                capped = True
                break
            if oracle(complement):
                seq = complement
                n = max(n - 1, 2)
                reduced = True
                break
        if capped:
            break
        if reduced:
            continue

        # phase 3: increase granularity, or stop if already maximal
        if n >= len(seq):
            break
        n = min(n * 2, len(seq))

    if capped:
        notes.append(f"stopped at the max_calls cap ({max_calls}); result may not be 1-minimal")

    # verify 1-minimality (unless we bailed on the cap): every single-element removal must pass
    is_one_minimal = False
    if not capped:
        is_one_minimal = True
        for i in range(len(seq)):
            calls += 1
            if still_fails(seq[:i] + seq[i + 1 :]):
                is_one_minimal = False
                notes.append("not 1-minimal: an inconsistent oracle let a smaller input still fail")
                break

    return Reduction(
        minimal=tuple(seq),
        original_size=len(sequence),
        oracle_calls=calls,
        is_one_minimal=is_one_minimal,
        notes=tuple(notes),
    )


def minimize_string(text: str, still_fails: Callable[[str], bool], **kw: int) -> Reduction:
    """Convenience: delta-debug a string character-by-character."""
    return ddmin(list(text), lambda chars: still_fails("".join(chars)), **kw)


def minimize_lines(text: str, still_fails: Callable[[str], bool], **kw: int) -> Reduction:
    """Convenience: delta-debug a multi-line string line-by-line."""
    return ddmin(text.splitlines(), lambda lines: still_fails("\n".join(lines)), **kw)


def render(reduction: Reduction) -> str:
    """A human-readable rendering of the reduction."""
    summary = (
        f"delta debugging: {reduction.original_size} -> {reduction.reduced_size} elements "
        f"in {reduction.oracle_calls} oracle calls "
        f"({'1-minimal' if reduction.is_one_minimal else 'NOT verified 1-minimal'})"
    )
    lines = [summary, f"  minimal reproducer: {list(reduction.minimal)!r}"]
    for note in reduction.notes:
        lines.append(f"  note: {note}")
    return "\n".join(lines)
