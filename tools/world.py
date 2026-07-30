"""The `world` developer CLI: read-only validation of the Aethryn world map.

A thin front for parts/world/survey.py (all logic + tests live there). Usage:

    python -m tools.world validate
    python -m tools.world check-canon
    python -m tools.world list-regions
    python -m tools.world list-locations
    python -m tools.world find-broken-references

Exit code is 0 when clean, 1 when the Surveyor found problems, 2 on a usage error, so it can gate
a script or a Make button. The mutating half of the tool family lands with the area generator.
"""

from __future__ import annotations

import sys

from parts.world import survey


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    code, text = survey.run(args)
    print(text)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
