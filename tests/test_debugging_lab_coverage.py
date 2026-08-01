"""Edge-branch coverage for the Debugging Lab shelf parts.

The three rung twins pin behavior; this exercises the remaining honesty/edge branches
(the ddmin call cap and inconsistent-oracle path, the SBFL undefined-denominator and
no-failure cases, the profile zero-time note and empty render) so every path runs.
"""

from __future__ import annotations

from parts.shelf import ddmin, profile_hotspots, sbfl


def test_ddmin_degenerate_oracle_is_reported_not_1_minimal() -> None:
    # a degenerate oracle that "fails" for EVERY subset (even the empty one): ddmin shrinks
    # to a single element, but removing it still "fails", so 1-minimality cannot hold and is
    # reported honestly rather than claimed.
    reduction = ddmin.ddmin([1, 2, 3], lambda subset: True)
    assert not reduction.is_one_minimal
    assert any("not 1-minimal" in n for n in reduction.notes)


def test_ddmin_max_calls_cap_mid_run() -> None:
    reduction = ddmin.ddmin(list(range(200)), lambda s: 99 in s, max_calls=4)
    assert not reduction.is_one_minimal
    assert any("max_calls" in n for n in reduction.notes)
    assert "NOT verified 1-minimal" in ddmin.render(reduction)


def test_ddmin_cap_hit_inside_the_chunk_loop() -> None:
    # max_calls=2 forces the cap to trip mid phase-1 (after the full check + one chunk),
    # when no single chunk reproduces (the failure needs two elements)
    reduction = ddmin.ddmin(list(range(20)), lambda s: 5 in s and 15 in s, max_calls=2)
    assert not reduction.is_one_minimal
    assert any("max_calls" in n for n in reduction.notes)


def test_ddmin_split_skips_empty_chunks() -> None:
    # a 3-element input at high granularity yields some empty chunk slots that are skipped
    reduction = ddmin.ddmin([1, 2, 3], lambda s: 2 in s)
    assert list(reduction.minimal) == [2]


def test_ddmin_render_note_line() -> None:
    out = ddmin.render(ddmin.ddmin(list(range(50)), lambda s: 7 in s, max_calls=3))
    assert "note:" in out


def test_sbfl_dstar_undefined_denominator() -> None:
    # one failing test covers "x", no passing tests -> for x: ef=1, ep=0, nf=0 -> denom 0
    report = sbfl.localize({"t1": {"x"}}, {"t1": False}, formula="dstar")
    assert report.ranking[0].element == "x"
    assert report.ranking[0].score > 0  # falls back to the raw numerator, not a crash


def test_sbfl_tarantula_with_no_failures() -> None:
    report = sbfl.localize({"t1": {"a"}}, {"t1": True}, formula="tarantula")
    assert report.total_failed == 0
    assert report.prime_suspects == ()  # nothing suspicious without a failure


def test_profile_empty_stats_renders_no_functions() -> None:
    report = profile_hotspots.analyze({})
    out = profile_hotspots.render(report)
    assert "no functions recorded" in out
    assert "note:" in out  # the zero-time note line


def test_profile_render_note_line_on_zero_time() -> None:
    report = profile_hotspots.analyze({("f.py", 1, "g"): (1, 1, 0.0, 0.0, {})})
    assert any("too fast" in n for n in report.notes)
    assert "note:" in profile_hotspots.render(report)
