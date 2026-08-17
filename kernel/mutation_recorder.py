"""CARD: mutation_recorder -- persist one `make mutation` run so posture can read it as a KPI.

The AP-09 follow-up (RD-2026-0003). The shelf part `kernel/shelf/mutation_kpi.py` is the pure,
tool-agnostic core: it turns a MutationResult into a MEASURED / NOT_COMPUTABLE KPI and parses
cosmic-ray's text output. It deliberately touches no disk. This is the codeforge-specific I/O
seam around it: the recorder that `make mutation` pipes its cr-report into, and the loader
`kernel/posture.py` reads so the mutation-kill-rate KPI flips from NOT_COMPUTABLE to MEASURED.

Why a separate module, not more of the shelf part: the shelf part is mirrored to codeforge-shelf
as a reusable Hardware Store part; keeping its surface pure (no filesystem, no repo paths) lets it
travel. The disk format, the repo-anchored default path, and the `python -m` CLI are codeforge
integration, so they live in kernel/. Clean-room, stdlib only (json, datetime, pathlib).

Evidence file (a single JSON object, the LAST run wins - mutation is on-demand, never a CI gate):

    {"total": 179, "killed": 122, "survived": 57, "incomplete": 0, "run_date": "2026-08-02"}
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

from kernel.shelf.mutation_kpi import MutationKpiError, MutationResult, parse_cr_report

# Repo-anchored so the file lands beside the pip-audit store posture already reads, no matter the
# caller's cwd (the same trap kernel/world/db.py closed). parents[1] of kernel/mutation_recorder.py
# is the repo root.
DEFAULT_EVIDENCE_PATH = (
    Path(__file__).resolve().parents[1] / "security-evidence" / "mutation-latest.json"
)


class MutationEvidenceError(ValueError):
    """Raised when a recorded mutation file exists but cannot be parsed - never load a bad value."""


def to_json(result: MutationResult) -> str:
    """Serialize one run to the on-disk JSON object (run_date as ISO text)."""
    return json.dumps(
        {
            "total": result.total,
            "killed": result.killed,
            "survived": result.survived,
            "incomplete": result.incomplete,
            "run_date": result.run_date.isoformat(),
        }
    )


def record(result: MutationResult, path: Path | str = DEFAULT_EVIDENCE_PATH) -> Path:
    """Write one run to `path` (last run wins), creating parent dirs. Returns the path written."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(to_json(result) + "\n", "utf-8")
    return p


def record_cr_report(
    text: str, run_date: date, path: Path | str = DEFAULT_EVIDENCE_PATH
) -> MutationResult:
    """Parse a cosmic-ray `cr-report` and record it. Loud on a malformed report (the adapter)."""
    result = parse_cr_report(text, run_date)
    record(result, path)
    return result


def load(path: Path | str = DEFAULT_EVIDENCE_PATH) -> MutationResult | None:
    """Read the recorded run, or None if none exists yet (an absent file is honest, not an error).

    A present-but-corrupt file fails LOUD (MutationEvidenceError) - the same rule posture uses for a
    malformed scan: a bad number must never be laundered into a green KPI."""
    p = Path(path)
    if not p.exists():
        return None
    raw = p.read_text("utf-8").strip()
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return MutationResult(
            total=int(data["total"]),
            killed=int(data["killed"]),
            survived=int(data["survived"]),
            incomplete=int(data.get("incomplete", 0)),
            run_date=date.fromisoformat(data["run_date"]),
        )
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise MutationEvidenceError(f"cannot read mutation evidence {p}: {exc}") from exc  # noqa: TRY003


def _main(argv: list[str]) -> int:
    """`... cr-report session.sqlite | python -m kernel.mutation_recorder [path]` - record stdin.

    Reads a cr-report from stdin, stamps today's date, and writes the evidence file. The date is
    real wall-clock here (a genuine run happens now); tests inject dates through record()/load()."""
    path = argv[1] if len(argv) > 1 else DEFAULT_EVIDENCE_PATH
    text = sys.stdin.read()
    try:
        result = record_cr_report(text, date.today(), path)  # noqa: DTZ011
    except MutationKpiError as exc:
        print(f"mutation-recorder: refused a malformed cr-report: {exc}", file=sys.stderr)
        return 1
    print(
        f"mutation-recorder: recorded {result.killed}/{result.killed + result.survived} "
        f"killed ({result.kill_rate:.0%}) -> {path}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - thin CLI wrapper over tested functions
    raise SystemExit(_main(sys.argv))
