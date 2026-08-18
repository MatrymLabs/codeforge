#!/usr/bin/env python3
"""Print the assembled Aethryn level 1-300 campaign census as JSON."""

from __future__ import annotations

import json
import os

os.environ.setdefault("FORGE_SEED", "aethryn")

from kernel.world.campaign import load_campaign, report  # noqa: E402, RUF100
from kernel.world.quest import all_ids  # noqa: E402, RUF100
from kernel.world.seed import BLUEPRINT_DIR, load_zones  # noqa: E402, RUF100
from kernel.world.world import NPCS, WORLD, _dungeons, _settlements  # noqa: E402, RUF100


def main() -> int:
    zones = [
        dict(zone, label=label)
        for label, zone in load_zones(BLUEPRINT_DIR / "zones.yaml", set(WORLD)).items()
    ]
    contract = load_campaign(BLUEPRINT_DIR / "campaign.yaml")
    if contract is None:  # pragma: no cover - the flagship seed ships the contract
        raise SystemExit("Aethryn campaign.yaml is missing")
    print(
        json.dumps(
            report(contract, zones, _dungeons or [], _settlements or [], NPCS, all_ids()), indent=2
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
