"""Test twin for parts/hardware.py -- the cross-domain reusable-parts catalog.

Acceptance: the shipped catalog loads and every part maps to a domain.
Refusal: a malformed entry fails loud rather than stocking a bad part."""

import pytest

from parts.hardware import CatalogError, catalog_text, find_part, load_catalog, source_gaps


def _write(tmp_path, text: str):
    path = tmp_path / "parts.yaml"
    path.write_text(text)
    return path


def test_shipped_catalog_loads_and_every_part_maps_to_a_domain():
    parts = load_catalog()  # the real catalog/parts.yaml
    assert parts, "the shipped catalog should stock at least one part"
    assert all(part.reuse for part in parts)  # each part reuses in >=1 domain
    assert all(part.source for part in parts)  # each names its source file


def test_reuse_score_is_derived_not_authored():
    # reuse_score is DERIVED (count of reuse domains), never a hand-entered, ungated claim.
    parts = load_catalog()
    assert all(part.reuse_score == len(part.reuse) for part in parts)


def test_every_shipped_part_is_free_to_use_and_records_its_pattern():
    # the Free-to-Use rule, enforced: clear provenance + the pattern it was rebuilt from
    parts = load_catalog()
    assert all(part.source_status == "original" for part in parts)
    assert all(part.license for part in parts)
    assert all(part.influence for part in parts), "each part should record its known pattern"


def test_every_shipped_part_shows_its_road_not_taken():
    # the road-not-taken section: the deliberate alternative (a framework, or the frameless path)
    parts = load_catalog()
    assert all(part.experimental for part in parts), "each part should note its road not taken"
    text = catalog_text()
    assert "road not taken" in text


def test_experimental_is_optional_and_omitted_when_absent(tmp_path):
    # a part without an experimental note loads fine and prints no experimental line
    catalog = _write(
        tmp_path,
        "- id: x\n  name: X\n  source: parts/x.py\n  category: c\n  purpose: p\n"
        "  maturity: beta\n  risk: low\n  reuse: {game: y}\n",
    )
    part = load_catalog(catalog)[0]
    assert part.experimental == ""
    assert "road not taken" not in catalog_text(catalog)


def test_a_non_free_to_use_source_status_is_refused(tmp_path):
    path = _write(
        tmp_path,
        "- id: x\n  name: X\n  source: parts/x.py\n  category: c\n  maturity: beta\n"
        "  risk: low\n  source_status: gpl-3.0\n  reuse: {game: y}\n  purpose: z\n",
    )
    with pytest.raises(CatalogError, match="free-to-use status"):
        load_catalog(path)


def test_find_part_by_id():
    parts = load_catalog()
    first = parts[0]
    assert find_part(first.id) == first
    assert find_part("no-such-part") is None


def test_render_shows_the_domains(tmp_path):
    catalog = _write(
        tmp_path,
        """
- id: demo-part
  name: Demo Part
  source: parts/demo.py
  category: example
  purpose: A demonstration part.
  maturity: beta
  risk: low
  reuse:
    game: an in-world thing
    finance: an accounts-payable thing
""",
    )
    text = catalog_text(catalog)
    assert "Demo Part" in text
    assert "finance" in text and "accounts-payable thing" in text


def test_missing_required_field_fails_loud(tmp_path):
    catalog = _write(tmp_path, "- id: broken\n  name: Broken\n")  # missing most fields
    with pytest.raises(CatalogError):
        load_catalog(catalog)


def test_unknown_maturity_fails_loud(tmp_path):
    catalog = _write(
        tmp_path,
        """
- id: x
  name: X
  source: s
  category: c
  purpose: p
  maturity: legendary
  risk: low
  reuse: {game: y}
""",
    )
    with pytest.raises(CatalogError):
        load_catalog(catalog)


def test_missing_catalog_is_empty_not_an_error(tmp_path):
    assert load_catalog(tmp_path / "nope.yaml") == []


# --- EXP-001: parse-once mtime-guarded cache (correctness + invalidation) --------
def _one_part(pid: str, name: str = "X") -> str:
    return (
        f"- {{id: {pid}, name: {name}, source: s.py, category: c, purpose: p, "
        f"maturity: shipped, risk: low, reuse: {{game: g}}}}\n"
    )


def test_the_catalog_is_parsed_once_and_cached(tmp_path):
    # conftest clears the shared loader cache before each test, so this starts cold.
    path = _write(tmp_path, _one_part("alpha"))
    first = load_catalog(path)
    second = load_catalog(path)
    assert first is second  # same object on an unchanged file -> not re-parsed


def test_cached_result_equals_a_fresh_parse(tmp_path):
    from parts import loader_cache

    path = _write(tmp_path, _one_part("alpha"))
    cached = load_catalog(path)
    loader_cache.clear()  # force a genuinely fresh parse
    fresh = load_catalog(path)
    assert cached == fresh  # Part is a frozen dataclass; equality is by value


def test_an_on_disk_edit_invalidates_the_cache(tmp_path):
    import os

    path = _write(tmp_path, _one_part("alpha"))
    assert load_catalog(path)[0].id == "alpha"
    _write(tmp_path, _one_part("beta"))  # rewrite with different content
    st = os.stat(path)
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000_000))  # guarantee a new mtime
    assert load_catalog(path)[0].id == "beta"  # sees the edit, never the stale cache


def test_a_bad_edit_never_poisons_the_cache(tmp_path):
    path = _write(tmp_path, _one_part("alpha"))
    assert load_catalog(path)[0].id == "alpha"
    _write(tmp_path, "- {id: bad}\n")  # missing required fields
    import os

    st = os.stat(path)
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000_000))
    with pytest.raises(CatalogError):
        load_catalog(path)  # fails loud on the edit, and does not cache the bad catalog


def test_no_shipped_part_cites_a_missing_source_file():
    # Every catalog part must cite a source file that exists (a real provenance claim,
    # not a ghost), mirroring career.py's proof-path gate.
    assert source_gaps() == []


def test_source_gaps_flags_a_part_that_cites_a_missing_file(tmp_path):
    cat = _write(
        tmp_path,
        "- id: ghost\n  name: Ghost\n  source: parts/does_not_exist.py\n  category: c\n"
        "  maturity: beta\n  risk: low\n  reuse: {game: y}\n  purpose: p\n",
    )
    gaps = source_gaps(root=tmp_path, path=cat)
    assert any("ghost" in g and "does_not_exist" in g for g in gaps)
