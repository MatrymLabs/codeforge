"""CARD: journey_form -- the last link: bind the Engineering Form to the journey generator, so a
filled Form becomes a playable, durable, recoverable game. This closes Form -> Spec -> Seed.

The pipeline had every stage but its front door. The Form (form.py) walks a data catalog and emits
a validated SeedSpec; `journey` (MOD-10.088) generates a GameSpec from a compact intent; the Linker
links it and game_session operates + recovers it. This adapter joins the two halves:
`journey_from_form(spec)` reads a `journey` SeedSpec's answers and calls `journey_region`.

The Form's scale/persistence question is carried through, not gated: `persistence_tier` records
whether this journey is a `single_session` personal INSTANCE or a `persistent` shared region.
Instancing is a valid mode WITHIN the one integrated MMORPG (founder ruling, revised): the runtime
honours the tier; the generated region content is the same either way.

Grammar before worlds: this lives in kernel/domains/ and may read the neutral platform's SeedSpec
(kernel/domains -> kernel/seedlab is allowed); the platform still imports no domain (import-linter
`grammar-before-worlds`/`platform-imports-no-domain-module`). Status: PROTOTYPED (see
docs/seed_platform/RECENTERING.md).
"""

from __future__ import annotations

from kernel.domains.game_linker import GameSpec
from kernel.domains.journey import journey_region
from kernel.seedlab.form import SeedSpec

_PRODUCT_TYPE = "journey"


class JourneyFormError(Exception):
    """A SeedSpec cannot become a journey (it is not a journey product type). Fails loud. Content
    problems (an empty or bad-label waypoint) surface as JourneyError from the generator."""


def journey_from_form(spec: SeedSpec) -> GameSpec:
    """Turn a validated `journey` SeedSpec (from the Engineering Form) into a GameSpec, ready to
    link and play. Refuses a spec that is not a journey. The region and the ordered, comma-separated
    waypoint labels come from the answers; `journey_region` validates them and fails loud on a bad
    label. The `persistence_tier` answer (single_session = a personal instance
    within the world; persistent = a shared region) rides along in the SeedSpec for the runtime to
    honour -- instancing is a valid mode WITHIN the one MMORPG; the region content is the same."""
    if spec.product_type != _PRODUCT_TYPE:
        raise JourneyFormError(f"not a journey spec: product type is {spec.product_type!r}")
    region = str(spec.answers.get("region", "")).strip()
    waypoints = [w.strip() for w in str(spec.answers.get("waypoints", "")).split(",") if w.strip()]
    return journey_region(region, waypoints)
