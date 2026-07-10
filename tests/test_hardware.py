"""Test twin for parts/hardware.py -- the cross-domain reusable-parts catalog.

Acceptance: the shipped catalog loads and every part maps to a domain.
Refusal: a malformed entry fails loud rather than stocking a bad part."""

import pytest

from parts.hardware import CatalogError, catalog_text, find_part, load_catalog


def _write(tmp_path, text: str):
    path = tmp_path / "parts.yaml"
    path.write_text(text)
    return path


def test_shipped_catalog_loads_and_every_part_maps_to_a_domain():
    parts = load_catalog()  # the real catalog/parts.yaml
    assert parts, "the shipped catalog should stock at least one part"
    assert all(part.reuse for part in parts)  # each part reuses in >=1 domain
    assert all(part.source for part in parts)  # each names its source file


def test_every_shipped_part_is_free_to_use_and_records_its_pattern():
    # the Free-to-Use rule, enforced: clear provenance + the pattern it was rebuilt from
    parts = load_catalog()
    assert all(part.source_status == "original" for part in parts)
    assert all(part.license for part in parts)
    assert all(part.influence for part in parts), "each part should record its known pattern"


def test_every_shipped_part_shows_its_road_not_taken():
    # the experimental section: what the part would become if it were NOT frameless
    parts = load_catalog()
    assert all(part.experimental for part in parts), "each part should note its non-frameless path"
    text = catalog_text()
    assert "experimental (if not frameless)" in text


def test_experimental_is_optional_and_omitted_when_absent(tmp_path):
    # a part without an experimental note loads fine and prints no experimental line
    catalog = _write(
        tmp_path,
        "- id: x\n  name: X\n  source: parts/x.py\n  category: c\n  purpose: p\n"
        "  maturity: beta\n  risk: low\n  reuse: {game: y}\n",
    )
    part = load_catalog(catalog)[0]
    assert part.experimental == ""
    assert "experimental (if not frameless)" not in catalog_text(catalog)


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
