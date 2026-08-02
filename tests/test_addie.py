"""Test twin for kernel/addie.py -- the loop refuses to close on an unlooped cycle.

Acceptance (a cycle that ran the whole loop passes) AND refusal (each of the four failure modes the
loop exists to prevent is caught), plus the real seeded ledger. Hostile cases: a major cycle
with a phase skipped, an unknown scale, a subject-less cycle.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kernel.addie import (
    PHASES,
    SCALES,
    AddieError,
    audit_addie,
    gaps,
    read_ledger,
    render_addie,
    render_self_check,
    self_check,
)

_LEDGER = Path(__file__).resolve().parent.parent / "addie_ledger.toml"


def _full(**overrides) -> object:
    """A major self-check with every phase filled; overrides blank a phase to test refusals."""
    fields = dict(
        subject="a subsystem",
        scale="major",
        analyze="the gap",
        design="the smallest solution",
        develop="what was built",
        implement="where it integrated",
        evaluate="the evidence it worked",
        next_cycle="what to analyze next",
    )
    fields.update(overrides)
    return self_check(**fields)


# --- acceptance -----------------------------------------------------------------------


def test_the_five_phases_are_the_addie_cycle():
    assert [name for name, _ in PHASES] == ["analyze", "design", "develop", "implement", "evaluate"]


def test_a_fully_looped_major_cycle_passes():
    assert gaps(_full()) == []


def test_a_minor_cycle_only_needs_a_subject():
    # minor work is checked silently; it must not be forced to file a full loop
    assert gaps(self_check("a tiny edit", scale="minor")) == []


def test_the_seeded_ledger_closes_its_loop():
    audit = audit_addie(_LEDGER)
    assert audit.passed, audit.flagged
    assert "PASS" in render_addie(_LEDGER)


# --- refusal: the four failure modes the loop exists to prevent -----------------------


def test_building_without_understanding_is_refused():
    assert any("built without understanding" in g for g in gaps(_full(analyze="")))


def test_designing_without_evidence_is_refused():
    assert any("designed without evidence" in g for g in gaps(_full(design="")))


def test_implementing_without_integration_is_refused():
    assert any("implemented without integration" in g for g in gaps(_full(implement="")))


def test_declaring_success_without_evaluation_is_refused():
    assert any("declared success without evaluation" in g for g in gaps(_full(evaluate="")))


def test_a_major_cycle_that_leaves_the_loop_open_is_refused():
    assert any("loop left open" in g for g in gaps(_full(next_cycle="")))


# --- refusal: malformed cycles --------------------------------------------------------


def test_an_unknown_scale_is_refused():
    assert any("unknown scale" in g for g in gaps(_full(scale="huge")))
    assert "minor" in SCALES and "major" in SCALES


def test_a_subjectless_cycle_is_refused():
    assert any("no subject" in g for g in gaps(_full(subject="")))


def test_a_missing_ledger_fails_loud():
    with pytest.raises(AddieError):
        read_ledger(Path("/no/such/addie_ledger.toml"))


def test_a_malformed_ledger_fails_loud(tmp_path):
    bad = tmp_path / "addie_ledger.toml"
    bad.write_text("[unclosed table\n", encoding="utf-8")
    with pytest.raises(AddieError):
        read_ledger(bad)


def test_a_non_table_cycle_section_fails_loud(tmp_path):
    bad = tmp_path / "addie_ledger.toml"
    bad.write_text("cycle = 5\n", encoding="utf-8")
    with pytest.raises(AddieError):
        read_ledger(bad)


def test_a_ledger_with_an_unlooped_cycle_reports_fail(tmp_path):
    led = tmp_path / "addie_ledger.toml"
    led.write_text(
        '[cycle.half]\nsubject = "half a loop"\nscale = "major"\nanalyze = "only this"\n',
        encoding="utf-8",
    )
    assert not audit_addie(led).passed
    text = render_addie(led)
    assert "FAIL" in text and "half" in text


def test_main_passes_on_the_seeded_ledger(capsys):
    from kernel import addie

    assert addie.main([]) == 0
    assert "ADDIE loop: PASS" in capsys.readouterr().out


# --- the addie verb, in the world -----------------------------------------------------


def test_the_addie_verb_renders_the_loop():
    from kernel.addie import addie

    assert "ADDIE loop:" in addie("")
    assert "ADDIE loop:" in addie("status")
    assert "Unknown addie action" in addie("wat")


def test_the_addie_verb_is_reachable_through_the_engine_tick():
    # a feature is not wired until handle_command proves it reachable (the CARD convention)
    from forge import handle_command
    from kernel.world.session import Session

    out = handle_command(Session(player_id="matrym", location="courtyard"), "addie")
    assert "ADDIE loop:" in out


# --- the brief self-check renders every phase -----------------------------------------


def test_render_self_check_shows_the_whole_loop():
    text = render_self_check(_full())
    for label in ("Analyze", "Design", "Develop", "Implement", "Evaluate", "Next cycle"):
        assert label in text
