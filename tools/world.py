"""The `world` developer CLI: validate the Aethryn world map, and generate areas for it.

A thin front for two parts (all logic + tests live there): kernel/world/survey.py (the read-only
Surveyor) and kernel/world/area_store.py (the mutating area bench). Usage:

    python -m tools.world validate
    python -m tools.world check-canon
    python -m tools.world list-regions
    python -m tools.world list-locations
    python -m tools.world find-broken-references
    python -m tools.world find-unreachable
    python -m tools.world inspect <region-id>
    python -m tools.world graph
    python -m tools.world generate-area <region> [--seed N] [--size N]
    python -m tools.world preview-area <area-id>
    python -m tools.world promote <area-id>
    python -m tools.world export <area-id> <dest-file>
    python -m tools.world list-areas

Exit code is 0 when clean/ok, 1 when the Surveyor found problems or a store op is refused, 2 on a
usage error, so it can gate a script or a Make button.
"""

from __future__ import annotations

import sys

from kernel.world import area_store, survey

# The read-only half routes to the Surveyor; everything else is the area bench.
_READ_ONLY = {
    "validate",
    "check-canon",
    "list-regions",
    "list-locations",
    "find-broken-references",
    "find-unreachable",
    "inspect",
    "graph",
}


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] in _READ_ONLY:
        code, text = survey.run(args)
    else:
        code, text = area_store.run(args)
    print(text)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
