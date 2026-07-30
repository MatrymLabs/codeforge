"""CARD: generation_contract -- the generator's contract as data, and the checks that enforce it.

The source seed's GENERATION_CONTRACT says what every procedurally generated area must carry (the
required fields), which historical layers it may speak to, how a batch of minor areas should be
distributed across archetypes, the beats a dungeon should move through, and the hard lines no
generator may cross. This loads that contract (seeds/aethryn/generation_contract.yaml), validates
its shape, and exposes the checks: `missing_fields(area)` measures one area against the required
set, and `distribution_gaps(areas)` measures a batch against the recommended archetype mix.

It is the ruler the cave forge is held to: an area that answers `missing_fields` with anything is
incomplete, and a batch whose archetypes drift far from the target is flagged. The contract is
data, so the requirement can change without touching the checker.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from parts.world import canon
from parts.world.seed import SeedError, _UniqueKeyLoader

_CONTRACT_PATH = canon.AETHRYN_DIR / "generation_contract.yaml"

# A batch's observed archetype share may sit this far from the target before it is flagged (the seed
# calls the mix a recommendation, not a hard rule).
_DEFAULT_TOLERANCE = 0.15


def load_contract(path: Path | None = None) -> dict[str, Any]:
    """Read and VALIDATE the generation contract. Fails loud (SeedError) if a section is missing or
    the archetype shares do not sum to 1, so a broken contract never silently under-checks."""
    where = path if path is not None else _CONTRACT_PATH
    if not where.exists():
        raise SeedError(f"Generation contract file not found: {where}")
    data = yaml.load(where.read_text(encoding="utf-8"), Loader=_UniqueKeyLoader)
    if not isinstance(data, dict):
        raise SeedError(f"Generation contract file is not a mapping: {where}")

    for section in (
        "required_area_fields",
        "historical_layers",
        "dungeon_grammar",
        "forbidden_changes",
        "minor_area_archetypes",
    ):
        if not data.get(section):
            raise SeedError(f"generation contract: missing or empty section {section!r}")

    archetypes = data["minor_area_archetypes"]
    for arch in archetypes:
        if not arch.get("id") or arch.get("share") is None:
            raise SeedError(
                f"generation contract archetype {arch.get('id')!r}: needs an id and share"
            )
    total = sum(a["share"] for a in archetypes)
    if abs(total - 1.0) > 1e-6:
        raise SeedError(f"generation contract: archetype shares must sum to 1.0, got {total}")
    return data


def required_area_fields(contract: dict[str, Any] | None = None) -> list[str]:
    """Every field a generated area must carry."""
    return list((contract or load_contract())["required_area_fields"])


def historical_layers(contract: dict[str, Any] | None = None) -> list[str]:
    """The historical layers an area may speak to (a generator picks one)."""
    return list((contract or load_contract())["historical_layers"])


def dungeon_grammar(contract: dict[str, Any] | None = None) -> list[str]:
    """The ordered beats a substantial dungeon should move through."""
    return list((contract or load_contract())["dungeon_grammar"])


def forbidden_changes(contract: dict[str, Any] | None = None) -> list[str]:
    """The hard lines no generator may cross (they would break C0/C1 canon)."""
    return list((contract or load_contract())["forbidden_changes"])


def archetype_shares(contract: dict[str, Any] | None = None) -> dict[str, float]:
    """The recommended share of each minor-area archetype, keyed by id."""
    return {a["id"]: a["share"] for a in (contract or load_contract())["minor_area_archetypes"]}


def _is_blank(value: Any) -> bool:
    """A field counts as missing when it is absent, None, or an empty string/list/dict, so a
    placeholder cannot pass. A real 0 or False is a value, not a blank (a seed of 0 is valid)."""
    return value is None or value == "" or value == [] or value == {}


def missing_fields(area: dict[str, Any], contract: dict[str, Any] | None = None) -> list[str]:
    """The required fields a generated area lacks (empty == it satisfies the contract). A field
    present but blank counts as missing; a real 0/False does not (a seed of 0 is valid)."""
    return [field for field in required_area_fields(contract) if _is_blank(area.get(field))]


def distribution_gaps(
    areas: list[dict[str, Any]],
    contract: dict[str, Any] | None = None,
    tolerance: float = _DEFAULT_TOLERANCE,
) -> list[str]:
    """Measure a BATCH of minor areas against the recommended archetype mix. Each area is read by
    its `archetype` field; an archetype whose observed share drifts past `tolerance` from target, or
    that names an archetype the contract does not know, is reported. Empty batch == no opinion."""
    if not areas:
        return []
    shares = archetype_shares(contract)
    counts: dict[str, int] = {}
    gaps: list[str] = []
    for area in areas:
        arch = area.get("archetype")
        if arch not in shares:
            gaps.append(f"area {area.get('id')!r}: unknown archetype {arch!r}")
        else:
            counts[arch] = counts.get(arch, 0) + 1
    total = len(areas)
    for arch, target in shares.items():
        observed = counts.get(arch, 0) / total
        if abs(observed - target) > tolerance:
            gaps.append(
                f"archetype {arch!r}: observed {observed:.0%} vs target {target:.0%} "
                f"(off by more than {tolerance:.0%})"
            )
    return gaps


def canon_tier_for(canon_status: str) -> str:
    """Map this repo's canon_status to the seed's C0-C4 tier label (for the area's provenance)."""
    return {
        "CANON_LOCKED": "C1",
        "CANON_WORKING": "C2",
        "AUTHORED_LOCAL": "C3",
        "GENERATED_LOCAL": "C3",
        "RUMOR": "C4",
    }.get(canon_status, "C3")
