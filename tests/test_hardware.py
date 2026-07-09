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
