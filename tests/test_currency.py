"""Test twin for the toolchain currency audit.

Every case here runs with a FAKE fetch. The audit's whole reason for taking an injected seam is
that a checker which can only be exercised against the live internet is a checker nobody runs in
a test, and one that turns CI red when GitHub has a bad afternoon.

The load-bearing cases are the two that are easy to get wrong: UNVERIFIABLE must never read as a
pass, and the per-ecosystem resolver must be honoured, because asking the wrong source produces a
confident wrong answer rather than an error.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kernel.currency import PIN_SITES, Tool, find_pin, read_inventory, unmatched_pins
from scripts.currency_audit import (
    BEHIND,
    CURRENT,
    UNVERIFIABLE,
    audit,
    http_fetch,
    latest_from_hashicorp,
    render,
)

REPO = Path(__file__).resolve().parent.parent


def _tool(name: str = "widget", pinned: str = "1.0.0", ecosystem: str = "github-release") -> Tool:
    return Tool(
        name=name, pinned=pinned, where="somewhere", ecosystem=ecosystem, locator="fake://x"
    )


def _github(tag: str):
    return lambda _locator: json.dumps({"tag_name": tag}).encode()


def test_a_matching_pin_is_current() -> None:
    (verdict,) = audit([_tool(pinned="1.0.0")], _github("v1.0.0"))
    assert verdict.status == CURRENT


def test_the_v_prefix_does_not_make_a_current_pin_look_stale() -> None:
    """`v1.34.2` and `1.34.2` are the same version wearing different clothes."""
    (verdict,) = audit([_tool(pinned="1.34.2")], _github("v1.34.2"))
    assert verdict.status == CURRENT


def test_an_older_pin_is_behind_and_names_the_gap() -> None:
    (verdict,) = audit([_tool(pinned="1.34.2")], _github("v1.36.12"))
    assert verdict.status == BEHIND
    assert verdict.latest == "v1.36.12"


def test_a_fetch_failure_is_unverifiable_not_a_pass() -> None:
    """The case this file exists for. "I could not check" must never render as "fine"."""

    def explode(_locator: str) -> bytes:
        raise OSError("network is down")

    (verdict,) = audit([_tool()], explode)
    assert verdict.status == UNVERIFIABLE
    assert verdict.status != CURRENT
    assert "network is down" in verdict.detail


def test_unparseable_payload_is_unverifiable_not_a_crash() -> None:
    (verdict,) = audit([_tool()], lambda _l: b"<html>not json</html>")
    assert verdict.status == UNVERIFIABLE


def test_an_unknown_ecosystem_is_unverifiable() -> None:
    (verdict,) = audit([_tool(ecosystem="carrier-pigeon")], _github("v9.9.9"))
    assert verdict.status == UNVERIFIABLE
    assert "carrier-pigeon" in verdict.detail


def test_the_go_proxy_resolver_reads_the_field_the_proxy_actually_uses() -> None:
    """The govulncheck lesson, pinned as a test.

    golang.org/x/vuln is developed at go.googlesource.com. Its GitHub mirror does not carry every
    release, so GitHub reports v1.1.4 while the proxy reports v1.7.0. Both payloads are real. Ask
    the wrong one and a CURRENT pin is filed as six versions ahead of upstream, which is not a
    thing that can happen and would have been reported as a defect.
    """
    proxy = lambda _l: json.dumps({"Version": "v1.7.0"}).encode()  # noqa: E731
    (verdict,) = audit([_tool(name="govulncheck", pinned="1.7.0", ecosystem="go-proxy")], proxy)
    assert verdict.status == CURRENT

    # The same pin, asked of the mirror, would have looked wrong.
    (mirror_verdict,) = audit(
        [_tool(name="govulncheck", pinned="1.7.0", ecosystem="github-release")], _github("v1.1.4")
    )
    assert mirror_verdict.status == BEHIND


def test_hashicorp_index_ignores_prereleases() -> None:
    """A beta is not a version we pin to, and must not be reported as the one we are behind."""
    payload = json.dumps({"versions": {"1.9.8": {}, "1.15.8": {}, "1.16.0-beta1": {}}}).encode()
    assert latest_from_hashicorp(payload) == "1.15.8"


@pytest.mark.parametrize("locator", ["file:///etc/passwd", "ftp://x/y", "http://x/y"])
def test_the_real_fetch_refuses_a_non_https_locator(locator: str) -> None:
    """urlopen honours whatever scheme it is handed, including file:.

    A locator reaching the fetch from anywhere less trustworthy than the declared inventory could
    otherwise read the local disk and have the contents parsed as a version string. bandit flags
    this as B310; constraining the scheme is the fix, and silencing the check is not.
    """
    with pytest.raises(ValueError, match="non-HTTPS"):
        http_fetch(locator)


def test_every_declared_locator_is_https() -> None:
    """The inventory must satisfy the rule the fetch enforces, or a real run dies at the guard."""
    offenders = [t.name for t in read_inventory(REPO) if not t.locator.startswith("https://")]
    assert offenders == [], f"these pin sites use a non-HTTPS locator: {offenders}"


def test_unverifiable_is_called_out_in_the_report() -> None:
    report = render(audit([_tool()], lambda _l: b"nope"))
    assert "UNVERIFIABLE" in report
    assert "is not a pass" in report


# --- the inventory itself, against the real working tree -------------------------------------


def test_every_declared_pin_still_matches_its_file() -> None:
    """A pattern that stops matching must fail loudly, not shrink the audit in silence.

    If a pin moves file or changes shape, the audit would otherwise cover nine tools where it used
    to cover ten and still report a clean run. Silent shrinkage is how a gate stops covering
    things without ever going red.
    """
    assert unmatched_pins(REPO) == [], (
        "these pin patterns no longer match anything; the audit has silently stopped covering "
        f"them: {unmatched_pins(REPO)}"
    )


def test_the_inventory_is_not_empty() -> None:
    assert PIN_SITES, "no pins declared; every test above would pass vacuously"
    assert len(read_inventory(REPO)) == len(PIN_SITES)


@pytest.mark.parametrize("site", PIN_SITES, ids=lambda s: s.name)
def test_each_pin_resolves_to_something_version_shaped(site) -> None:
    found = find_pin(REPO, site)
    assert found is not None, f"{site.name}: pattern found nothing in {site.file}"
    assert found[0].isdigit(), f"{site.name}: {found!r} does not look like a version"
