"""Runtime projections for compiled Aethryn schedules, flows, and pressures."""

from __future__ import annotations

from pathlib import Path

from kernel.world.aethryn_runtime import load_catalog, project_runtime_context

ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "content" / "seeds" / "aethryn" / "generated"


def test_compiled_catalog_projects_brightwater_runtime_signals_deterministically() -> None:
    catalog = load_catalog(GENERATED)
    assert catalog is not None

    market = project_runtime_context("brightwater_market", 0, catalog)
    millrace = project_runtime_context("brightwater_millrace", 0, catalog)
    lower_weirs = project_runtime_context("brightwater_lowerweir", 0, catalog)

    assert "routine: Chandler Merrow is on dawn stock check." in market
    assert "trade: meadowfoil" in market.lower()
    assert "draughts_and_rations" in market.lower()
    assert "trade: meadowfoil" in millrace.lower()
    assert "ecology: wyrm and lower-weir pressure" in lower_weirs.lower()
    assert "pressure: lower-weir danger: a river-wyrm" in lower_weirs.lower()
    assert project_runtime_context("brightwater_market", 0, catalog) == market


def test_schedule_projection_changes_only_with_the_world_beat() -> None:
    catalog = load_catalog(GENERATED)
    assert catalog is not None

    first = project_runtime_context("brightwater_market", 0, catalog)
    second = project_runtime_context("brightwater_market", 1, catalog)

    assert "dawn stock check" in first
    assert "market trade" in second
    assert first != second


def test_state_gated_pressure_disappears_after_cistern_repair() -> None:
    catalog = load_catalog(GENERATED)
    assert catalog is not None

    flowing = project_runtime_context(
        "veridia_living_cistern_court",
        0,
        catalog,
        {"greenhold.cistern_status": "flowing"},
    )

    assert "water shortage" not in flowing.lower()


def test_non_aethryn_runtime_context_is_empty() -> None:
    assert project_runtime_context("brightwater_market", 0, None) == ""


def test_live_room_renderer_includes_compiled_runtime_signals(monkeypatch) -> None:
    from kernel.world import world

    catalog = load_catalog(GENERATED)
    assert catalog is not None
    monkeypatch.setitem(
        world.WORLD,
        "brightwater_market",
        {"name": "The Weir Market", "desc": "A working river market.", "exits": {}},
    )
    monkeypatch.setattr(world, "_AETHRYN_RUNTIME", catalog)

    rendered = world.render_room("brightwater_market")

    assert "WORLD SIGNALS" in rendered
    assert "Chandler Merrow is on dawn stock check" in rendered
    assert "meadowfoil" in rendered
