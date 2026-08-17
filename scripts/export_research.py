"""Export the R&D Factory's candidate register into a `Research.Findings` manifest.

The Master Client's Research panel reads a MOUNTED `research.json` (`SEEDLAB_RESEARCH`); this
bridges the ship-root R&D Factory (`rd/`) into that shape, so the panel shows the fleet's REAL
research instead of an honestly-empty mount. codeforge reads `rd/` READ-ONLY (the
Federal-Guidance-Library pattern: a sibling mount via `RD_HOME`), never vendoring it. Run this, then
point `SEEDLAB_RESEARCH` at the output.

    python3 scripts/export_research.py                 # rd/ sibling -> $SEEDLAB_HOME/research.json
    RD_HOME=/path/to/rd python3 scripts/export_research.py --out /srv/research.json

The output is a JSON list of finding records the engine's `research_findings` projector emits and
the client's `parse_research_findings` reads; generated (git-ignored), reproducible from `rd/`.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import yaml

#: The R&D Factory's verdict-bearing register (candidate technologies + their status), relative to
#: the mounted rd/ home. Each candidate becomes one research finding.
_REGISTER = Path("04-verdicts") / "CANDIDATE_REGISTER.yaml"

#: How a candidate's fields map onto the finding record shape (finding_key <- candidate_key). A
#: field the candidate lacks is simply absent from the finding (No Vision Theater), never invented.
_FIELD_MAP = (
    ("title", "technology"),
    ("question", "problem_it_may_solve"),
    ("verdict", "status"),
    ("source", "source"),
    ("evidence", "required_experiment"),
    ("summary", "expected_benefit"),
)


def _default_rd_home() -> Path:
    """The mounted R&D Factory: `RD_HOME`, else the ship-root `rd/` sibling of this repo."""
    return Path(os.environ.get("RD_HOME") or Path(__file__).resolve().parents[2] / "rd")


def _default_out() -> Path:
    """Where the manifest is written: `$SEEDLAB_HOME/research.json` (the gateway's mount)."""
    return Path(os.environ.get("SEEDLAB_HOME", ".seedlab")) / "research.json"


def _finding(candidate: Any) -> dict[str, object] | None:
    """One finding record from a candidate, or None when it lacks a `candidate_id` (dropped, not
    trusted). Each mapped field is a collapsed one-line string (the register uses folded scalars);
    an absent field is left out of the finding entirely."""
    if not isinstance(candidate, dict):
        return None
    cid = candidate.get("candidate_id")
    if not isinstance(cid, str) or not cid.strip():
        return None
    finding: dict[str, object] = {"id": cid.strip()}
    for finding_key, candidate_key in _FIELD_MAP:
        value = candidate.get(candidate_key)
        if isinstance(value, str) and value.strip():
            finding[finding_key] = " ".join(value.split())  # collapse the register's folded scalars
    return finding


def export_findings(register: Any) -> list[dict[str, object]]:
    """Map a parsed `CANDIDATE_REGISTER.yaml` into `Research.Findings` records, sorted by id. A
    malformed register (not a mapping with a `candidates` list) fails loud, never a silent empty
    manifest."""
    if not isinstance(register, dict) or not isinstance(register.get("candidates"), list):
        raise ValueError("candidate register must be a mapping with a 'candidates' list") # noqa: TRY004
    findings = [finding for finding in (_finding(c) for c in register["candidates"]) if finding]
    return sorted(findings, key=lambda finding: str(finding["id"]))


def load_register(rd_home: Path) -> Any:
    """Read + parse the candidate register under a mounted `rd/` home (read-only)."""
    return yaml.safe_load((rd_home / _REGISTER).read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Export the R&D candidate register to research.json"
    )
    parser.add_argument("--rd-home", type=Path, default=_default_rd_home())
    parser.add_argument("--out", type=Path, default=_default_out())
    args = parser.parse_args(argv)
    findings = export_findings(load_register(args.rd_home))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(findings, indent=2) + "\n", encoding="utf-8")
    print(f"exported {len(findings)} findings from {args.rd_home} -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
