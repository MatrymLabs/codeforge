"""CARD: hubble.grounding -- produce the retrieval-grounding finding the gate escalates on.

RD-2026-0002 #15. `hubble.diagnosis` lists `retrieval_grounding` as a NON-OVERRIDABLE escalation
class, but nothing in the fleet PRODUCES that finding -- the gate consumes a dimension no one feeds.
This is the producer: it checks that the claims a proposed change makes are GROUNDED in evidence
that actually exists (a cited file path resolves; a cited symbol is really defined), and emits a
`DiagnosticFinding(dimension="retrieval_grounding", ...)` that `decide()` already knows how to act
on. Ungrounded claims -- a citation to a file that is not there, a symbol nobody defined -- are the
hallucination signal; catching them forces the "consult the attending" escalation.

The existence check is INJECTED (a `Resolver` seam): tests pass a fake, real use passes a filesystem
resolver. Honest scope: this verifies a claim's citation RESOLVES, not that the claim is true --
grounding is necessary for trust, not sufficient. Clean-room, stdlib only.
"""

from __future__ import annotations

import ast
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from kernel.hubble.diagnosis import DiagnosticFinding

# A resolver answers "does this cited evidence exist?" for one claim. Injected so tests never touch
# a real filesystem; `filesystem_resolver` is the real-use implementation.
Resolver = Callable[["Claim"], bool]


class GroundingError(ValueError):
    """Raised on a malformed claim (e.g. an empty citation)."""


@dataclass(frozen=True)
class Claim:
    """One grounded assertion a change makes: a cited path, optionally a symbol defined in it."""

    text: str  # the human-readable claim, e.g. "reuses the cursor part"
    path: str  # the file it cites as evidence
    symbol: str = ""  # an optional function/class the claim says lives in that file

    def __post_init__(self) -> None:
        if not self.path.strip():
            raise GroundingError(f"claim {self.text!r} cites no path")


def filesystem_resolver(root: Path | str) -> Resolver:
    """A resolver that checks a claim against a real tree: the path exists, and (if a symbol is
    named) it is really defined there (via ast, so a mention in a comment does not count)."""
    base = Path(root)

    def resolve(claim: Claim) -> bool:
        target = base / claim.path
        if not target.is_file():
            return False
        if not claim.symbol:
            return True
        try:
            tree = ast.parse(target.read_text("utf-8"), filename=str(target))
        except (SyntaxError, OSError):
            return False
        defined = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        }
        return claim.symbol in defined

    return resolve


def check_grounding(
    claims: list[Claim], resolver: Resolver, *, weight: float = 1.0
) -> DiagnosticFinding:
    """Emit the retrieval_grounding finding for a set of claims: passed iff EVERY claim resolves.

    An empty claim set passes (nothing was asserted, nothing to hallucinate); one unresolved
    citation fails the whole finding, because a single ungrounded claim is enough to warrant a human
    look (the gate treats retrieval_grounding as non-overridable)."""
    ungrounded = [c for c in claims if not resolver(c)]
    if not ungrounded:
        return DiagnosticFinding(
            "retrieval_grounding", True, weight, "all claims grounded in evidence"
        )
    detail = "; ".join(
        f"{c.text!r} cites {c.path}" + (f"::{c.symbol}" if c.symbol else "") for c in ungrounded
    )
    return DiagnosticFinding("retrieval_grounding", False, weight, f"ungrounded: {detail}")
