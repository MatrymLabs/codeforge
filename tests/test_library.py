"""Test twin for parts/library.py -- read the guidance library's documents.

Card functions run against a temp library root; reachability is proven through the
engine tick. Acceptance (list + read + case-insensitive) and refusal (not mounted,
unknown id, empty library) are both pinned.
"""

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from forge import handle_command
from parts.library import library, library_index, library_read
from parts.world.session import SESSIONS, Session


@pytest.fixture
def home(tmp_path: Path) -> Path:
    """A minimal FGL checkout root: one document + its text analog."""
    meta = tmp_path / "library" / "metadata"
    meta.mkdir(parents=True)
    text = tmp_path / "library" / "text"
    text.mkdir(parents=True)
    (text / "doc.txt").write_text(
        "NIST SP 800-171 protects Controlled Unclassified Information.", encoding="utf-8"
    )
    (meta / "documents.json").write_text(
        json.dumps(
            [
                {
                    "document_id": "nist_800_171",
                    "title": "NIST SP 800-171",
                    "domain": "cyber",
                    "freshness_status": "unknown",
                    "publication_date": "",
                    "retrieved_date": "2026-07-09",
                    "source_url": "https://csrc.nist.gov/x",
                    "text_path": "library/text/doc.txt",
                }
            ]
        ),
        encoding="utf-8",
    )
    return tmp_path


def test_index_lists_documents(home: Path) -> None:
    out = library_index(home=home)
    assert "nist_800_171" in out
    assert "1 document(s)" in out


def test_read_shows_metadata_and_text(home: Path) -> None:
    out = library_read("nist_800_171", home=home)
    assert "NIST SP 800-171" in out
    assert "Controlled Unclassified Information" in out  # the text analog is inlined
    assert "retrieved: 2026-07-09" in out
    assert "published: unknown" in out  # never invents a date it doesn't have


def test_read_is_case_insensitive(home: Path) -> None:
    assert "NIST SP 800-171" in library_read("NIST_800_171", home=home)


def test_unknown_document_is_helpful(home: Path) -> None:
    assert "No document" in library_read("bogus", home=home)


def test_missing_text_analog_is_reported_not_crashed(home: Path) -> None:
    (home / "library" / "text" / "doc.txt").unlink()
    out = library_read("nist_800_171", home=home)
    assert "Text analog missing" in out
    assert "NIST SP 800-171" in out  # metadata still shown


def test_not_mounted_when_home_absent(tmp_path: Path) -> None:
    assert "not mounted" in library(home=tmp_path / "absent")


def test_empty_library_message(tmp_path: Path) -> None:
    assert "No documents" in library_index(home=tmp_path)


@pytest.fixture(autouse=True)
def fresh() -> Iterator[None]:
    SESSIONS.clear()
    yield
    SESSIONS.clear()


def test_library_reachable_through_the_tick(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # FGL_HOME is read at call time, so the tick honors this repoint.
    monkeypatch.setattr("parts.library.FGL_HOME", home)
    session = Session(player_id="reader")
    session.location = "archive"
    SESSIONS["reader"] = session
    assert "nist_800_171" in handle_command(session, "library")
    assert "Controlled Unclassified Information" in handle_command(session, "library nist_800_171")
