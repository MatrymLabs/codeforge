"""Test twin for parts/encounter_flush.py -- the trusted boundary (tallies -> Chronicle metrics).

Every test injects a tmp `root`, so the real (git-tracked) chronicle/ ledger is never touched. Pins:
the flush records one metric per non-zero kind, clears the tallies, no-ops on an empty period, and
the tallies feed the Chronicle's own `trend` machinery.
"""

import inspect
from pathlib import Path

import pytest

from parts import encounter_flush
from parts.chronicle import read, trend
from parts.encounter_flush import flush
from parts.world import encounter_log


@pytest.fixture(autouse=True)
def fresh_log():
    encounter_log.reset()
    yield
    encounter_log.reset()


def test_flush_records_one_metric_per_nonzero_kind(tmp_path: Path):
    encounter_log.witness("open_strike", "the reaver")
    encounter_log.witness("open_strike", "the reaver")
    encounter_log.witness("defeat", "the dummy")
    summary = flush("abc1234", root=tmp_path)
    assert "open_strike=2" in summary and "defeat=1" in summary

    metrics = read("metric", root=tmp_path)
    names = {m.payload["name"]: m.payload["value"] for m in metrics}
    assert names == {"encounters.open_strike": 2, "encounters.defeat": 1}  # only non-zero kinds


def test_flush_clears_the_tallies_but_not_the_ring(tmp_path: Path):
    encounter_log.witness("fall", "the reaver")
    flush("c0ffee", root=tmp_path)
    assert encounter_log.tally()["fall"] == 0  # tallies reset for the next period
    assert encounter_log.recent()  # the live ring still shows the beat


def test_an_empty_period_flushes_nothing(tmp_path: Path):
    summary = flush("deadbee", root=tmp_path)
    assert "nothing flushed" in summary
    assert read("metric", root=tmp_path) == []  # no noise for no encounters


def test_flushed_metrics_feed_the_chronicle_trend(tmp_path: Path):
    encounter_log.witness("defeat", "the dummy")
    flush("c1", root=tmp_path)
    encounter_log.witness("defeat", "the dummy")
    encounter_log.witness("defeat", "the dummy")
    flush("c2", root=tmp_path)
    series = trend("encounters.defeat", root=tmp_path)
    assert [r.payload["value"] for r in series] == [1, 2]  # two periods, a real trend


def test_the_flush_verb_is_owner_gated_and_reaches_the_boundary():
    """The trusted boundary is an OWNER verb run in the server process. A player is refused (the
    tick never flushes); an owner with an empty period reaches the boundary and is told nothing was
    flushed -- proving reachability + gating without writing the real (git-tracked) ledger."""
    from forge import handle_command
    from parts.world.session import SESSIONS, Session

    encounter_log.clear_tally()  # empty period: the owner path writes nothing to the real ledger
    player = Session(player_id="mortal", rank="player")
    SESSIONS["mortal"] = player
    assert "authority" in handle_command(player, "@flush-encounters").lower()

    owner = Session(player_id="root", rank="owner")
    SESSIONS["root"] = owner
    assert "nothing flushed" in handle_command(owner, "@flush-encounters")
    SESSIONS.clear()


def test_the_flush_is_the_only_bridge_encounter_log_stays_pure():
    """encounter_flush is where encounter_log and chronicle meet; encounter_log itself must still
    import nothing from chronicle (the tick's write path stays away from the trusted ledger)."""
    log_imports = [
        line
        for line in inspect.getsource(encounter_log).splitlines()
        if line.strip().startswith(("import ", "from "))
    ]
    assert not any("chronicle" in line.lower() for line in log_imports)
    # the boundary module, by contrast, is allowed to import both
    flush_src = inspect.getsource(encounter_flush)
    assert "chronicle" in flush_src and "encounter_log" in flush_src
