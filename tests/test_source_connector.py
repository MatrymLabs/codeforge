"""Test twin for kernel/seedlab/source_connector.py -- the safe, read-only local source connector.

Acceptance: register a directory as a source (provenance recorded), list/read/search ONLY approved
files, identify manifests/tests/docs, and read git branch+commit from .git/ files.

Refusal (the security surface -- fail loud): a path that escapes the root (`..`, absolute, or a
symlink pointing outside) is refused; a protected path (.env, keys, .git, secrets) is never listed,
searched, or read; an empty search query and a non-directory root are refused.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kernel.seedlab.project_model import Provenance
from kernel.seedlab.source_connector import (
    LocalSource,
    PathBoundaryError,
    ProtectedPathError,
    SourceConnectorError,
    source_connection,
    source_connector_label,
    source_label,
)

# A fake git sha + secret-file contents for the fixture (none are real). The commit is centralized
# and marked so the secret scanner treats it as the allowlisted test fixture it is.
_FAKE_COMMIT = "a1b2c3d4e5f6deadbeef"  # pragma: allowlist secret
_FAKE_SHORT = _FAKE_COMMIT[:12]  # what register() records (git short sha)


def _project(tmp_path: Path) -> Path:
    """A small project tree with a manifest, a test, docs, and planted protected files."""
    root = tmp_path / "proj"
    (root / "src").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    (root / "README.md").write_text("# Demo\na needle lives here\n", encoding="utf-8")
    (root / "src" / "app.py").write_text("def main():\n    return 42\n", encoding="utf-8")
    (root / "tests" / "test_app.py").write_text(
        "def test_main():\n    assert True\n", encoding="utf-8"
    )
    # Protected fixtures: excluded by FILENAME, so their contents are innocuous by design.
    (root / ".env").write_text("TOKEN=placeholder-not-a-real-value\n", encoding="utf-8")
    (root / "id_rsa").write_text("placeholder; a denylist fixture, not a key\n", encoding="utf-8")
    # a fake git working tree (read-only inspection, no real repo needed)
    (root / ".git").mkdir()
    (root / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (root / ".git" / "refs" / "heads").mkdir(parents=True)
    (root / ".git" / "refs" / "heads" / "main").write_text(_FAKE_COMMIT + "\n", encoding="utf-8")
    return root


def _source(tmp_path: Path, owner: str = "josh") -> LocalSource:
    return LocalSource(
        _project(tmp_path),
        Provenance("demo-src", owner=owner, license="MIT", visibility="private"),
    )


# --- acceptance --------------------------------------------------------------------------------
def test_register_records_provenance_and_metadata(tmp_path: Path) -> None:
    record = _source(tmp_path).register()
    assert record.source_id == "demo-src" and record.provenance.owner == "josh"
    assert record.branch == "main" and record.commit == _FAKE_SHORT
    assert (
        record.file_count == 4
    )  # pyproject, README, src/app.py, tests/test_app.py (secrets excluded)


def test_list_excludes_protected_files(tmp_path: Path) -> None:
    files = _source(tmp_path).list_files()
    assert "pyproject.toml" in files and "src/app.py" in files
    assert ".env" not in files and "id_rsa" not in files
    assert not any(f.startswith(".git") for f in files)


def test_read_returns_approved_content(tmp_path: Path) -> None:
    assert "return 42" in _source(tmp_path).read("src/app.py")


def test_search_finds_a_needle_in_approved_files(tmp_path: Path) -> None:
    hits = _source(tmp_path).search("needle")
    assert hits and hits[0][0] == "README.md"


def test_search_never_returns_a_secret(tmp_path: Path) -> None:
    # The value lives only in .env; a search must never surface it (protected files aren't read).
    assert _source(tmp_path).search("placeholder-not-a-real-value") == []


def test_identify_classifies_files(tmp_path: Path) -> None:
    ident = _source(tmp_path).identify()
    assert "pyproject.toml" in ident["manifests"]
    assert "tests/test_app.py" in ident["tests"]
    assert "README.md" in ident["docs"]


def test_source_label_is_hub_ready(tmp_path: Path) -> None:
    label = source_label(_source(tmp_path).register())
    assert label == f"local:demo-src (4 files, main@{_FAKE_SHORT})"


def test_source_connector_label_is_hub_ready(tmp_path: Path) -> None:
    label = source_connector_label(_source(tmp_path).register())
    assert label.startswith("connector:local-source:demo-src")
    assert "josh" in label and "private" in label and _FAKE_SHORT in label


def test_source_connection_is_structured(tmp_path: Path) -> None:
    payload = source_connection(_source(tmp_path).register())
    assert payload["source_id"] == "demo-src"
    assert payload["owner"] == "josh"
    assert payload["file_count"] == 4


def test_a_registered_source_lights_up_the_hub_sources_facet(tmp_path: Path) -> None:
    # Stage 3 -> Stage 2 wiring: a registered source's label populates the Project Hub's `sources`
    # facet, turning "none yet" into real data over both the text render and the contract.
    from kernel.seedlab.kernel import InMemorySeedStore, SeedKernel
    from kernel.seedlab.project_hub import ProjectHub, ProjectState

    kernel = SeedKernel(InMemorySeedStore(), clock=lambda: "2026-08-01T00:00:00+00:00")
    kernel.create_seed("Demo", "josh", "a demo", seed_id="seed-x")
    label = source_label(_source(tmp_path).register())

    hub = ProjectHub(kernel)
    state = ProjectState("seed-x", sources=(label,))
    assert label in hub.command("seed-x", "list sources", state)
    assert hub.contract("seed-x", state)["project"]["sources"] == [label]


def test_metadata_without_git(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / "a.txt").write_text("hi", encoding="utf-8")
    meta = LocalSource(plain, Provenance("plain")).metadata()
    assert meta["branch"] is None and meta["commit"] is None and meta["file_count"] == 1


# --- refusal: the security surface -------------------------------------------------------------
def test_traversal_is_refused(tmp_path: Path) -> None:
    with pytest.raises(PathBoundaryError, match="escapes"):
        _source(tmp_path).read("../../etc/passwd")


def test_absolute_path_is_refused(tmp_path: Path) -> None:
    with pytest.raises(PathBoundaryError, match="absolute"):
        _source(tmp_path).read("/etc/passwd")


def test_reading_a_protected_file_is_refused(tmp_path: Path) -> None:
    src = _source(tmp_path)
    with pytest.raises(ProtectedPathError):
        src.read(".env")
    with pytest.raises(ProtectedPathError):
        src.read("id_rsa")


def test_a_symlink_escaping_the_root_is_refused(tmp_path: Path) -> None:
    root = _project(tmp_path)
    outside = tmp_path / "outside_secret.txt"
    outside.write_text("top secret\n", encoding="utf-8")
    link = root / "escape_link"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not supported on this platform")
    src = LocalSource(root, Provenance("demo-src"))
    with pytest.raises(PathBoundaryError, match="escapes"):
        src.read("escape_link")  # resolve() follows the link out; the bounds-check refuses it


def test_empty_query_is_refused(tmp_path: Path) -> None:
    with pytest.raises(SourceConnectorError, match="non-empty"):
        _source(tmp_path).search("")


def test_a_non_directory_root_is_refused(tmp_path: Path) -> None:
    afile = tmp_path / "f.txt"
    afile.write_text("x", encoding="utf-8")
    with pytest.raises(SourceConnectorError, match="not a directory"):
        LocalSource(afile, Provenance("x"))


# --- edge branches -----------------------------------------------------------------------------
def test_reading_a_directory_is_refused(tmp_path: Path) -> None:
    with pytest.raises(SourceConnectorError, match="not a file"):
        _source(tmp_path).read("src")  # a directory, not a file


def test_search_respects_max_hits(tmp_path: Path) -> None:
    # 'e' occurs in several approved files; max_hits caps the result and returns early.
    assert len(_source(tmp_path).search("e", max_hits=1)) == 1


def test_search_skips_a_file_it_cannot_read(tmp_path: Path) -> None:
    class _Flaky(LocalSource):
        def read(self, relpath: str, **kw: object) -> str:
            if relpath == "README.md":
                raise SourceConnectorError("simulated unreadable file")
            return super().read(relpath, **kw)  # type: ignore[arg-type]

    src = _Flaky(_project(tmp_path), Provenance("demo-src"))
    # 'needle' lives only in the now-unreadable README: search skips it, never crashes.
    assert src.search("needle") == []


def _git_root(tmp_path: Path, name: str, head: str, loose: bool) -> LocalSource:
    root = tmp_path / name
    (root / ".git").mkdir(parents=True)
    (root / "a.txt").write_text("x", encoding="utf-8")
    (root / ".git" / "HEAD").write_text(head, encoding="utf-8")
    if loose:
        (root / ".git" / "refs" / "heads").mkdir(parents=True)
        (root / ".git" / "refs" / "heads" / "main").write_text(
            _FAKE_COMMIT + "\n", encoding="utf-8"
        )
    return LocalSource(root, Provenance(name))


def test_detached_head_reports_a_bare_commit(tmp_path: Path) -> None:
    meta = _git_root(tmp_path, "detached", _FAKE_COMMIT + "\n", loose=False).metadata()
    assert meta["branch"] is None and meta["commit"] == _FAKE_SHORT


def test_branch_without_a_loose_ref_reports_no_commit(tmp_path: Path) -> None:
    # HEAD names a branch but the commit lives only in packed-refs (no loose ref file).
    meta = _git_root(tmp_path, "packed", "ref: refs/heads/main\n", loose=False).metadata()
    assert meta["branch"] == "main" and meta["commit"] is None
