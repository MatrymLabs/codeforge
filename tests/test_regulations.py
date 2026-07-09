"""Test twin for parts/regulations.py -- read-only guidance reference."""
# ruff: noqa: E501  (the CSV fixture below has inherently long data lines)

from pathlib import Path

import pytest

from parts.regulations import regs

_CSV = """# the guidance library registry (comment line, skipped)
source_id,domain,authority_tier,source_name,official_url,api_url,citation_format,document_owner,internal_owner,refresh_frequency,last_checked,last_changed,current_version_or_date,status,legal_reliance_note,related_internal_controls,review_required
REG-CMMC-32CFR170,cmmc,1,32 CFR Part 170,https://ecfr.gov/x,,,DoD,Compliance Lead,weekly,2026-07-08,,2025 rule,current,verify vs GovInfo,cmmc-l1;cmmc-l2,no
PUB-NIST-800-171,cyber,2,NIST SP 800-171,https://csrc.nist.gov/x,,,NIST,Security Lead,monthly,2026-07-08,,Rev 2,current,,800-171-controls,no
"""


@pytest.fixture
def reg(tmp_path: Path) -> Path:
    p = tmp_path / "reg.csv"
    p.write_text(_CSV)
    return p


def test_index_lists_every_source(reg: Path) -> None:
    out = regs(path=reg)
    assert "REG-CMMC-32CFR170" in out and "PUB-NIST-800-171" in out
    assert "2 source(s) filed." in out


def test_domain_filter(reg: Path) -> None:
    out = regs("cmmc", path=reg)
    assert "REG-CMMC-32CFR170" in out and "PUB-NIST-800-171" not in out


def test_domain_filter_is_case_insensitive(reg: Path) -> None:
    assert "REG-CMMC-32CFR170" in regs("CMMC", path=reg)


def test_detail_by_id_lowercased_by_the_tick(reg: Path) -> None:
    # the engine tick lowercases routed input, so ids arrive lowercase
    out = regs("reg-cmmc-32cfr170", path=reg)
    assert "32 CFR Part 170" in out
    assert "cmmc-l1, cmmc-l2" in out
    assert "verify vs GovInfo" in out


def test_unknown_id_is_helpful(reg: Path) -> None:
    assert "No source" in regs("bogus", path=reg)


def test_keyword_search_finds_nist(reg: Path) -> None:
    out = regs("nist", path=reg)  # not a domain, not an exact id -> keyword search
    assert "matching 'nist'" in out
    assert "PUB-NIST-800-171" in out  # matches on id + name
    assert "REG-CMMC-32CFR170" not in out  # cmmc row doesn't mention nist


def test_detail_shows_version_and_publication_date(reg: Path) -> None:
    out = regs("pub-nist-800-171", path=reg)
    assert "Version: Rev 2" in out
    assert "published/last changed:" in out  # the publication/revision date field


def test_reports_unnoted_reliance(reg: Path) -> None:
    # NIST row has a blank legal_reliance_note -> shown as "(none noted)"
    assert "(none noted)" in regs("pub-nist-800-171", path=reg)


def test_not_mounted_message_when_registry_missing(tmp_path: Path) -> None:
    assert "not mounted" in regs(path=tmp_path / "absent.csv")
