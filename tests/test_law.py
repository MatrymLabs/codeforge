"""Test twin for parts/law.py -- legal/policy AWARENESS (never legal advice).

The hard boundary is the point: every view carries the disclaimer and ends with
"No legal conclusion. Human review required." Acceptance (index + detail render the
awareness lens) and refusal (unknown id, not mounted) are pinned; reachability is
proven through the engine tick with a repointed registry.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest

from forge import handle_command
from parts.law import law, law_detail, law_index
from parts.world.session import SESSIONS, Session

# ruff: noqa: E501  (the CSV fixture below has inherently long data lines)
_CSV = """source_id,domain,authority_tier,source_name,official_url,api_url,citation_format,document_owner,internal_owner,refresh_frequency,last_checked,last_changed,current_version_or_date,status,legal_reliance_note,related_internal_controls,review_required
PUB-NIST-800-171,cyber,2,NIST SP 800-171,https://csrc.nist.gov/x,,,NIST,Security Lead,monthly,2026-07-08,2021-01-28,Rev 2,current,,800-171-controls,no
"""


@pytest.fixture
def reg(tmp_path: Path) -> Path:
    p = tmp_path / "reg.csv"
    p.write_text(_CSV)
    return p


def test_index_carries_the_boundary(reg: Path) -> None:
    out = law_index(path=reg)
    assert "NOT legal advice" in out
    assert "PUB-NIST-800-171" in out
    assert "No legal conclusion. Human review required." in out


def test_detail_shows_jurisdiction_and_refuses_conclusions(reg: Path) -> None:
    out = law_detail("pub-nist-800-171", path=reg)
    assert "United States Federal" in out
    assert "2021-01-28" in out  # publication date surfaced
    assert "Applicability:     Not determined - human review required." in out
    assert "No legal conclusion. Human review required." in out


def test_unknown_source_still_refuses_a_conclusion(reg: Path) -> None:
    out = law_detail("bogus", path=reg)
    assert "No source" in out
    assert "Human review required" in out


def test_not_mounted_when_registry_absent(tmp_path: Path) -> None:
    assert "not mounted" in law(path=tmp_path / "absent.csv")


# --- reachable through the engine tick ---------------------------------------


@pytest.fixture(autouse=True)
def fresh() -> Iterator[None]:
    SESSIONS.clear()
    yield
    SESSIONS.clear()


def test_law_reachable_through_the_tick(reg: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # REGISTRY_PATH is read at call time, so the tick honors this repoint.
    monkeypatch.setattr("parts.law.REGISTRY_PATH", reg)
    session = Session(player_id="counsel")
    SESSIONS["counsel"] = session
    out = handle_command(session, "law")
    assert "NOT legal advice" in out
    assert "PUB-NIST-800-171" in out
