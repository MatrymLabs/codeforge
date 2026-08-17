"""CARD: addie -- the ADDIE loop: a systems-engineering self-check so CodeForge learns in a loop.

CodeForge should not move in a straight line; it should learn in a loop. When it plans, builds,
changes, tests, or evaluates anything (a feature, subsystem, workflow, client capability, Hardware
Store part, Blueprint, Seed, automation, or fleet integration), it runs the five-phase cycle:
ANALYZE the need, DESIGN the response, DEVELOP the capability, IMPLEMENT it in the real system,
EVALUATE it against the vision and the evidence, then REANALYZE (docs/addie_loop.md).

ADDIE adds NO new authority and overrides no established control (Blueprints, ARC, AURA, Ritual, the
Hardware Store, testing, security, documentation, fleet governance). It is the loop those controls
run inside. This card is the machine-checkable side: an `AddieSelfCheck` record with the five phases
plus the loop-back, a `gaps` validator that names the four failure modes the loop exists to
prevent -- building without understanding, designing without evidence, implementing without
integration, declaring success without evaluation -- and a ledger of the MAJOR cycles CodeForge has
run. Minor work runs the check silently (nothing filed); major work files a brief self-check, and
`make addie` fails loud if any filed cycle skipped a phase. Frameless: stdlib only (tomllib).
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_LEDGER = _ROOT / "addie_ledger.toml"

# The circular operating method. Each phase carries the question it must answer before the next
# phase may claim to be done; the loop closes by reanalyzing (the sixth move is back to the first).
PHASES: tuple[tuple[str, str], ...] = (
    ("analyze", "What problem, gap, constraints, and evidence-of-success?"),
    ("design", "What smallest coherent solution, where it belongs, its boundaries/tests/rollback?"),
    ("develop", "What was built - controlled, modular, testable, reusing existing parts?"),
    ("implement", "Where it integrated - commands, Ritual, Blueprints, Cards, docs, consumers?"),
    ("evaluate", "What evidence shows it worked against the problem, tests, security, the vision?"),
)

# A cycle is either MINOR (checked silently, not filed) or MAJOR (a brief self-check is filed and
# must close the whole loop). The distinction keeps the discipline lightweight, per the doctrine.
SCALES = frozenset({"minor", "major"})

# The four failure modes the loop exists to prevent, plus the two that complete it, keyed by the
# phase whose absence causes them. A MAJOR cycle missing any of these has not really looped.
_FAILURE = {
    "analyze": "built without understanding (ANALYZE is empty)",
    "design": "designed without evidence (DESIGN is empty)",
    "develop": "developed nothing (DEVELOP is empty)",
    "implement": "implemented without integration (IMPLEMENT is empty)",
    "evaluate": "declared success without evaluation (EVALUATE is empty)",
}


class AddieError(RuntimeError):
    """A malformed ADDIE ledger fails loud, never silently passes."""


@dataclass(frozen=True)
class AddieSelfCheck:
    """One ADDIE cycle. `data` holds the raw fields; the accessors read the phases the gate checks.
    An absent field reads as empty, so a skipped phase is a missing string."""

    cycle_id: str
    data: dict[str, object]

    def _text(self, key: str) -> str:
        value = self.data.get(key, "")
        return value.strip() if isinstance(value, str) else ""

    @property
    def subject(self) -> str:
        return self._text("subject")

    @property
    def scale(self) -> str:
        return self._text("scale") or "major"

    @property
    def analyze(self) -> str:
        return self._text("analyze")

    @property
    def design(self) -> str:
        return self._text("design")

    @property
    def develop(self) -> str:
        return self._text("develop")

    @property
    def implement(self) -> str:
        return self._text("implement")

    @property
    def evaluate(self) -> str:
        return self._text("evaluate")

    @property
    def next_cycle(self) -> str:
        return self._text("next_cycle")


def self_check(
    subject: str,
    *,
    scale: str = "major",
    analyze: str = "",
    design: str = "",
    develop: str = "",
    implement: str = "",
    evaluate: str = "",
    next_cycle: str = "",
) -> AddieSelfCheck:
    """Build an ADDIE self-check in code (the operating method, not just the ledger). Pair with
    `gaps` to refuse an incomplete loop, or `render_self_check` to show the brief self-check."""
    return AddieSelfCheck(
        "(inline)",
        {
            "subject": subject,
            "scale": scale,
            "analyze": analyze,
            "design": design,
            "develop": develop,
            "implement": implement,
            "evaluate": evaluate,
            "next_cycle": next_cycle,
        },
    )


def gaps(check: AddieSelfCheck) -> list[str]:
    """Every reason a cycle has not really looped, in order, or an empty list when it is sound.

    A minor cycle is run silently and needs only its subject. A major cycle must close the whole
    loop: every phase carries content, and it names the next reanalysis (learn in a loop).
    """
    found: list[str] = []
    if not check.subject:
        found.append("no subject: name the feature/subsystem/change under review")
    if check.scale not in SCALES:
        found.append(f"unknown scale {check.scale!r} (expected one of {sorted(SCALES)})")
    if check.scale == "major":
        found.extend(msg for phase, msg in _FAILURE.items() if not getattr(check, phase))
        if not check.next_cycle:
            found.append("loop left open: no next cycle to reanalyze (CodeForge learns in a loop)")
    return found


def read_ledger(path: Path = _LEDGER) -> list[AddieSelfCheck]:
    """Read the ADDIE ledger into cycles. Each `[cycle.<id>]` table is one filed cycle. A missing or
    malformed ledger fails loud."""
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AddieError(f"ADDIE ledger not found at {path}") from exc  # noqa: TRY003
    except tomllib.TOMLDecodeError as exc:
        raise AddieError(f"malformed ADDIE ledger: {exc}") from exc  # noqa: TRY003
    cycles = raw.get("cycle", {})
    if not isinstance(cycles, dict):
        raise AddieError("ADDIE ledger: [cycle] must be a table of records")  # noqa: TRY003
    return [AddieSelfCheck(cycle_id, fields) for cycle_id, fields in cycles.items()]


@dataclass(frozen=True)
class AddieAudit:
    """The verdict: the cycles read, and every one that did not close its loop (with its gaps)."""

    cycles: list[AddieSelfCheck]
    flagged: dict[str, list[str]]

    @property
    def passed(self) -> bool:
        return not self.flagged


def audit_addie(ledger: Path = _LEDGER) -> AddieAudit:
    """Read the ledger and flag every filed cycle that skipped a phase or left the loop open."""
    cycles = read_ledger(ledger)
    flagged = {cycle.cycle_id: g for cycle in cycles if (g := gaps(cycle))}
    return AddieAudit(cycles, flagged)


def render_self_check(check: AddieSelfCheck) -> str:
    """The brief ADDIE Self-Check block the doctrine asks for on major work."""
    return "\n".join(
        [
            f"ADDIE Self-Check: {check.subject or '(unnamed)'} [{check.scale}]",
            f"  Analyze:    {check.analyze or '-'}",
            f"  Design:     {check.design or '-'}",
            f"  Develop:    {check.develop or '-'}",
            f"  Implement:  {check.implement or '-'}",
            f"  Evaluate:   {check.evaluate or '-'}",
            f"  Next cycle: {check.next_cycle or '-'}",
        ]
    )


def render_addie(ledger: Path = _LEDGER) -> str:
    """The gate's human report (used by `make addie` and any in-game terminal)."""
    audit = audit_addie(ledger)
    verdict = "PASS" if audit.passed else "FAIL"
    major = sum(1 for c in audit.cycles if c.scale == "major")
    lines = [
        f"ADDIE loop: {verdict}",
        f"  filed cycles: {len(audit.cycles)}   major: {major}   flagged: {len(audit.flagged)}",
    ]
    for cycle_id, reasons in sorted(audit.flagged.items()):
        lines.append(f"  FAIL {cycle_id}:")
        lines.extend(f"    - {reason}" for reason in reasons)
    if audit.passed:
        lines.append("  every filed cycle closed its loop (analyze -> evaluate -> reanalyze).")
    return "\n".join(lines)


def addie(arg: str = "") -> str:
    """The `addie` / `addie status` verb: the world's window onto the filed continuous-improvement
    cycles. Text is a projection, never a mutation (architecture law 1)."""
    sub = arg.strip().lower()
    if sub in ("", "status"):
        return render_addie()
    return "Unknown addie action. Try: addie status"


def main(argv: list[str] | None = None) -> int:  # noqa: ARG001
    """`python -m kernel.addie` / `make addie`: print the report, exit non-zero on a FAIL."""
    print(render_addie())
    return 0 if audit_addie().passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
