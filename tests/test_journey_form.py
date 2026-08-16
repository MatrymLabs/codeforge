"""Test twin for kernel/domains/journey_form.py -- the Form -> journey bridge that closes
Form -> Spec -> Seed.

Acceptance (the whole pipeline, front door to playable): a filled Engineering Form for the `journey`
product type builds a validated BlueprintSpec, the bridge turns it into a GameSpec, and that
GameSpec
both LINKS and OPERATES-AND-RESUMES on the real engine -- so a filled Form becomes a playable,
durable, recoverable game. The Form actually offers `journey` (the catalog is wired).

Refusal (fail loud, enforces J3): a single_session (instanced) tier is refused; a non-journey spec
is refused; a bad waypoint surfaces as a JourneyError from the generator.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kernel.domains.game_session import RESUMED, operate_and_recover
from kernel.domains.journey import JourneyError
from kernel.domains.journey_form import JourneyFormError, journey_from_form
from kernel.seedlab.form import EngineeringForm

_COMMON = {"name": "Veridia Road", "owner": "josh", "purpose": "a first journey"}


def _journey_spec(**answers):
    """Build a validated `journey` BlueprintSpec through the real Form (the shipped catalog)."""
    return EngineeringForm.load().build_spec("journey", {**_COMMON, **answers})


# --- acceptance: a filled Form becomes a playable, recoverable game -------------------------------


def test_the_form_offers_a_journey_product_type() -> None:
    ids = {pt.id for pt in EngineeringForm.load().product_types()}
    assert "journey" in ids  # the catalog is wired: the Form can ask for a journey


def test_form_to_playable_journey_end_to_end(tmp_path: Path) -> None:
    spec = _journey_spec(
        persistence_tier="persistent", region="veridia", waypoints="greenhold, riverside, summit"
    )
    game = journey_from_form(spec)
    assert game.region == "veridia" and game.quest is not None
    report = operate_and_recover(
        game, tmp_path
    )  # Form -> Spec -> Seed -> link -> operate -> recover
    assert report.verdict == RESUMED and report.terminal == "arrived"


# --- both persistence tiers are valid (instancing allowed within the MMORPG) ---------------------


@pytest.mark.parametrize("tier", ["single_session", "persistent"])
def test_both_persistence_tiers_generate_a_playable_journey(tier: str, tmp_path: Path) -> None:
    # Instancing is a valid mode within the one MMORPG: single_session (an instance) and persistent
    # (a shared region) both produce a playable, recoverable journey. Tier is carried, not gated.
    spec = _journey_spec(persistence_tier=tier, region="veridia", waypoints="greenhold, summit")
    report = operate_and_recover(journey_from_form(spec), tmp_path)
    assert report.verdict == RESUMED


# --- refusal: fail loud ---------------------------------------------------------------------------


def test_a_non_journey_spec_is_refused() -> None:
    mmorpg = EngineeringForm.load().build_spec(
        "mmorpg",
        {
            **_COMMON,
            "world_scale": "small",
            "combat": False,
            "economy": False,
            "progression": False,
            "moderation": "standard",
        },
    )
    with pytest.raises(JourneyFormError) as err:
        journey_from_form(mmorpg)
    assert "not a journey" in str(err.value)


def test_a_bad_waypoint_surfaces_as_a_journey_error() -> None:
    spec = _journey_spec(persistence_tier="persistent", region="veridia", waypoints="Bad Label")
    with pytest.raises(JourneyError):  # the generator's own gate, not swallowed
        journey_from_form(spec)


def test_a_waypoints_string_with_no_labels_is_refused() -> None:
    # A non-empty string the Form accepts, but it yields no labels -> the generator refuses.
    spec = _journey_spec(persistence_tier="persistent", region="veridia", waypoints=",")
    with pytest.raises(JourneyError):
        journey_from_form(spec)
