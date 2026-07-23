"""Test twin for parts/cast_update.py -- the read-only cast drift report (U1 slice 1).

Acceptance: a real engine drift (a changed carried module, an upstream-only file, a cast-only file)
is named, and the commit delta is reported from an injected source seam (offline). Refusal: a dir
with no manifest, and a source that is not a checkout, both fail loud. Edge: a one-byte content
difference counts as changed; an identical tree reports no drift.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from parts.cast import CastError, CastManifest, main, write_manifest
from parts.cast_update import (
    CastDrift,
    _commit_present,
    _engine_files,
    _read_at_commit,
    _resolve_commit,
    diff_cast,
    render_drift,
)


def _raise_oserror(*args, **kwargs):
    raise OSError("git not found")


def _pin_reader(files: dict[str, str]):
    """A fake read_at_commit: returns the given files' bytes at the pin, None for anything else."""
    return lambda root, commit, rel: files[rel].encode() if rel in files else None


def _engine_tree(root: Path, files: dict[str, str]) -> None:
    """Lay down an engine tree (forge.py + parts/**) with the given root-relative file bodies."""
    for rel, body in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)


def _poured_cast(root: Path, files: dict[str, str], *, commit: str, strategy: str) -> None:
    """A poured cast: an engine tree plus a cast_manifest.json pinning its source commit."""
    _engine_tree(root, files)
    write_manifest(
        CastManifest(
            seed_id="CAST-X-001",
            seed_name="X",
            template="blank_mud",
            codeforge_commit=commit,
            engine_strategy=strategy,
        ),
        root / "cast_manifest.json",
    )


_BASE = {
    "forge.py": "def handle_command(session, text):\n    return 'ok'\n",
    "parts/__init__.py": "",
    "parts/world/__init__.py": "",
    "parts/world/combat.py": "def hit():\n    return 1\n",
}


def test_a_cast_matching_the_source_has_no_drift(tmp_path: Path) -> None:
    cast, source = tmp_path / "cast", tmp_path / "src"
    _poured_cast(cast, _BASE, commit="aaa111", strategy="vendored-whole")
    _engine_tree(source, _BASE)
    drift = diff_cast(cast, source, resolve_commit=lambda r: "aaa111")
    assert not drift.has_engine_drift
    assert drift.changed == [] and drift.upstream_only == [] and drift.cast_only == []
    assert drift.pinned_commit == "aaa111" and drift.target_commit == "aaa111"


def test_a_changed_upstream_module_is_named(tmp_path: Path) -> None:
    cast, source = tmp_path / "cast", tmp_path / "src"
    _poured_cast(cast, _BASE, commit="aaa111", strategy="vendored-whole")
    bumped = dict(_BASE)
    bumped["parts/world/combat.py"] = "def hit():\n    return 2\n"  # one-byte fix upstream
    _engine_tree(source, bumped)
    drift = diff_cast(cast, source, resolve_commit=lambda r: "bbb222")
    assert drift.changed == ["parts/world/combat.py"]
    assert drift.has_engine_drift
    assert drift.pinned_commit == "aaa111" and drift.target_commit == "bbb222"


def test_upstream_only_and_cast_only_are_split(tmp_path: Path) -> None:
    cast, source = tmp_path / "cast", tmp_path / "src"
    cast_files = dict(_BASE)
    cast_files["parts/house_rules.py"] = "HOUSE = 1\n"  # the owner added a module to the cast
    _poured_cast(cast, cast_files, commit="aaa111", strategy="vendored-whole")
    source_files = dict(_BASE)
    source_files["parts/new_core.py"] = "NEW = 1\n"  # a module that appeared upstream
    _engine_tree(source, source_files)
    drift = diff_cast(cast, source, resolve_commit=lambda r: "bbb222")
    assert drift.upstream_only == ["parts/new_core.py"]
    assert drift.cast_only == ["parts/house_rules.py"]
    assert drift.changed == []


def test_a_selective_cast_flags_shed_modules_as_upstream_only(tmp_path: Path) -> None:
    # A selective cast SHED modules at pour time; those read as upstream_only here (slice 1 cannot
    # yet tell "shed" from "genuinely new" -- that is the closure slice). Documented, not hidden.
    cast, source = tmp_path / "cast", tmp_path / "src"
    _poured_cast(cast, _BASE, commit="aaa111", strategy="vendored-selective")
    fuller = dict(_BASE)
    fuller["parts/pm.py"] = "# a dev-tool the game shed\n"
    _engine_tree(source, fuller)
    drift = diff_cast(cast, source, resolve_commit=lambda r: "bbb222")
    assert drift.upstream_only == ["parts/pm.py"]
    assert drift.engine_strategy == "vendored-selective"


def test_a_dir_without_a_manifest_is_refused(tmp_path: Path) -> None:
    cast, source = tmp_path / "cast", tmp_path / "src"
    _engine_tree(cast, _BASE)  # engine files but NO cast_manifest.json
    _engine_tree(source, _BASE)
    with pytest.raises(CastError, match="not a poured cast"):
        diff_cast(cast, source, resolve_commit=lambda r: "x")


def test_a_source_that_is_not_a_checkout_is_refused(tmp_path: Path) -> None:
    cast, source = tmp_path / "cast", tmp_path / "src"
    _poured_cast(cast, _BASE, commit="aaa111", strategy="vendored-whole")
    source.mkdir()
    (source / "readme.txt").write_text("not an engine")  # no forge.py / parts/
    with pytest.raises(CastError, match="not a codeforge checkout"):
        diff_cast(cast, source, resolve_commit=lambda r: "x")


def test_engine_files_skips_pycache_and_hashes_content(tmp_path: Path) -> None:
    _engine_tree(tmp_path, _BASE)
    (tmp_path / "parts" / "__pycache__").mkdir()
    (tmp_path / "parts" / "__pycache__" / "cached.py").write_text("x = 1\n")  # a .py in a cache
    files = _engine_files(tmp_path)
    assert "forge.py" in files and "parts/world/combat.py" in files
    assert not any("__pycache__" in f for f in files)  # caches never compared, even a .py within


def test_engine_files_tolerates_a_missing_forge_or_parts(tmp_path: Path) -> None:
    assert _engine_files(tmp_path) == {}  # neither forge.py nor parts/ -> empty, no crash
    (tmp_path / "forge.py").write_text("y = 1\n")  # forge.py but no parts/
    assert list(_engine_files(tmp_path)) == ["forge.py"]


def test_resolve_commit_degrades_when_git_cannot_run(tmp_path: Path, monkeypatch) -> None:
    # the git call raising (OSError: no git on PATH) must degrade to 'unknown', never propagate
    import parts.cast_update as cu

    def _boom(*args, **kwargs):
        raise OSError("git not found")

    monkeypatch.setattr(cu.subprocess, "run", _boom)
    assert cu._resolve_commit(tmp_path) == "unknown"


def test_resolve_commit_returns_unknown_outside_a_repo(tmp_path: Path) -> None:
    # git rev-parse is a LOCAL call (no network); a non-repo dir degrades to 'unknown', never raises
    assert _resolve_commit(tmp_path) == "unknown"


def test_resolve_commit_reads_the_real_checkout() -> None:
    # the codeforge tree IS a git checkout: the default seam yields a real short commit, not unknown
    repo_root = Path(__file__).resolve().parent.parent
    commit = _resolve_commit(repo_root)
    assert commit != "unknown" and commit.strip() == commit and len(commit) >= 4


def test_render_shows_in_sync_when_there_is_no_drift() -> None:
    drift = CastDrift(cast_dir="c", pinned_commit="a", target_commit="a", engine_strategy="whole")
    out = render_drift(drift)
    assert "IN SYNC" in out and "pinned commit:    a" in out


def test_render_names_every_drift_bucket() -> None:
    drift = CastDrift(
        cast_dir="c",
        pinned_commit="a",
        target_commit="b",
        engine_strategy="vendored-selective",
        changed=["parts/world/combat.py"],
        upstream_only=["parts/new_core.py"],
        newly_upstream=["parts/new_core.py"],
        cast_only=["parts/house_rules.py"],
        pin_verifiable=True,
    )
    out = render_drift(drift)
    assert "parts/world/combat.py" in out  # changed
    assert "parts/new_core.py" in out  # newly upstream (split of upstream-only)
    assert "parts/house_rules.py" in out  # cast-only
    assert "Read-only report" in out  # never mistaken for an apply


def test_render_falls_back_to_raw_upstream_when_pin_unverifiable() -> None:
    drift = CastDrift(
        cast_dir="c",
        pinned_commit="dead",
        target_commit="b",
        engine_strategy="vendored-selective",
        upstream_only=["parts/pm.py"],
        pin_verifiable=False,  # cannot split new-vs-shed without the pin
    )
    out = render_drift(drift)
    assert "upstream-only (new upstream, or shed" in out and "parts/pm.py" in out


def test_cli_diff_prints_a_report(tmp_path, capsys) -> None:
    cast, source = tmp_path / "cast", tmp_path / "src"
    _poured_cast(cast, _BASE, commit="aaa111", strategy="vendored-whole")
    _engine_tree(source, _BASE)
    assert main(["diff", str(cast), str(source)]) == 0
    assert "Cast drift" in capsys.readouterr().out


def test_cli_diff_usage_error_without_args(capsys) -> None:
    assert main(["diff"]) == 2
    assert "usage" in capsys.readouterr().err


def test_cli_diff_refuses_a_dir_that_is_not_a_cast(tmp_path, capsys) -> None:
    cast, source = tmp_path / "cast", tmp_path / "src"
    _engine_tree(cast, _BASE)  # no manifest
    _engine_tree(source, _BASE)
    assert main(["diff", str(cast), str(source)]) == 2
    assert "not a poured cast" in capsys.readouterr().err


# --- Slice 3: split upstream_only into newly-upstream vs shed (by the pin) ----------------------


def test_upstream_only_splits_into_new_and_shed(tmp_path: Path) -> None:
    cast, source = tmp_path / "cast", tmp_path / "src"
    _poured_cast(cast, _BASE, commit="aaa111", strategy="vendored-selective")
    source_files = dict(_BASE)
    source_files["parts/pm.py"] = "# a dev-tool shed at pour\n"  # existed at the pin -> shed
    source_files["parts/brand_new.py"] = "# appeared upstream since pour\n"  # absent at pin -> new
    _engine_tree(source, source_files)
    at_pin = dict(_BASE)
    at_pin["parts/pm.py"] = (
        "# a dev-tool shed at pour\n"  # pm existed at the pin; brand_new did not
    )
    drift = diff_cast(
        cast,
        source,
        resolve_commit=lambda r: "bbb222",
        commit_present=lambda r, c: True,
        read_at_commit=_pin_reader(at_pin),
    )
    assert drift.upstream_only == ["parts/brand_new.py", "parts/pm.py"]  # the raw union, sorted
    assert drift.newly_upstream == ["parts/brand_new.py"]  # absent at the pin: genuinely new
    assert drift.shed == ["parts/pm.py"]  # present at the pin: deliberately not carried


def test_a_whole_cast_has_no_shed_only_new(tmp_path: Path) -> None:
    # a vendored-whole cast carried everything at pour, so upstream_only is all genuinely new
    cast, source = tmp_path / "cast", tmp_path / "src"
    _poured_cast(cast, _BASE, commit="aaa111", strategy="vendored-whole")
    source_files = dict(_BASE)
    source_files["parts/brand_new.py"] = "# new upstream\n"
    _engine_tree(source, source_files)
    drift = diff_cast(
        cast,
        source,
        resolve_commit=lambda r: "bbb222",
        commit_present=lambda r, c: True,
        read_at_commit=_pin_reader(_BASE),  # brand_new absent at pin -> new; nothing shed
    )
    assert drift.newly_upstream == ["parts/brand_new.py"] and drift.shed == []


def test_render_splits_new_from_shed_when_verifiable() -> None:
    drift = CastDrift(
        cast_dir="c",
        pinned_commit="a",
        target_commit="b",
        engine_strategy="vendored-selective",
        upstream_only=["parts/brand_new.py", "parts/pm.py"],
        newly_upstream=["parts/brand_new.py"],
        shed=["parts/pm.py"],
        pin_verifiable=True,
    )
    out = render_drift(drift)
    assert "newly upstream since your pin" in out and "parts/brand_new.py" in out
    assert "shed by this cast" in out and "parts/pm.py" in out


# --- Slice 2: local-edit detection (vendored file vs the source AT THE PIN) --------------------


def test_a_locally_edited_file_is_flagged(tmp_path: Path) -> None:
    cast, source = tmp_path / "cast", tmp_path / "src"
    edited = dict(_BASE)
    edited["parts/world/combat.py"] = "def hit():\n    return 999  # owner tweak after pour\n"
    _poured_cast(cast, edited, commit="aaa111", strategy="vendored-whole")
    _engine_tree(source, edited)  # target == cast content, so no 'changed'; but the PIN had _BASE
    drift = diff_cast(
        cast,
        source,
        resolve_commit=lambda r: "aaa111",
        commit_present=lambda r, c: True,
        read_at_commit=_pin_reader(_BASE),  # the pin's combat.py was the original
    )
    assert drift.locally_modified == ["parts/world/combat.py"]
    assert drift.pin_verifiable and not drift.in_sync


def test_an_owner_added_file_is_not_a_local_edit(tmp_path: Path) -> None:
    cast, source = tmp_path / "cast", tmp_path / "src"
    with_extra = dict(_BASE)
    with_extra["parts/house_rules.py"] = "HOUSE = 1\n"  # added by the owner AFTER pour
    _poured_cast(cast, with_extra, commit="aaa111", strategy="vendored-whole")
    _engine_tree(source, _BASE)
    drift = diff_cast(
        cast,
        source,
        resolve_commit=lambda r: "aaa111",
        commit_present=lambda r, c: True,
        read_at_commit=_pin_reader(
            _BASE
        ),  # house_rules absent at the pin -> None -> added, not edited
    )
    assert drift.locally_modified == []  # absent-at-pin is owner-ADDED, not a local edit
    assert drift.cast_only == ["parts/house_rules.py"]


def test_pin_absent_from_source_cannot_verify_local_edits(tmp_path: Path) -> None:
    cast, source = tmp_path / "cast", tmp_path / "src"
    _poured_cast(cast, _BASE, commit="deadbee", strategy="vendored-whole")
    _engine_tree(source, _BASE)
    drift = diff_cast(
        cast,
        source,
        resolve_commit=lambda r: "tgt",
        commit_present=lambda r, c: False,  # the pin is not in the source repo
        read_at_commit=_raise_oserror,  # must NOT be called when the pin is unverifiable
    )
    assert not drift.pin_verifiable and drift.locally_modified == []


def test_render_flags_local_edits_as_overwrite_risk() -> None:
    drift = CastDrift(
        cast_dir="c",
        pinned_commit="a",
        target_commit="b",
        engine_strategy="whole",
        locally_modified=["parts/world/combat.py"],
        pin_verifiable=True,
    )
    out = render_drift(drift)
    assert "local edits:      1 file(s) modified" in out
    assert "an update would overwrite these" in out and "parts/world/combat.py" in out


def test_render_says_when_it_cannot_verify_the_pin() -> None:
    drift = CastDrift(
        cast_dir="c",
        pinned_commit="deadbee",
        target_commit="b",
        engine_strategy="whole",
        pin_verifiable=False,
    )
    out = render_drift(drift)
    assert "cannot verify" in out and "deadbee" in out


def test_commit_present_and_read_at_commit_on_the_real_repo() -> None:
    # git cat-file / git show are LOCAL (no network); exercise the real seams against this checkout
    repo = Path(__file__).resolve().parent.parent
    head = _resolve_commit(repo)
    assert _commit_present(repo, head)
    assert not _commit_present(repo, "unknown")  # early-out on the sentinel, no git call
    assert not _commit_present(repo, "0000000")  # a well-formed but non-existent commit
    blob = _read_at_commit(repo, head, "forge.py")
    assert blob is not None and b"handle_command" in blob
    assert _read_at_commit(repo, head, "no/such/file.py") is None  # absent path -> None


def test_git_history_seams_degrade_when_git_raises(tmp_path: Path, monkeypatch) -> None:
    import parts.cast_update as cu

    monkeypatch.setattr(cu.subprocess, "run", _raise_oserror)
    assert cu._commit_present(tmp_path, "abc1234") is False
    assert cu._read_at_commit(tmp_path, "abc1234", "forge.py") is None


def test_drift_is_a_frozen_report(tmp_path: Path) -> None:
    drift = CastDrift(cast_dir="c", pinned_commit="a", target_commit="b", engine_strategy="w")
    with pytest.raises(FrozenInstanceError):
        drift.changed = ["x"]  # type: ignore[misc]  # frozen: a report never mutates
