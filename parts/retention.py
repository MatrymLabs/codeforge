"""CARD: retention -- honest, hold-aware retention analysis for the Chronicle (read-only, R1).

The Chronicle is append-only and hash-chained: its records must not be mutated or removed, or the
chain (its one real guarantee) breaks. Retention here therefore means **disposition, not
deletion** - and R1 is *analysis only*: it makes retention visible (what is within its period,
what is eligible for review, what a hold protects) and offers a **dry-run plan**. It writes
nothing and removes nothing. Owner-gated marking arrives in R2; physical destruction, if ever, is
a later measurement-driven slice behind its own keel decision.

Federal rule #10 governs: a retention period only makes a record *eligible for review*; a human
decides, and **any hold wins** (litigation, audit, contract, CUI, ...). Nothing here claims a
legal disposition authority.

Provenance: original composition of CodeForge parts (chronicle, seed loader). No code copied.
See docs/reports/2026-07-14-retention-design.md for the design and the R1..R4 staging.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from parts.chronicle import Record


class RetentionError(ValueError):
    """A malformed policy/hold, or a disallowed action (real disposition in R1): fail loud."""


@dataclass(frozen=True)
class RetentionRule:
    """A record kind's advisory retention period and its records category."""

    kind: str
    period_days: int
    category: str


@dataclass(frozen=True)
class Hold:
    """An active hold that blocks disposition. `scope` is 'all', a kind, or 'subject:<prefix>'."""

    scope: str
    reason: str

    def covers(self, record: Record) -> bool:
        if self.scope == "all" or self.scope == record.kind:
            return True
        if self.scope.startswith("subject:"):
            prefix = self.scope.split(":", 1)[1]
            return str(record.payload.get("subject", "")).startswith(prefix)
        return False


@dataclass(frozen=True)
class DispositionPlan:
    """The read-only result of an analysis: nothing here has been or will be written or removed."""

    active: list[Record]  # still within its retention period
    blocked: list[tuple[Record, Hold]]  # eligible, but a hold protects it (any hold wins)
    candidates: list[Record]  # eligible AND unheld: a human may review for disposition (R2+)


# Advisory default periods, in days, per Chronicle kind. NOT legal retention authorities; they only
# move a record from "active" to "eligible for review". A kind absent here is never eligible (keep).
DEFAULT_POLICY = {
    "evidence": RetentionRule("evidence", 2555, "records"),  # ~7 years, advisory
    "metric": RetentionRule("metric", 1095, "operational"),  # ~3 years
    "edge": RetentionRule("edge", 2555, "records"),
    "incident": RetentionRule("incident", 2555, "safety"),
    "ai-eval": RetentionRule("ai-eval", 1095, "operational"),
}


def record_age_days(record: Record, today: date) -> int:
    """Whole days between a record's recorded date and `today` (negative if the stamp is future)."""
    try:
        recorded = date.fromisoformat(record.recorded_utc[:10])
    except ValueError as exc:
        raise RetentionError(
            f"record has an unreadable recorded_utc {record.recorded_utc!r}"
        ) from exc
    return (today - recorded).days


def is_eligible(record: Record, policy: dict[str, RetentionRule], today: date) -> bool:
    """True if the record is past its kind's advisory retention period (a kind with no rule: no)."""
    rule = policy.get(record.kind)
    return rule is not None and record_age_days(record, today) > rule.period_days


def held(record: Record, holds: list[Hold]) -> Hold | None:
    """The first hold covering the record, or None. Any hold blocks disposition (rule #10)."""
    for hold in holds:
        if hold.covers(record):
            return hold
    return None


def plan(
    records: list[Record],
    policy: dict[str, RetentionRule] | None = None,
    holds: list[Hold] | None = None,
    today: date | None = None,
) -> DispositionPlan:
    """Partition records into active / hold-blocked / disposition-candidate. Reads only."""
    policy = policy if policy is not None else DEFAULT_POLICY
    holds = holds if holds is not None else []
    when = today if today is not None else date.today()
    active: list[Record] = []
    blocked: list[tuple[Record, Hold]] = []
    candidates: list[Record] = []
    for record in records:
        if not is_eligible(record, policy, when):
            active.append(record)
            continue
        hold = held(record, holds)
        if hold is not None:
            blocked.append((record, hold))
        else:
            candidates.append(record)
    return DispositionPlan(active=active, blocked=blocked, candidates=candidates)


def dispose(
    records: list[Record],
    policy: dict[str, RetentionRule] | None = None,
    holds: list[Hold] | None = None,
    today: date | None = None,
    *,
    dry_run: bool = True,
) -> DispositionPlan:
    """Return the disposition plan. R1 is dry-run ONLY: a real run refuses (R2 is owner-gated)."""
    if not dry_run:
        raise RetentionError(
            "real disposition is owner-gated and arrives in R2; R1 is dry-run only (writes none)"
        )
    return plan(records, policy, holds, today)


def _label(record: Record) -> str:
    p = record.payload
    tag = p.get("subject") or p.get("what") or p.get("name") or p.get("from") or p.get("dimension")
    return f"[{record.kind}] {tag} @ {record.commit}"


def render_doctor(result: DispositionPlan) -> str:
    """An honest, read-only retention view. It shouts what a hold protects; it never acts."""
    lines = [
        "RETENTION DOCTOR (read-only, R1 dry-run: nothing is disposed or removed)",
        "",
        f"  active (within retention):          {len(result.active)}",
        f"  eligible, BLOCKED by a hold:        {len(result.blocked)}   (any hold wins, rule #10)",
        f"  eligible for disposition review:    {len(result.candidates)}   (a human decides; R2+)",
    ]
    if result.blocked:
        lines += ["", "  held (protected, will NOT be disposed):"]
        lines += [f"    {_label(r)}  <- held: {h.reason}" for r, h in result.blocked]
    if result.candidates:
        lines += ["", "  eligible for review (no hold; R1 takes no action):"]
        lines += [f"    {_label(r)}" for r in result.candidates]
    return "\n".join(lines)


def _load_yaml(path: Path) -> object:
    import yaml  # lazy: keep this module light for the import chain

    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (yaml.YAMLError, OSError) as exc:
        raise RetentionError(f"could not read {path}: {exc}") from exc


def load_policy(path: Path | None = None) -> dict[str, RetentionRule]:
    """The default policy, or a validated override from a YAML `{kind: {period_days, category}}`."""
    if path is None or not path.exists():
        return dict(DEFAULT_POLICY)
    raw = _load_yaml(path)
    if not isinstance(raw, dict):
        raise RetentionError(f"{path}: policy must be a mapping of kind -> settings")
    policy: dict[str, RetentionRule] = {}
    for kind, settings in raw.items():
        if not isinstance(settings, dict) or "period_days" not in settings:
            raise RetentionError(f"{path}: policy for {kind!r} needs a 'period_days'")
        days = settings["period_days"]
        if not isinstance(days, int) or isinstance(days, bool) or days < 0:
            raise RetentionError(f"{path}: period_days for {kind!r} must be a non-negative int")
        policy[str(kind)] = RetentionRule(str(kind), days, str(settings.get("category", "")))
    return policy


def load_holds(path: Path | None = None) -> list[Hold]:
    """No holds by default, or a validated list of `{scope, reason}` from YAML."""
    if path is None or not path.exists():
        return []
    raw = _load_yaml(path)
    if not isinstance(raw, list):
        raise RetentionError(f"{path}: holds must be a list of {{scope, reason}}")
    holds: list[Hold] = []
    for entry in raw:
        if not isinstance(entry, dict) or not entry.get("scope") or not entry.get("reason"):
            raise RetentionError(f"{path}: each hold needs a non-empty 'scope' and 'reason'")
        holds.append(Hold(str(entry["scope"]), str(entry["reason"])))
    return holds


def retention(arg: str = "") -> str:
    """The read-only `retention` verb: the retention doctor over the current Chronicle (R1)."""
    from parts import chronicle

    try:
        records = chronicle.read()
    except chronicle.ChronicleError as exc:
        return f"The Chronicle failed its integrity check: {exc}"
    return render_doctor(plan(records, load_policy(), load_holds(), date.today()))


def main(argv: list[str] | None = None) -> int:
    """`make retention`: print the read-only retention doctor for the current Chronicle."""
    print(retention())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
