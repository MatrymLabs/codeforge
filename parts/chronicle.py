"""CARD: chronicle -- the ship's memory: an append-only, content-hashed record store, read back.

The tick (`handle_command`) is the engine of *now*: it computes and renders the present moment,
then discards it. The Chronicle is its symmetric twin, the engine of *memory*: one small,
retained, append-only, hash-chained ledger the ship reads back to answer "how did we get here,
is it getting better, and can we prove it?"

One core mechanism (a content-addressed, hash-chained JSONL ledger) with typed `Record` kinds.
Slice 1 ships the core plus the `evidence` kind (a retained, cited gate verdict); later approved
slices add `metric` (trend series), `incident` (FRACAS), `ai-eval`, and `edge` (provenance).

Honesty rules, mirrored from `arc_ledger`:
- **Append-only + hash-chained.** Each record carries a content hash over its own fields and the
  prior record's hash, so any edit to a past record breaks the chain and is detected on read.
- **Fail loud.** A malformed record, an unknown kind, or a broken chain raises `ChronicleError`
  on read; a dishonest record is worse than an error. Absence reads as empty, never a false pass.
- **Retained, reproducible.** The store is git-tracked (NOT git-ignored) so evidence is kept, not
  discarded; every record cites the commit it was computed at.

Provenance: original composition of CodeForge parts (arc_ledger, reporting). No code copied. The
content-hash-chain concept is the standard tamper-evident append-only log (hash chain / Merkle).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from parts.shelf import hashchain

# The record kinds the Chronicle understands. Slices added, in order: `evidence` (1), `metric`
# (2), `edge` (3), `incident` (4), `ai-eval` (5). A record with any other kind fails loud, so the
# store never accretes junk.
KINDS = ("evidence", "metric", "edge", "incident", "ai-eval")

# The provenance relations an `edge` may assert (PROV-O flavored). A relation outside this set
# fails loud, so the graph stays meaningful rather than a free-for-all of ad-hoc verbs.
RELATIONS = ("wasGeneratedBy", "wasDerivedFrom", "wasInformedBy", "wasAttributedTo")

# FRACAS (Failure Reporting, Analysis, and Corrective Action) vocabulary for `incident` records.
INCIDENT_SEVERITIES = ("low", "medium", "high", "critical")
INCIDENT_STATUSES = ("open", "closed")

CHRONICLE_DIR = "chronicle"  # git-TRACKED (retained), unlike arc-evidence/ which is git-ignored
LEDGER_FILE = "ledger.jsonl"

_GENESIS = ""  # the prior-hash of the first record: no predecessor


class ChronicleError(ValueError):
    """A malformed record, unknown kind, or broken hash chain: fail loud, never a false memory."""


@dataclass(frozen=True)
class Record:
    """One filed memory: a typed payload, the commit it was computed at, and its chain links."""

    kind: str
    payload: dict  # JSON-serializable engineering metadata (no secrets/PII)
    commit: str  # the short sha the record was computed at (reproducibility)
    recorded_utc: str  # ISO-8601 stamp
    prior_hash: str  # content_hash of the preceding record ("" for the genesis record)
    content_hash: str  # sha256 over (kind, payload, commit, recorded_utc, prior_hash)


def _digest(kind: str, payload: dict, commit: str, recorded_utc: str, prior_hash: str) -> str:
    """A deterministic sha256 over a record's content, via the ship's one canonical content hash
    (`parts/shelf/hashchain`), so the Chronicle and the general ledger never drift to other hashing.
    The field set and canonicalization are unchanged, so on-disk hashes are byte-for-byte stable."""
    return hashchain.content_hash(
        {
            "kind": kind,
            "payload": payload,
            "commit": commit,
            "recorded_utc": recorded_utc,
            "prior_hash": prior_hash,
        }
    )


def _ledger_path(root: Path | None) -> Path:
    base = root if root is not None else Path(__file__).resolve().parent.parent
    return base / CHRONICLE_DIR / LEDGER_FILE


def _validate_payload(kind: str, payload: object, where: str) -> None:
    """Fail loud if a payload is not the shape its kind requires (checked on append AND on read)."""
    if not isinstance(payload, dict):
        raise ChronicleError(f"{where}: payload must be an object, got {type(payload).__name__}")
    if kind == "metric":
        name = payload.get("name")
        value = payload.get("value")
        if not isinstance(name, str) or not name.strip():
            raise ChronicleError(f"{where}: a metric record needs a non-empty string 'name'")
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ChronicleError(f"{where}: a metric 'value' must be a number, got {value!r}")
    if kind == "edge":
        for field in ("from", "relation", "to"):
            val = payload.get(field)
            if not isinstance(val, str) or not val.strip():
                raise ChronicleError(f"{where}: an edge needs a non-empty string {field!r}")
        if payload["relation"] not in RELATIONS:
            raise ChronicleError(
                f"{where}: unknown edge relation {payload['relation']!r}; expected {RELATIONS}"
            )
    if kind == "incident":
        what = payload.get("what")
        if not isinstance(what, str) or not what.strip():
            raise ChronicleError(f"{where}: an incident needs a non-empty 'what'")
        if payload.get("severity") not in INCIDENT_SEVERITIES:
            raise ChronicleError(
                f"{where}: incident severity must be one of {INCIDENT_SEVERITIES}, "
                f"got {payload.get('severity')!r}"
            )
        if payload.get("status") not in INCIDENT_STATUSES:
            raise ChronicleError(
                f"{where}: incident status must be one of {INCIDENT_STATUSES}, "
                f"got {payload.get('status')!r}"
            )
        if not isinstance(payload.get("corrective_action", ""), str):
            raise ChronicleError(f"{where}: incident 'corrective_action' must be a string")
    if kind == "ai-eval":
        subject = payload.get("subject")
        score = payload.get("score")
        model = payload.get("model")
        if not isinstance(subject, str) or not subject.strip():
            raise ChronicleError(f"{where}: an ai-eval needs a non-empty 'subject'")
        if not isinstance(score, (int, float)) or isinstance(score, bool):
            raise ChronicleError(f"{where}: an ai-eval 'score' must be a number, got {score!r}")
        if not 0.0 <= score <= 1.0:
            raise ChronicleError(f"{where}: an ai-eval 'score' must be in [0.0, 1.0], got {score}")
        if not isinstance(model, str) or not model.strip():
            raise ChronicleError(f"{where}: an ai-eval needs a non-empty 'model'")
        if not isinstance(payload.get("passed"), bool):
            raise ChronicleError(f"{where}: an ai-eval 'passed' must be a bool")


def _parse_line(line: str, where: str) -> Record:
    """Turn one JSONL line into a validated Record, failing loud on anything malformed."""
    try:
        raw = json.loads(line)
    except json.JSONDecodeError as exc:
        raise ChronicleError(f"{where}: unreadable record ({exc})") from exc
    try:
        record = Record(
            kind=raw["kind"],
            payload=raw["payload"],
            commit=raw["commit"],
            recorded_utc=raw["recorded_utc"],
            prior_hash=raw["prior_hash"],
            content_hash=raw["content_hash"],
        )
    except (KeyError, TypeError) as exc:
        raise ChronicleError(f"{where}: malformed record (missing {exc})") from exc
    if record.kind not in KINDS:
        raise ChronicleError(f"{where}: unknown kind {record.kind!r}; expected {KINDS}")
    _validate_payload(record.kind, record.payload, where)
    return record


def read(kind: str | None = None, *, root: Path | None = None) -> list[Record]:
    """Every record in append order (optionally filtered by `kind`), with the chain verified.

    Verifying on read is the point: each record's stored hash must match a recomputation, and each
    record's `prior_hash` must equal the previous record's hash. A tampered or reordered ledger
    fails loud with `ChronicleError` rather than returning a dishonest memory. An absent store
    reads as empty (never an error).
    """
    path = _ledger_path(root)
    if not path.is_file():
        return []
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    records: list[Record] = []
    expected_prior = _GENESIS
    for i, line in enumerate(lines, start=1):
        record = _parse_line(line, f"{LEDGER_FILE} line {i}")
        recomputed = _digest(
            record.kind, record.payload, record.commit, record.recorded_utc, record.prior_hash
        )
        if recomputed != record.content_hash:
            raise ChronicleError(
                f"{LEDGER_FILE} line {i}: content hash mismatch (record was tampered with)"
            )
        if record.prior_hash != expected_prior:
            raise ChronicleError(
                f"{LEDGER_FILE} line {i}: broken chain "
                f"(prior_hash {record.prior_hash[:8] or '<genesis>'} != expected "
                f"{expected_prior[:8] or '<genesis>'})"
            )
        expected_prior = record.content_hash
        records.append(record)
    if kind is None:
        return records
    if kind not in KINDS:
        raise ChronicleError(f"unknown kind {kind!r}; expected {KINDS}")
    return [r for r in records if r.kind == kind]


def read_latest(kind: str, *, root: Path | None = None) -> Record | None:
    """The newest filed record of `kind`, or None if none is filed (then it is simply absent)."""
    matching = read(kind, root=root)
    return matching[-1] if matching else None


def append(
    kind: str,
    payload: dict,
    *,
    commit: str,
    root: Path | None = None,
    stamp: datetime | None = None,
) -> Record:
    """Validate, hash-chain, and append one record to the retained ledger; return it.

    The record's `prior_hash` links to the current tail of the ledger, so the store is a
    tamper-evident chain. Fails loud (`ChronicleError`) on an unknown kind or a payload that is not
    the shape its kind requires, before anything is written.
    """
    if kind not in KINDS:
        raise ChronicleError(f"unknown kind {kind!r}; expected {KINDS}")
    _validate_payload(kind, payload, "append")
    existing = read(None, root=root)  # verifies the chain before we extend it
    prior_hash = existing[-1].content_hash if existing else _GENESIS
    when = stamp if stamp is not None else datetime.now(UTC)
    if when.tzinfo is not None:
        when = when.astimezone(UTC)  # a field named recorded_utc must be the real UTC instant
    recorded_utc = when.strftime("%Y-%m-%dT%H:%M:%SZ")
    safe_commit = commit or "unknown"
    try:
        content_hash = _digest(kind, payload, safe_commit, recorded_utc, prior_hash)
    except (TypeError, ValueError) as exc:
        # The contract is fail-loud with ChronicleError; a non-serializable payload (a set, a
        # mixed-key dict) must not escape as a raw TypeError the chronicle() verb can't catch.
        raise ChronicleError(f"payload for {kind!r} is not JSON-serializable: {exc}") from exc
    record = Record(
        kind=kind,
        payload=payload,
        commit=safe_commit,
        recorded_utc=recorded_utc,
        prior_hash=prior_hash,
        content_hash=content_hash,
    )
    path = _ledger_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(asdict(record), sort_keys=True) + "\n")
    return record


def record_metric(
    name: str,
    value: float,
    *,
    commit: str,
    root: Path | None = None,
    stamp: datetime | None = None,
) -> Record:
    """Append one `metric` point `{name, value}` - a typed convenience over `append`."""
    return append("metric", {"name": name, "value": value}, commit=commit, root=root, stamp=stamp)


def trend(name: str, *, root: Path | None = None) -> list[Record]:
    """Every recorded `metric` point for `name`, oldest first (a trend series)."""
    return [r for r in read("metric", root=root) if r.payload.get("name") == name]


def render_trend(name: str, records: list[Record]) -> str:
    """A read-only view of one metric's series over time, with the net first->last direction."""
    if not records:
        return f"No metric named {name!r} has been recorded yet."
    lines = [f"TREND - {name}  ({len(records)} point(s), oldest first)", ""]
    for r in records:
        lines.append(f"  [{r.recorded_utc}] {r.payload['value']:>12}  @ {r.commit}")
    first, last = records[0].payload["value"], records[-1].payload["value"]
    delta = last - first
    direction = "flat" if delta == 0 else ("up" if delta > 0 else "down")
    lines += [
        "",
        f"  net: {first:g} -> {last:g}  ({direction} {abs(delta):g})",
        "  (direction is not a judgment: whether higher or lower is better depends on the metric,",
        "   and host-relative numbers only compare within the same host.)",
    ]
    return "\n".join(lines)


def record_edge(
    frm: str,
    relation: str,
    to: str,
    *,
    commit: str,
    root: Path | None = None,
    stamp: datetime | None = None,
) -> Record:
    """Append one provenance `edge` (`frm -relation-> to`) - a typed convenience over `append`."""
    return append(
        "edge",
        {"from": frm, "relation": relation, "to": to},
        commit=commit,
        root=root,
        stamp=stamp,
    )


def provenance(node: str, *, root: Path | None = None) -> list[Record]:
    """Every `edge` touching `node` (as either endpoint), in record order."""
    return [
        r for r in read("edge", root=root) if node in (r.payload.get("from"), r.payload.get("to"))
    ]


def render_provenance(node: str, edges: list[Record]) -> str:
    """A read-only view of the provenance around `node`: its outgoing and incoming edges."""
    if not edges:
        return f"No provenance recorded for {node!r}."
    outgoing = [e for e in edges if e.payload["from"] == node]
    # A self-loop (from == to == node) is already shown as outgoing; excluding it from incoming
    # keeps the line count matching the header's edge count instead of printing it twice.
    incoming = [e for e in edges if e.payload["to"] == node and e.payload["from"] != node]
    lines = [f"PROVENANCE - {node}  ({len(edges)} edge(s))", ""]
    for e in outgoing:
        lines.append(f"  {node} -{e.payload['relation']}-> {e.payload['to']}  @ {e.commit}")
    for e in incoming:
        lines.append(f"  {e.payload['from']} -{e.payload['relation']}-> {node}  @ {e.commit}")
    return "\n".join(lines)


def record_incident(
    what: str,
    severity: str,
    *,
    corrective_action: str = "",
    status: str = "open",
    commit: str,
    root: Path | None = None,
    stamp: datetime | None = None,
) -> Record:
    """Append one FRACAS `incident` record - a typed convenience over `append`."""
    return append(
        "incident",
        {
            "what": what,
            "severity": severity,
            "corrective_action": corrective_action,
            "status": status,
        },
        commit=commit,
        root=root,
        stamp=stamp,
    )


def incidents(status: str | None = None, *, root: Path | None = None) -> list[Record]:
    """Every `incident` record, optionally filtered by status (`open` | `closed`)."""
    recs = read("incident", root=root)
    return [r for r in recs if status is None or r.payload.get("status") == status]


def render_incidents(records: list[Record]) -> str:
    """A read-only FRACAS view: open first, then most severe first."""
    if not records:
        return "No incidents recorded."
    status_rank = {"open": 0, "closed": 1}
    sev_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    ordered = sorted(
        records,
        key=lambda r: (
            status_rank.get(r.payload["status"], 9),
            sev_rank.get(r.payload["severity"], 9),
        ),
    )
    lines = ["INCIDENTS (FRACAS) - open first, most severe first", ""]
    for r in ordered:
        p = r.payload
        lines.append(f"  [{p['status']:<6}] {p['severity']:>8}  {p['what']}  @ {r.commit}")
        lines.append(f"      corrective action: {p.get('corrective_action') or '(none yet)'}")
    return "\n".join(lines)


def record_ai_eval(
    subject: str,
    score: float,
    *,
    model: str,
    passed: bool,
    commit: str,
    root: Path | None = None,
    stamp: datetime | None = None,
) -> Record:
    """Append one scored AI/Advisor evaluation - a typed convenience over `append`."""
    return append(
        "ai-eval",
        {"subject": subject, "score": score, "model": model, "passed": passed},
        commit=commit,
        root=root,
        stamp=stamp,
    )


def ai_evals(subject: str | None = None, *, root: Path | None = None) -> list[Record]:
    """Every `ai-eval` record, optionally for one subject, in append order (oldest first)."""
    recs = read("ai-eval", root=root)
    return [r for r in recs if subject is None or r.payload.get("subject") == subject]


def render_ai_evals(records: list[Record]) -> str:
    """A read-only MLOps view: the latest score per subject, flagging a drop below the prior one."""
    if not records:
        return "No AI evaluations recorded."
    by_subject: dict[str, list[Record]] = {}
    for r in records:  # append order, so the last per subject is the latest
        by_subject.setdefault(r.payload["subject"], []).append(r)
    lines = ["AI EVALUATIONS - latest per subject (regression = below the prior score)", ""]
    for subject, series in sorted(by_subject.items()):
        latest = series[-1]
        verdict = "pass" if latest.payload["passed"] else "FAIL"
        flag = ""
        if len(series) > 1 and latest.payload["score"] < series[-2].payload["score"]:
            flag = f"  REGRESSION (was {series[-2].payload['score']:g})"
        lines.append(
            f"  {subject}: {latest.payload['score']:g} [{verdict}] via "
            f"{latest.payload['model']} @ {latest.commit}{flag}"
        )
    return "\n".join(lines)


def render(records: list[Record]) -> str:
    """A read-only human view of the memory (newest first), for the `chronicle` verb."""
    if not records:
        return "The Chronicle is empty; no memory has been filed yet."
    lines = ["THE CHRONICLE - the ship's memory (newest first)", ""]
    for r in reversed(records):
        summary = ", ".join(f"{k}={v}" for k, v in r.payload.items())
        lines.append(f"  [{r.recorded_utc}] {r.kind} @ {r.commit}  ({summary})")
        lines.append(
            f"      hash {r.content_hash[:12]}  <- prior {r.prior_hash[:12] or '<genesis>'}"
        )
    return "\n".join(lines)


def chronicle(arg: str = "") -> str:
    """The read-only `chronicle` verb: show the ship's filed memory.

    - `chronicle`                 all records, newest first
    - `chronicle <kind>`          just one kind (evidence | metric | edge | incident)
    - `chronicle trend <m>`       the series for metric `<m>` over time
    - `chronicle provenance <n>`  the provenance edges around node `<n>`
    - `chronicle incidents`       the FRACAS register (open first, most severe first)
    - `chronicle evals`           the AI-evaluation memory (latest score per subject)

    Reads only. A tampered or broken ledger surfaces its integrity failure honestly rather than
    crashing the tick (text is a projection; it never mutates the store).
    """
    tokens = arg.split()
    try:
        if tokens and tokens[0].lower() == "trend":
            name = tokens[1] if len(tokens) > 1 else ""
            if not name:
                return "usage: chronicle trend <metric-name>"
            return render_trend(name, trend(name))
        if tokens and tokens[0].lower() == "provenance":
            node = tokens[1] if len(tokens) > 1 else ""
            if not node:
                return "usage: chronicle provenance <node>"
            return render_provenance(node, provenance(node))
        if tokens and tokens[0].lower() == "incidents":
            return render_incidents(incidents())
        if tokens and tokens[0].lower() == "evals":
            return render_ai_evals(ai_evals())
        kind = arg.strip().lower() or None
        if kind is not None and kind not in KINDS:
            return f"Unknown record kind {kind!r}; the Chronicle knows: {', '.join(KINDS)}."
        return render(read(kind))
    except ChronicleError as exc:
        return f"The Chronicle failed its integrity check: {exc}"


def main(argv: list[str] | None = None) -> int:
    """CLI: `python -m parts.chronicle trend <name>` (render) or `record-metric <name> <value>
    <commit>` (append a point). Used by `make trend`; recording is a deliberate, evidenced act."""
    import sys

    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) >= 2 and args[0] == "trend":
        print(render_trend(args[1], trend(args[1])))
        return 0
    if len(args) >= 2 and args[0] == "provenance":
        print(render_provenance(args[1], provenance(args[1])))
        return 0
    if len(args) >= 4 and args[0] == "record-metric":
        rec = record_metric(args[1], float(args[2]), commit=args[3])
        print(f"  recorded {rec.payload['name']}={rec.payload['value']} @ {rec.commit} (chronicle)")
        return 0
    if len(args) >= 5 and args[0] == "record-edge":
        edge = record_edge(args[1], args[2], args[3], commit=args[4])
        p = edge.payload
        print(f"  recorded {p['from']} -{p['relation']}-> {p['to']} @ {edge.commit} (chronicle)")
        return 0
    if args and args[0] == "incidents":
        print(render_incidents(incidents()))
        return 0
    if args and args[0] == "evals":
        print(render_ai_evals(ai_evals()))
        return 0
    if (
        len(args) >= 4 and args[0] == "record-incident"
    ):  # record-incident <severity> <commit> <what...>
        inc = record_incident(" ".join(args[3:]), args[1], commit=args[2])
        print(f"  recorded incident [{inc.payload['severity']}] {inc.payload['what']} (chronicle)")
        return 0
    print(
        "usage: python -m parts.chronicle {trend <name> | provenance <node> | incidents | "
        "evals | record-metric <name> <value> <commit> | "
        "record-edge <from> <relation> <to> <commit> | "
        "record-incident <severity> <commit> <what...>}"
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
