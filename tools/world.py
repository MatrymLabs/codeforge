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

from kernel.world import aethryn_cli, area_store, survey

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

_AETHRYN_COMMANDS = {
    "explain",
    "validate-packet",
    "compile-packet",
    "materialize",
    "diff",
    "hotfix",
    "cache-inspect",
    "provenance",
    "find-orphans",
    "economy-check",
    "item-check",
    "weapon-check",
    "armor-check",
    "crafting-check",
    "merchant-check",
    "loot-check",
    "inspect-item",
    "inspect-material",
    "inspect-recipe",
    "inspect-merchant-stock",
    "item-lineage",
    "item-provenance",
    "recipe-tree",
    "merchant-preview",
    "loot-preview",
    "simulate-crafting",
    "simulate-stock",
    "find-unobtainable-items",
    "find-unproducible-items",
    "find-orphaned-recipes",
    "find-broken-sets",
    "find-balance-outliers",
    "find-economic-loops",
    "find-duplicate-uniques",
    "ecology-check",
    "bestiary-check",
    "population-check",
    "inspect-creature",
    "inspect-population",
    "population-map",
    "encounter-preview",
    "simulate-population",
    "find-overpopulated",
    "find-empty-zones",
    "find-habitat-conflicts",
    "find-orphaned-creatures",
    "quest-check",
    "quest-reference-check",
    "quest-graph-check",
    "quest-reward-check",
    "quest-consequence-check",
    "inspect-quest",
    "inspect-pressure",
    "inspect-arc",
    "quest-graph",
    "quest-lineage",
    "quest-provenance",
    "simulate-quest",
    "simulate-public-event",
    "preview-contract",
    "find-broken-quests",
    "find-unreachable-quest-states",
    "find-unobtainable-objectives",
    "find-missing-quest-references",
    "find-duplicate-rewards",
    "find-quest-economic-loops",
    "find-canon-leaking-quests",
    "find-quests-without-consequences",
    "find-overused-quest-targets",
    "canon-check",
    "map-concordance-check",
    "full-world-check",
}


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] in _READ_ONLY:
        code, text = survey.run(args)
    elif args and args[0] in _AETHRYN_COMMANDS:
        code, text = aethryn_cli.run(args)
    else:
        code, text = area_store.run(args)
    print(text)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
