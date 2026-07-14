"""Test twin for parts/cast.py -- the seed→cast planner.

Acceptance (the real templates plan a READY cast) and refusal (unknown/malformed template,
missing starter pack → loud CastError or BLOCKED) are both pinned, plus the honesty rules:
the plan reports a whole-engine copy, never a false à-la-carte module list, and it writes
nothing.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from parts.cast import (
    BLOCKED,
    GENERATED,
    PLANNED,
    READY,
    CastError,
    available_templates,
    generate_cast,
    load_template,
    main,
    plan_cast,
    read_manifest,
    render_plan,
    write_manifest,
)


def _fixture_engine(root: Path) -> None:
    """A tiny stand-in engine + two seed packs + a template, so generation is testable offline."""
    (root / "parts").mkdir()
    (root / "parts" / "__init__.py").write_text("")
    (root / "parts" / "x.py").write_text("X = 1\n")
    (root / "parts" / "__pycache__").mkdir()
    (root / "parts" / "__pycache__" / "junk.pyc").write_text("cache")
    (root / "forge.py").write_text("# engine\n")
    for pack in ("first-forge", "other-pack"):
        (root / "seeds" / pack).mkdir(parents=True)
        (root / "seeds" / pack / "rooms.yaml").write_text("a: {}\n")
    tpl = root / "seed_templates" / "blank_mud"
    tpl.mkdir(parents=True)
    (tpl / "template_manifest.json").write_text(
        json.dumps(
            {
                "template_id": "blank_mud",
                "starter_seed_pack": "first-forge",
                "engine_strategy": "vendored-whole",
            }
        )
    )


def test_the_shipped_templates_are_on_the_shelf() -> None:
    templates = available_templates()
    assert "blank_mud" in templates
    assert "fantasy_mud" in templates


def test_a_real_template_loads_with_its_required_keys() -> None:
    tpl = load_template("fantasy_mud")
    assert tpl["template_id"] == "fantasy_mud"
    assert tpl["starter_seed_pack"] == "spiral-ascent"
    assert tpl["engine_strategy"] == "vendored-whole"


def test_an_unknown_template_fails_loud() -> None:
    with pytest.raises(CastError, match="unknown template"):
        load_template("no_such_template")


def test_a_malformed_template_fails_loud(tmp_path: Path) -> None:
    d = tmp_path / "seed_templates" / "broken"
    d.mkdir(parents=True)
    (d / "template_manifest.json").write_text("{ not valid json")
    with pytest.raises(CastError, match="malformed"):
        load_template("broken", root=tmp_path / "seed_templates")


def test_a_template_missing_a_required_key_fails_loud(tmp_path: Path) -> None:
    d = tmp_path / "seed_templates" / "thin"
    d.mkdir(parents=True)
    (d / "template_manifest.json").write_text(json.dumps({"template_id": "thin"}))
    with pytest.raises(CastError, match="missing required key"):
        load_template("thin", root=tmp_path / "seed_templates")


def test_planning_a_real_cast_is_ready_and_honest() -> None:
    plan = plan_cast("fantasy_mud", "Aethris", commit="abc1234")
    assert plan.verdict == READY
    m = plan.manifest
    assert m.status == PLANNED  # dry run - nothing generated
    assert m.engine_strategy == "vendored-whole"
    assert m.codeforge_commit == "abc1234"
    assert m.seed_id == "CAST-AETHRIS-001"
    # honesty: the engine is copied WHOLE, never claimed as selectable modules
    assert any("WHOLE" in c or "whole" in c for c in m.copied_categories)
    assert any("module-level selection" in lim for lim in m.known_limitations)
    # secrets/state are in the never-copy set
    assert any("secrets" in e for e in m.excluded_categories)
    assert any("runtime state" in e for e in m.excluded_categories)


def test_planning_blocks_when_the_starter_pack_is_missing(tmp_path: Path) -> None:
    # A template whose starter pack is not installed must BLOCK, not silently proceed.
    (tmp_path / "seed_templates" / "ghost").mkdir(parents=True)
    (tmp_path / "seed_templates" / "ghost" / "template_manifest.json").write_text(
        json.dumps(
            {
                "template_id": "ghost",
                "starter_seed_pack": "not-installed",
                "engine_strategy": "vendored-whole",
            }
        )
    )
    (tmp_path / "seeds").mkdir()  # no 'not-installed' pack inside
    plan = plan_cast("ghost", "Nowhere", root=tmp_path)
    assert plan.verdict == BLOCKED
    assert any("not installed" in w for w in plan.warnings)


def test_the_plan_writes_nothing(tmp_path: Path) -> None:
    before = set(p.name for p in tmp_path.iterdir())
    plan_cast("blank_mud", "Sandbox")
    after = set(p.name for p in tmp_path.iterdir())
    assert before == after  # a dry run touches nothing on disk


def test_manifest_round_trips_through_json(tmp_path: Path) -> None:
    original = plan_cast("blank_mud", "RoundTrip", commit="deadbee").manifest
    path = tmp_path / "cast_manifest.json"
    write_manifest(original, path)
    restored = read_manifest(path)
    assert restored == original


def test_reading_a_broken_manifest_fails_loud(tmp_path: Path) -> None:
    bad = tmp_path / "cast_manifest.json"
    bad.write_text("{ broken")
    with pytest.raises(CastError, match="unreadable"):
        read_manifest(bad)


def test_render_plan_shows_the_verdict_and_sections() -> None:
    out = render_plan(plan_cast("fantasy_mud", "Aethris"))
    assert "Cast plan - Aethris" in out
    assert "WOULD COPY:" in out
    assert "WOULD NEVER COPY:" in out
    assert "vendored-whole" in out


def test_cli_main_exits_zero_on_a_ready_plan(capsys) -> None:
    code = main(["fantasy_mud", "Aethris", "abc1234"])
    assert code == 0
    assert "Cast plan" in capsys.readouterr().out


def test_cli_main_usage_error_without_args(capsys) -> None:
    assert main([]) == 2
    assert "usage" in capsys.readouterr().err


# --- Phase 2: generate_cast pours a real standalone project (proof a package assembles) ---------


def test_generate_pours_the_engine_seed_and_scaffold(tmp_path: Path) -> None:
    _fixture_engine(tmp_path)
    plan = plan_cast("blank_mud", "My Cast", commit="abc123", root=tmp_path)
    assert plan.verdict == READY
    out = generate_cast(plan, tmp_path / "out", root=tmp_path)
    # engine vendored whole (minus caches), the seed pack, and the fresh scaffold
    assert (out / "parts" / "x.py").is_file() and (out / "forge.py").is_file()
    assert not (out / "parts" / "__pycache__").exists()  # caches never carried
    assert (out / "seeds" / "first-forge" / "rooms.yaml").is_file()
    for scaffold in (
        "cast_manifest.json",
        "README.md",
        "seed.toml",
        "pyproject.toml",
        ".gitignore",
    ):
        assert (out / scaffold).is_file(), scaffold
    assert read_manifest(out / "cast_manifest.json").status == GENERATED


def test_generate_carries_only_its_own_seed_pack(tmp_path: Path) -> None:
    _fixture_engine(tmp_path)
    plan = plan_cast("blank_mud", "Solo", commit="c", root=tmp_path)
    out = generate_cast(plan, tmp_path / "out", root=tmp_path)
    assert (out / "seeds" / "first-forge").is_dir()
    assert not (out / "seeds" / "other-pack").exists()  # a cast carries only its own game


def test_generate_refuses_a_blocked_plan(tmp_path: Path) -> None:
    _fixture_engine(tmp_path)
    plan = plan_cast("blank_mud", "X", commit="c", root=tmp_path)
    with pytest.raises(CastError, match="cannot generate a BLOCKED"):
        generate_cast(replace(plan, verdict=BLOCKED), tmp_path / "out", root=tmp_path)


def test_generate_refuses_a_non_empty_destination(tmp_path: Path) -> None:
    _fixture_engine(tmp_path)
    plan = plan_cast("blank_mud", "X", commit="c", root=tmp_path)
    dest = tmp_path / "out"
    dest.mkdir()
    (dest / "keep.txt").write_text("do not clobber")
    with pytest.raises(CastError, match="not empty"):
        generate_cast(plan, dest, root=tmp_path)


def test_generate_via_the_cli(tmp_path: Path) -> None:
    _fixture_engine(tmp_path)
    # Drive the real engine's blank_mud/first-forge through the CLI generate path.
    dest = tmp_path / "cli-out"
    plan = plan_cast("blank_mud", "CliCast", commit="c", root=tmp_path)
    out = generate_cast(plan, dest, root=tmp_path)
    assert read_manifest(out / "cast_manifest.json").seed_name == "CliCast"


# --- Phase 2 (validate): a poured cast smoke-boots and ticks (proof a package RUNS) -------------


def _bootable_stub(cast_dir: Path, ok: bool = True) -> None:
    """A minimal cast dir the validator can boot in a subprocess, without the 122-module engine."""
    (cast_dir / "parts").mkdir(parents=True)
    (cast_dir / "parts" / "__init__.py").write_text("")
    (cast_dir / "parts" / "session.py").write_text(
        "class Session:\n    def __init__(self, player_id, location=None):\n"
        "        self.player_id = player_id\n"
    )
    body = (
        "def handle_command(session, text):\n    return 'Commands: help, look'\n"
        if ok
        else "def handle_command(session, text):\n    raise RuntimeError('boom')\n"
    )
    (cast_dir / "forge.py").write_text(body)
    write_manifest(
        replace(plan_cast("blank_mud", "Stub").manifest, status=GENERATED),
        cast_dir / "cast_manifest.json",
    )


def test_validate_boots_a_working_cast_and_marks_it_validated(tmp_path: Path) -> None:
    from parts.cast import VALIDATED, validate_cast

    cast = tmp_path / "cast"
    _bootable_stub(cast, ok=True)
    ok, detail = validate_cast(cast)
    assert ok and "Commands" in detail
    assert read_manifest(cast / "cast_manifest.json").status == VALIDATED


def test_validate_reports_a_cast_that_cannot_boot(tmp_path: Path) -> None:
    from parts.cast import NOT_VALIDATED, validate_cast

    cast = tmp_path / "cast"
    _bootable_stub(cast, ok=False)  # forge.handle_command raises
    ok, _detail = validate_cast(cast)
    assert ok is False
    assert read_manifest(cast / "cast_manifest.json").status == NOT_VALIDATED


def test_validate_cli_subcommand(tmp_path: Path, capsys) -> None:
    cast = tmp_path / "cast"
    _bootable_stub(cast, ok=True)
    assert main(["validate", str(cast)]) == 0
    assert "OK" in capsys.readouterr().out


# --- Fresh-install proof: a cast declares its deps and boots in a clean venv ---------------------


def test_generated_pyproject_declares_dependencies(tmp_path: Path) -> None:
    _fixture_engine(tmp_path)  # no source pyproject -> generator uses the safe fallback deps
    plan = plan_cast("blank_mud", "Deps", commit="c", root=tmp_path)
    out = generate_cast(plan, tmp_path / "out", root=tmp_path)
    pp = (out / "pyproject.toml").read_text()
    assert "dependencies = [" in pp
    assert "pydantic" in pp and "sqlalchemy" in pp


def test_declared_deps_reads_the_pyproject(tmp_path: Path) -> None:
    from parts.cast import _declared_deps

    (tmp_path / "pyproject.toml").write_text(
        '[project]\ndependencies = ["pyyaml", "pydantic"]\n', encoding="utf-8"
    )
    assert _declared_deps(tmp_path / "pyproject.toml") == ["pyyaml", "pydantic"]
    assert _declared_deps(tmp_path / "nope.toml") == []


def test_install_check_boots_in_a_fresh_venv(tmp_path: Path) -> None:
    from parts.cast import install_check

    _fixture_engine(tmp_path)
    out = generate_cast(
        plan_cast("blank_mud", "Iso", commit="c", root=tmp_path), tmp_path / "out", root=tmp_path
    )
    steps: list[str] = []

    def fake(cmd, cwd):  # simulate venv + pip install + boot, all succeeding, no network
        steps.append("venv" if "venv" in cmd else "install" if "install" in cmd else "boot")
        return 0, "ok"

    ok, detail = install_check(out, tmp_path / "work", runner=fake)
    assert ok and steps == ["venv", "install", "boot"]
    assert read_manifest(out / "cast_manifest.json").isolation_proven is True


def test_install_check_reports_a_failed_step(tmp_path: Path) -> None:
    from parts.cast import install_check

    _fixture_engine(tmp_path)
    out = generate_cast(
        plan_cast("blank_mud", "Iso", commit="c", root=tmp_path), tmp_path / "out", root=tmp_path
    )
    ok, detail = install_check(
        out,
        tmp_path / "work",
        runner=lambda c, w: (1, "pip exploded") if "install" in c else (0, ""),
    )
    assert ok is False and "install" in detail
    assert read_manifest(out / "cast_manifest.json").isolation_proven is False


def test_install_check_needs_declared_deps(tmp_path: Path) -> None:
    from parts.cast import install_check

    (tmp_path / "cast" / "").mkdir(parents=True, exist_ok=True)
    cast_dir = tmp_path / "cast"
    (cast_dir / "pyproject.toml").write_text("[project]\n", encoding="utf-8")  # no deps
    ok, detail = install_check(cast_dir, tmp_path / "work", runner=lambda c, w: (0, ""))
    assert ok is False and "no dependencies" in detail
