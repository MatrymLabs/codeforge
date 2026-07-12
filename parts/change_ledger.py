"""CARD: change_ledger -- a Change/Patch engine: record changes and gate them through a lifecycle.

The first slice of the Software Evolution Engine (research: patch/change management). A `Change`
records a patch's facts (id, kind, severity, CVEs, components, rollback plan) and walks a gated
lifecycle: identified -> triaged -> approved -> building -> testing -> canary -> deployed ->
verified -> closed, with reject and rollback edges. Approval and deploy are role-gated, and a change
cannot reach canary until it has PASSING test evidence.

Assembled from parts already on the shelf, not reinvented: the lifecycle is a `workflow` (role
gated, on the pure `statemachine`), storage is a `repository`, intake policy is a `validator`, and
the promotion gate reads a `test-evidence` ledger. One core, two lives: a world-maintenance log in
the game (`parts/maintenance`) and a dependency/CVE patch tracker in a practical app
(`parts/patch_tracker`).

Provenance: original composition of CodeForge Hardware Store parts. No code copied.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from parts.repository import InMemoryRepository
from parts.test_evidence import PASSED, EvidenceLedger
from parts.validation import Data, Validator, one_of, required
from parts.workflow import ANY_ROLE, Instance, Step, WorkflowEngine, build_workflow

KINDS = ("dependency", "security", "config", "migration", "version")
SEVERITIES = ("low", "medium", "high", "critical")


def _tests_passed(ctx: Data) -> str | None:
    """Guard: a change may only reach canary once its evidence ledger reports PASSED."""
    change = ctx.get("change")
    if not isinstance(change, Change):
        return "no change in context"
    if not change.evidence.passed():
        return "tests have not passed; cannot promote to canary"
    return None


_LIFECYCLE = build_workflow(
    "change_lifecycle",
    start="identified",
    steps=[
        Step("identified", "triage", "triaged"),
        Step("triaged", "approve", "approved", roles=frozenset({"approver"})),
        Step("triaged", "reject", "rejected", roles=frozenset({"approver"})),
        Step("approved", "build", "building"),
        Step("building", "test", "testing"),
        Step("testing", "canary", "canary", guard="tests_passed"),
        Step("testing", "fail", "rolled_back"),
        Step("canary", "deploy", "deployed", roles=frozenset({"operator"})),
        Step("canary", "rollback", "rolled_back", roles=frozenset({"operator"})),
        Step("deployed", "verify", "verified", roles=frozenset({"operator"})),
        Step("deployed", "rollback", "rolled_back", roles=frozenset({"operator"})),
        Step("verified", "close", "closed"),
        Step("rolled_back", "close", "closed"),
    ],
    terminal=["closed", "rejected"],
    labels={
        "identified": "identified",
        "triaged": "triaged",
        "approved": "approved",
        "building": "building",
        "testing": "testing",
        "canary": "in canary",
        "deployed": "deployed",
        "verified": "verified",
        "closed": "closed",
        "rejected": "rejected",
        "rolled_back": "rolled back",
    },
)
_ENGINE = WorkflowEngine(_LIFECYCLE, guards={"tests_passed": _tests_passed})

_INTAKE = Validator(
    required("change_id"),
    required("title"),
    one_of("kind", KINDS),
    one_of("severity", SEVERITIES),
)


@dataclass
class Change:
    """One recorded change/patch: its facts, its lifecycle run, and its test evidence."""

    change_id: str
    title: str
    kind: str
    severity: str
    created_by: str
    cve_refs: tuple[str, ...] = ()
    components: tuple[str, ...] = ()
    rollback_plan: str = ""
    run: Instance = field(default=None)  # type: ignore[assignment]
    evidence: EvidenceLedger = field(default=None)  # type: ignore[assignment]

    @property
    def status(self) -> str:
        return self.run.state


class ChangeLedger:
    """Record changes and gate each through the lifecycle. Composes five Hardware Store parts."""

    def __init__(self) -> None:
        self._repo: InMemoryRepository[Change, str] = InMemoryRepository(lambda c: c.change_id)

    def open(
        self,
        change_id: str,
        title: str,
        kind: str,
        severity: str,
        created_by: str,
        *,
        cve_refs: tuple[str, ...] = (),
        components: tuple[str, ...] = (),
        rollback_plan: str = "",
    ) -> Change:
        """Record a new change. Fails loud on invalid facts (intake policy) or a duplicate id."""
        _INTAKE.check(
            {"change_id": change_id, "title": title, "kind": kind, "severity": severity}
        ).raise_if_invalid()
        change = Change(
            change_id,
            title,
            kind,
            severity,
            created_by,
            cve_refs=cve_refs,
            components=components,
            rollback_plan=rollback_plan,
            run=_ENGINE.open(),
            evidence=EvidenceLedger(commit=change_id),
        )
        self._repo.add(change)  # DuplicateKey (a RepositoryError) if the id already exists
        return change

    def record_test(self, change_id: str, check: str, status: str = PASSED) -> None:
        """Attach a test result to a change (the evidence its promotion gate reads)."""
        self._repo.require(change_id).evidence.record(check, status)

    def advance(self, change_id: str, event: str, actor: str = ANY_ROLE):
        """Move a change one legal step. Role-gated, and canary is gated on passing evidence."""
        change = self._repo.require(change_id)
        return _ENGINE.advance(change.run, event, actor=actor, ctx={"change": change})

    def get(self, change_id: str) -> Change | None:
        return self._repo.get(change_id)

    def status(self, change_id: str) -> str:
        return self._repo.require(change_id).status

    def history(self, change_id: str) -> list[dict[str, str]]:
        return self._repo.require(change_id).run.history

    def all(self) -> list[Change]:
        return self._repo.list()
