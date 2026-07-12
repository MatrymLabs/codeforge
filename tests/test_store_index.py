"""Test twin for parts/store_index.py -- V3 catalog domains, addressing, and search."""

import pytest

from forge import handle_command
from parts.hardware import Part
from parts.session import Session
from parts.store_index import (
    Domain,
    DomainError,
    addressed,
    domain_for,
    load_domains,
    render_index,
    search,
)

_DOMAINS = [
    Domain("05", "Resilience", frozenset({"resilience", "rate-limiting"})),
    Domain("01", "Validation", frozenset({"validation"})),
]


def _part(pid: str, category: str, name: str = "X", maturity: str = "beta") -> Part:
    return Part(
        id=pid,
        name=name,
        source=f"parts/{pid}.py",
        category=category,
        purpose="does a thing",
        maturity=maturity,
        risk="low",
        reuse={"general": "use"},
    )


def test_domain_for_maps_category():
    assert domain_for(_part("retry", "resilience"), _DOMAINS).name == "Resilience"


def test_unmapped_category_has_no_domain():
    assert domain_for(_part("x", "weird"), _DOMAINS) is None


def test_addressed_assigns_domain_ordinals():
    parts = [
        _part("token-bucket", "rate-limiting"),
        _part("retry", "resilience"),
        _part("odd", "weird"),
    ]
    addr = {p.id: a for a, p in addressed(parts, _DOMAINS)}
    assert addr["retry"].startswith("05.")
    assert addr["token-bucket"].startswith("05.")
    assert addr["odd"].startswith("00.")  # unmapped files under domain 00


def test_search_matches_multiple_fields():
    parts = [_part("retry", "resilience", name="Retry Policy")]
    assert search(parts, "retry", domains=_DOMAINS)  # id + name
    assert search(parts, "resilience", domains=_DOMAINS)  # domain name
    assert search(parts, "nonsense", domains=_DOMAINS) == []


def test_empty_query_returns_nothing():
    assert search([_part("a", "validation")], "   ") == []


def test_render_index_groups_by_domain():
    out = render_index([_part("retry", "resilience", name="Retry")], _DOMAINS)
    assert "Resilience" in out
    assert "retry" in out


def test_load_domains_reads_the_real_taxonomy():
    assert any(d.name == "Validation" for d in load_domains())


@pytest.mark.parametrize(
    "body, needle",
    [
        ("domains: []", "non-empty"),
        ("nope: 1", "non-empty"),
        ("domains:\n  - name: X", "'code' and 'name'"),
        ("domains:\n  - code: '01'\n    name: A\n  - code: '01'\n    name: B", "not unique"),
        (
            "domains:\n  - code: '01'\n    name: A\n    categories: [v]\n"
            "  - code: '02'\n    name: B\n    categories: [v]",
            "claimed by both",
        ),
    ],
)
def test_bad_domains_fail_loud(tmp_path, body, needle):
    path = tmp_path / "d.yaml"
    path.write_text(body)
    with pytest.raises(DomainError) as err:
        load_domains(path)
    assert needle in str(err.value)


def test_store_verb_is_tick_reachable():
    out = handle_command(Session(player_id="matrym", location="courtyard"), "store")
    assert "V3 catalog" in out


def test_store_find_searches_the_catalog():
    out = handle_command(Session(player_id="matrym", location="courtyard"), "store find retry")
    assert "retry" in out.lower()
