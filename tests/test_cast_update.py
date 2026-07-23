"""Test twin for parts/cast_update.py -- the read-only cast drift report (U1 slice 1).

Acceptance: a real engine drift (a changed carried module, an upstream-only file, a cast-only file)
is named, and the commit delta is reported from an injected source seam (offline). Refusal: a dir
with no manifest, and a source that is not a checkout, both fail loud. Edge: a one-byte content
difference counts as changed; an identical tree reports no drift.
"""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from parts.cast import CastError, CastManifest, main, read_manifest, write_manifest
from parts.cast_update import (
    CastDrift,
    UpdateOutcome,
    _commit_present,
    _engine_files,
    _read_at_commit,
    _req_name,
    _resolve_commit,
    _restore_engine,
    audit_requirements,
    diff_cast,
    render_audit,
    render_drift,
    render_update,
    update_cast,
)


def _write_pyproject(root: Path, deps: list[str]) -> None:
    """Write a minimal pyproject.toml declaring `deps` under [project].dependencies."""
    body = "dependencies = [\n" + "".join(f'    "{d}",\n' for d in deps) + "]\n"
    (root / "pyproject.toml").write_text(f'[project]\nname = "x"\nversion = "0"\n{body}')


_PIP_AUDIT_JSON = json.dumps(
    {
        "dependencies": [
            {
                "name": "pyyaml",
                "version": "5.3",
                "vulns": [{"id": "PYSEC-1", "fix_versions": ["5.4"]}],
            },
            {"name": "sqlalchemy", "version": "2.0", "vulns": []},
        ]
    }
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


def _poured_cast(
    root: Path, files: dict[str, str], *, commit: str, strategy: str, surfaces=()
) -> None:
    """A poured cast: an engine tree plus a cast_manifest.json pinning its source commit."""
    _engine_tree(root, files)
    write_manifest(
        CastManifest(
            seed_id="CAST-X-001",
            seed_name="X",
            template="blank_mud",
            codeforge_commit=commit,
            engine_strategy=strategy,
            surfaces=list(surfaces),
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


# --- Slice 4: dependency delta (offline) + CVE audit (pip-audit behind a runner seam) -----------


def test_dependency_delta_is_reported(tmp_path: Path) -> None:
    cast, source = tmp_path / "cast", tmp_path / "src"
    _poured_cast(cast, _BASE, commit="aaa111", strategy="vendored-whole")
    _write_pyproject(cast, ["pyyaml>=6.0", "sqlalchemy>=2.0", "old-lib>=1.0"])
    _engine_tree(source, _BASE)
    _write_pyproject(source, ["pyyaml>=6.0", "sqlalchemy>=2.1", "new-lib>=3.0"])
    drift = diff_cast(cast, source, resolve_commit=lambda r: "bbb222")
    assert drift.deps_added == ["new-lib>=3.0"]
    assert drift.deps_removed == ["old-lib>=1.0"]
    assert drift.deps_changed == ["sqlalchemy: sqlalchemy>=2.0 -> sqlalchemy>=2.1"]
    assert drift.has_dep_drift and not drift.in_sync


def test_no_dep_delta_without_pyprojects(tmp_path: Path) -> None:
    # a bare fixture (no pyproject either side) gets no phantom delta -- deps are not compared
    cast, source = tmp_path / "cast", tmp_path / "src"
    _poured_cast(cast, _BASE, commit="aaa111", strategy="vendored-whole")
    _engine_tree(source, _BASE)
    drift = diff_cast(cast, source, resolve_commit=lambda r: "aaa111")
    assert not drift.has_dep_drift and drift.deps_added == []


def test_req_name_normalizes_pep503() -> None:
    assert _req_name("PyYAML>=6.0") == "pyyaml"
    assert _req_name("SQLAlchemy>=2.0") == "sqlalchemy"
    assert _req_name("typing_extensions") == "typing-extensions"


def test_render_shows_the_dependency_sections() -> None:
    drift = CastDrift(
        cast_dir="c",
        pinned_commit="a",
        target_commit="b",
        engine_strategy="whole",
        deps_added=["new-lib>=3.0"],
        deps_changed=["sqlalchemy: >=2.0 -> >=2.1"],
        pin_verifiable=True,
    )
    out = render_drift(drift)
    assert "dependencies:     2 change(s)" in out
    assert "dependencies added upstream" in out and "new-lib>=3.0" in out
    assert "dependency version specs changed" in out and "sqlalchemy: >=2.0 -> >=2.1" in out


def test_audit_requirements_flags_a_vuln_via_the_runner_seam() -> None:
    findings = audit_requirements(["pyyaml==5.3"], runner=lambda reqs: _PIP_AUDIT_JSON)
    assert findings == ["pyyaml 5.3: PYSEC-1 (fix: 5.4)"]  # the clean dep contributes nothing


def test_audit_requirements_no_reqs_never_calls_the_runner() -> None:
    assert audit_requirements([], runner=_raise_oserror) == []  # empty -> no scan, runner untouched


def test_audit_requirements_tolerates_bad_json() -> None:
    assert audit_requirements(["x==1"], runner=lambda reqs: "not json at all") == []


def test_render_audit_clean_and_with_findings() -> None:
    assert "no known vulnerabilities" in render_audit([])
    out = render_audit(["pyyaml 5.3: PYSEC-1 (fix: 5.4)"])
    assert "dependency vulnerabilities (pip-audit)" in out and "PYSEC-1" in out


def test_pip_audit_runner_shells_out_and_cleans_up(monkeypatch) -> None:
    # cover the real runner offline: mock subprocess, prove it writes a reqs file and removes it
    import parts.cast_update as cu

    captured: dict[str, list[str]] = {}

    class _Done:
        stdout = '{"dependencies": []}'

    def _fake_run(cmd, **kwargs):
        captured["cmd"] = list(cmd)
        assert Path(cmd[2]).is_file()  # the requirements temp file exists during the run
        return _Done()

    monkeypatch.setattr(cu.subprocess, "run", _fake_run)
    out = cu._pip_audit_runner(["pyyaml>=6.0"])
    assert '"dependencies"' in out
    assert captured["cmd"][0] == "pip-audit" and captured["cmd"][1] == "-r"
    assert not Path(captured["cmd"][2]).exists()  # temp file cleaned up afterward


def test_cli_diff_audit_flag_runs_the_scan(tmp_path, capsys, monkeypatch) -> None:
    import parts.cast_update as cu

    monkeypatch.setattr(
        cu, "audit_requirements", lambda reqs, **k: ["pyyaml 5.3: PYSEC-1 (fix: 5.4)"]
    )
    cast, source = tmp_path / "cast", tmp_path / "src"
    _poured_cast(cast, _BASE, commit="aaa111", strategy="vendored-whole")
    _write_pyproject(cast, ["pyyaml==5.3"])
    _engine_tree(source, _BASE)
    assert main(["diff", str(cast), str(source), "--audit"]) == 0
    out = capsys.readouterr().out
    assert "dependency vulnerabilities (pip-audit)" in out and "PYSEC-1" in out


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


# --- U2: apply an engine update to a poured cast, safely -----------------------------------------

_BUMPED = {**_BASE, "parts/world/combat.py": "def hit():\n    return 2\n"}  # an upstream fix
_OK = lambda cd: (True, "commands ran clean")  # noqa: E731  a passing validator
_COMBAT = "parts/world/combat.py"


def _whole_cast_with_upstream_fix(tmp_path: Path, *, commit="aaa111", strategy="vendored-whole"):
    """A vendored-whole cast at _BASE + a source with a one-line upstream fix to combat."""
    cast, source = tmp_path / "cast", tmp_path / "src"
    _poured_cast(cast, _BASE, commit=commit, strategy=strategy)
    _engine_tree(source, _BUMPED)
    return cast, source


def test_update_applies_the_fix_and_bumps_the_pin(tmp_path: Path) -> None:
    cast, source = _whole_cast_with_upstream_fix(tmp_path)
    outcome = update_cast(
        cast,
        source,
        validator=_OK,
        resolve_commit=lambda r: "bbb222",
        commit_present=lambda r, c: True,
        read_at_commit=_pin_reader(_BASE),  # pin == cast content -> no local edits
    )
    assert outcome.applied and "updated and revalidated" in outcome.reason
    assert outcome.from_commit == "aaa111" and outcome.to_commit == "bbb222"
    assert (cast / _COMBAT).read_text() == "def hit():\n    return 2\n"  # carries the source now
    assert read_manifest(cast / "cast_manifest.json").codeforge_commit == "bbb222"  # pin advanced


def test_update_refuses_a_selective_cast_without_recorded_surfaces(tmp_path: Path) -> None:
    # a selective cast poured before surface-recording can't have its closure recomputed -> refuse
    cast, source = _whole_cast_with_upstream_fix(tmp_path, strategy="vendored-selective")
    outcome = update_cast(
        cast,
        source,
        validator=_OK,
        resolve_commit=lambda r: "bbb222",
        commit_present=lambda r, c: True,
        read_at_commit=_pin_reader(_BASE),
    )
    assert not outcome.applied and "no recorded surfaces" in outcome.reason
    assert (cast / _COMBAT).read_text() == "def hit():\n    return 1\n"  # untouched


def test_update_applies_to_a_selective_cast_with_recorded_surfaces(tmp_path: Path) -> None:
    # a selective cast WITH surfaces: recompute the closure, re-vendor only it, re-validate
    cast, source = tmp_path / "cast", tmp_path / "src"
    _poured_cast(
        cast, _BASE, commit="aaa111", strategy="vendored-selective", surfaces=["solo", "save"]
    )
    _engine_tree(source, _BUMPED)
    seen = {}

    def _closure(surfaces):
        seen["surfaces"] = surfaces
        return {"world"}  # the recomputed closure carries the world subpackage

    outcome = update_cast(
        cast,
        source,
        validator=_OK,
        closure_fn=_closure,
        resolve_commit=lambda r: "bbb222",
        commit_present=lambda r, c: True,
        read_at_commit=_pin_reader(_BASE),
    )
    assert outcome.applied and seen["surfaces"] == [
        "solo",
        "save",
    ]  # the recorded surfaces drove it
    assert (cast / _COMBAT).read_text() == "def hit():\n    return 2\n"  # re-vendored from source
    assert read_manifest(cast / "cast_manifest.json").codeforge_commit == "bbb222"


def test_update_refuses_local_edits_without_force(tmp_path: Path) -> None:
    cast, source = tmp_path / "cast", tmp_path / "src"
    edited = {**_BASE, _COMBAT: "def hit():\n    return 999  # owner\n"}
    _poured_cast(cast, edited, commit="aaa111", strategy="vendored-whole")
    _engine_tree(source, _BUMPED)
    outcome = update_cast(
        cast,
        source,
        validator=_OK,
        resolve_commit=lambda r: "bbb222",
        commit_present=lambda r, c: True,
        read_at_commit=_pin_reader(_BASE),  # pin != cast -> a local edit
    )
    assert not outcome.applied and "local edit" in outcome.reason
    assert (cast / _COMBAT).read_text() == "def hit():\n    return 999  # owner\n"  # not clobbered


def test_force_overrides_local_edits(tmp_path: Path) -> None:
    cast, source = tmp_path / "cast", tmp_path / "src"
    edited = {**_BASE, _COMBAT: "def hit():\n    return 999  # owner\n"}
    _poured_cast(cast, edited, commit="aaa111", strategy="vendored-whole")
    _engine_tree(source, _BUMPED)
    outcome = update_cast(
        cast,
        source,
        force=True,
        validator=_OK,
        resolve_commit=lambda r: "bbb222",
        commit_present=lambda r, c: True,
        read_at_commit=_pin_reader(_BASE),
    )
    assert outcome.applied
    assert (cast / _COMBAT).read_text() == "def hit():\n    return 2\n"  # force clobbered the edit


def test_update_refuses_an_unverifiable_pin_without_force(tmp_path: Path) -> None:
    cast, source = _whole_cast_with_upstream_fix(tmp_path, commit="deadbee")
    outcome = update_cast(
        cast,
        source,
        validator=_OK,
        resolve_commit=lambda r: "bbb222",
        commit_present=lambda r, c: False,  # pin not in the source
        read_at_commit=_raise_oserror,
    )
    assert not outcome.applied and "cannot verify" in outcome.reason


def test_update_noop_when_already_in_sync(tmp_path: Path) -> None:
    cast, source = tmp_path / "cast", tmp_path / "src"
    _poured_cast(cast, _BASE, commit="aaa111", strategy="vendored-whole")
    _engine_tree(source, _BASE)
    outcome = update_cast(
        cast,
        source,
        validator=_OK,
        resolve_commit=lambda r: "aaa111",
        commit_present=lambda r, c: True,
        read_at_commit=_pin_reader(_BASE),
    )
    assert not outcome.applied and "already in sync" in outcome.reason


def test_update_rolls_back_when_validation_fails(tmp_path: Path) -> None:
    cast, source = _whole_cast_with_upstream_fix(tmp_path)
    outcome = update_cast(
        cast,
        source,
        validator=lambda cd: (False, "a command raised"),
        resolve_commit=lambda r: "bbb222",
        commit_present=lambda r, c: True,
        read_at_commit=_pin_reader(_BASE),
    )
    assert not outcome.applied and outcome.rolled_back and "rolled back" in outcome.reason
    assert (cast / _COMBAT).read_text() == "def hit():\n    return 1\n"  # restored
    assert read_manifest(cast / "cast_manifest.json").codeforge_commit == "aaa111"  # pin unchanged


def test_update_can_skip_validation(tmp_path: Path) -> None:
    cast, source = _whole_cast_with_upstream_fix(tmp_path)
    outcome = update_cast(
        cast,
        source,
        validate=False,
        resolve_commit=lambda r: "bbb222",
        commit_present=lambda r, c: True,
        read_at_commit=_pin_reader(_BASE),
    )
    assert outcome.applied and not outcome.validated and "validation skipped" in outcome.reason


def test_update_rolls_back_and_raises_on_an_unexpected_error(tmp_path: Path) -> None:
    cast, source = _whole_cast_with_upstream_fix(tmp_path)

    def _boom_validator(cd):
        raise RuntimeError("kaboom")

    with pytest.raises(CastError, match="rolled back"):
        update_cast(
            cast,
            source,
            validator=_boom_validator,
            resolve_commit=lambda r: "bbb222",
            commit_present=lambda r, c: True,
            read_at_commit=_pin_reader(_BASE),
        )
    assert (cast / _COMBAT).read_text() == "def hit():\n    return 1\n"  # restored after the crash


def test_update_default_validator_delegates_to_validate_cast(tmp_path: Path, monkeypatch) -> None:
    # validator=None uses _default_validator, which boots the cast via parts.cast.validate_cast
    import parts.cast_update as cu

    monkeypatch.setattr(cu, "validate_cast", lambda cd: (True, "delegated"))
    cast, source = _whole_cast_with_upstream_fix(tmp_path)
    outcome = update_cast(
        cast,
        source,
        validator=None,
        resolve_commit=lambda r: "bbb222",
        commit_present=lambda r, c: True,
        read_at_commit=_pin_reader(_BASE),
    )
    assert outcome.applied  # the default validator path ran and passed


def test_restore_engine_when_the_cast_has_no_parts(tmp_path: Path) -> None:
    backup = tmp_path / "backup"
    (backup / "parts").mkdir(parents=True)
    (backup / "parts" / "x.py").write_text("X = 1\n")
    (backup / "forge.py").write_text("f\n")
    cast = tmp_path / "cast"
    cast.mkdir()  # no parts/ yet -> the exists() guard is False
    _restore_engine(cast, backup)
    assert (cast / "parts" / "x.py").read_text() == "X = 1\n" and (
        cast / "forge.py"
    ).read_text() == "f\n"


def test_render_update_heads_and_rollback_line() -> None:
    applied = UpdateOutcome(True, "engine updated and revalidated", "a", "b", 5, True)
    assert "UPDATED" in render_update(applied) and "commit the update yourself" in render_update(
        applied
    )
    noop = UpdateOutcome(False, "already in sync with the target; nothing to update", "a", "a")
    assert "NO-OP" in render_update(noop)
    refused = UpdateOutcome(False, "2 local edit(s) would be overwritten; ...", "a", "b")
    assert "REFUSED" in render_update(refused)
    rolled = UpdateOutcome(
        False, "update failed validation, rolled back: boom", "a", "b", rolled_back=True
    )
    assert "rolled back" in render_update(rolled) and "restored" in render_update(rolled)


def test_cli_update_applies_and_returns_zero(tmp_path, capsys, monkeypatch) -> None:
    import parts.cast_update as cu

    monkeypatch.setattr(
        cu,
        "update_cast",
        lambda c, s, **k: UpdateOutcome(True, "engine updated and revalidated", "a", "b", 5, True),
    )
    assert main(["update", "somecast", "somesrc"]) == 0
    assert "UPDATED" in capsys.readouterr().out


def test_cli_update_refusal_returns_nonzero(tmp_path, capsys, monkeypatch) -> None:
    import parts.cast_update as cu

    monkeypatch.setattr(
        cu, "update_cast", lambda c, s, **k: UpdateOutcome(False, "3 local edit(s) ...", "a", "b")
    )
    assert main(["update", "d", "s"]) == 1  # a safety refusal signals "action needed"
    assert "REFUSED" in capsys.readouterr().out


def test_cli_update_usage_error(capsys) -> None:
    assert main(["update"]) == 2
    assert "usage" in capsys.readouterr().err


def test_cli_update_reports_a_cast_error(capsys, monkeypatch) -> None:
    import parts.cast_update as cu

    def _raise(c, s, **k):
        raise CastError("boom")

    monkeypatch.setattr(cu, "update_cast", _raise)
    assert main(["update", "d", "s"]) == 2
    assert "cast: boom" in capsys.readouterr().err


def test_selective_validator_drives_the_surface_corpus(monkeypatch) -> None:
    # the default selective validator boots the cast with the surfaces' commands + server imports
    import parts.cast_update as cu
    from parts import coupling

    calls: dict[str, list[str]] = {}
    monkeypatch.setattr(coupling, "surface_commands", lambda s: ["look"])
    monkeypatch.setattr(coupling, "surface_imports", lambda s: ["parts.gateway"])

    def _fake_validate(cd, *, commands, imports):
        calls["commands"], calls["imports"] = commands, imports
        return (True, "ran clean")

    monkeypatch.setattr(cu, "validate_cast", _fake_validate)
    ok, detail = cu._selective_validator(["solo"])(Path("/nonexistent"))
    assert ok and calls["commands"] == ["look"] and calls["imports"] == ["parts.gateway"]


def test_update_noop_for_a_current_selective_cast(tmp_path: Path) -> None:
    # a selective cast that only "lacks" its shed modules is in sync -> a no-op, not a re-vendor
    cast, source = tmp_path / "cast", tmp_path / "src"
    _poured_cast(cast, _BASE, commit="aaa111", strategy="vendored-selective", surfaces=["solo"])
    fuller = {**_BASE, "parts/pm.py": "# a shed dev-tool the source still has\n"}
    _engine_tree(source, fuller)
    outcome = update_cast(
        cast,
        source,
        validator=_OK,
        closure_fn=lambda s: {"world"},
        resolve_commit=lambda r: "aaa111",
        commit_present=lambda r, c: True,
        read_at_commit=_pin_reader(fuller),  # pm existed at the pin -> shed (expected), not new
    )
    assert not outcome.applied and "already in sync" in outcome.reason
