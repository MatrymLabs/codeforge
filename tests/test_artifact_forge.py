"""Test twin for parts/artifact_forge.py: the portfolio-artifact scaffold generator.

Acceptance AND refusal cases. Everything materializes into a tmp dir, so no test writes into the
repo. Hostile cases: an unsafe slug, an unknown kind, a path-traversal key, and a refused overwrite
that must leave the destination untouched.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from parts import artifact_forge as af

# --- Planning (pure, no filesystem) ----------------------------------------------------------


def test_plan_produces_the_documented_skeleton() -> None:
    plan = af.plan_scaffold("job-tracker", "service", description="Track applications")
    keys = set(plan.files)
    for expected in (
        "README.md",
        "docs/design-doc.md",
        "docs/api-spec.md",
        "docs/test-plan.md",
        "docs/adr/0001-record-architecture-decisions.md",
        "docs/adr/TEMPLATE.md",
        ".github/workflows/ci.yml",
        "docker-compose.yml",
        ".env.example",
        ".gitignore",
        "CHANGELOG.md",
    ):
        assert expected in keys, f"missing {expected}"


def test_readme_leads_with_the_case_study_convention() -> None:
    readme = af.plan_scaffold("job-tracker").files["README.md"]
    # The PDF's README convention: live demo first, then problem, decisions, stack, testing.
    assert "Live demo" in readme
    assert "## Problem" in readme
    assert "## Key decisions and trade-offs" in readme
    assert "## Testing" in readme
    assert "Track applications" not in readme  # no description given -> placeholder


def test_description_is_embedded_when_given() -> None:
    readme = af.plan_scaffold("job-tracker", description="Track applications").files["README.md"]
    assert "Track applications" in readme


def test_full_stack_kind_adds_frontend_and_backend() -> None:
    files = af.plan_scaffold("shop", "full-stack").files
    assert "frontend/README.md" in files
    assert "backend/README.md" in files
    assert "docker-compose.yml" in files


def test_cli_kind_is_lean() -> None:
    files = af.plan_scaffold("flashcards", "cli").files
    assert "docker-compose.yml" not in files  # a CLI needs no compose
    assert "frontend/README.md" not in files
    assert "Command reference" in files["docs/api-spec.md"]  # api spec becomes a command reference


def test_generated_yaml_files_parse() -> None:
    files = af.plan_scaffold("svc", "service").files
    # A scaffolded CI workflow and compose file must be valid YAML, not broken boilerplate.
    ci = yaml.safe_load(files[".github/workflows/ci.yml"])
    assert "jobs" in ci and "check" in ci["jobs"]
    compose = yaml.safe_load(files["docker-compose.yml"])
    assert "services" in compose and "app" in compose["services"]


def test_env_example_has_no_real_secret_value() -> None:
    env = af.plan_scaffold("svc").files[".env.example"]
    # Variable names + comments only; the values are blank placeholders (nothing to leak).
    for line in env.splitlines():
        if line.startswith("POSTGRES_PASSWORD") or line.startswith("SECRET_KEY"):
            assert line.split("=", 1)[1].strip() == ""


# --- Materializing (filesystem, into tmp) ----------------------------------------------------


def test_materialize_writes_every_file(tmp_path: Path) -> None:
    plan = af.plan_scaffold("job-tracker")
    written = af.materialize(plan, tmp_path)
    assert len(written) == len(plan.files)
    for rel in plan.files:
        assert (tmp_path / rel).is_file()
    # The ADR lives in a nested dir that the generator created.
    assert (tmp_path / "docs" / "adr" / "0001-record-architecture-decisions.md").is_file()


def test_materialize_refuses_overwrite_and_leaves_dest_untouched(tmp_path: Path) -> None:
    plan = af.plan_scaffold("svc")
    af.materialize(plan, tmp_path)
    (tmp_path / "README.md").write_text("MY EDITS", encoding="utf-8")
    with pytest.raises(af.ScaffoldError):
        af.materialize(plan, tmp_path)  # a second run must not clobber
    assert (tmp_path / "README.md").read_text(encoding="utf-8") == "MY EDITS"


def test_overwrite_flag_allows_regeneration(tmp_path: Path) -> None:
    plan = af.plan_scaffold("svc")
    af.materialize(plan, tmp_path)
    (tmp_path / "README.md").write_text("stale", encoding="utf-8")
    af.materialize(plan, tmp_path, overwrite=True)
    assert "stale" not in (tmp_path / "README.md").read_text(encoding="utf-8")


# --- Refusal ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad", ["", "Has Space", "UPPER", "-leading", "../escape", "a/b", "x" * 65]
)
def test_unsafe_name_refused(bad: str) -> None:
    with pytest.raises(af.ScaffoldError):
        af.plan_scaffold(bad)


def test_unknown_kind_refused() -> None:
    with pytest.raises(af.ScaffoldError):
        af.plan_scaffold("svc", "mainframe")


def test_path_traversal_key_refused(tmp_path: Path) -> None:
    evil = af.ScaffoldPlan(name="x", kind="service", files={"../escape.txt": "pwned"})
    with pytest.raises(af.ScaffoldError):
        af.materialize(evil, tmp_path)
    assert not (tmp_path.parent / "escape.txt").exists()


# --- ADR numbering ---------------------------------------------------------------------------


def test_next_adr_number_on_empty_or_missing(tmp_path: Path) -> None:
    assert af.next_adr_number(tmp_path / "nope") == 1  # missing dir
    (tmp_path).mkdir(exist_ok=True)
    assert af.next_adr_number(tmp_path) == 1  # empty dir


def test_next_adr_number_increments(tmp_path: Path) -> None:
    for n in ("0001-a.md", "0002-b.md", "0007-c.md"):
        (tmp_path / n).write_text("x", encoding="utf-8")
    (tmp_path / "TEMPLATE.md").write_text("x", encoding="utf-8")  # must be ignored
    assert af.next_adr_number(tmp_path) == 8


# --- CLI -------------------------------------------------------------------------------------


def test_main_usage_on_no_args(capsys: pytest.CaptureFixture[str]) -> None:
    assert af.main([]) == 2
    assert "usage" in capsys.readouterr().out


def test_main_refuses_bad_name() -> None:
    assert af.main(["Bad Name"]) == 2


def test_main_writes_to_a_redirected_dest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(af, "_default_dest", lambda name: tmp_path / name)
    assert af.main(["job-tracker", "service"]) == 0
    assert (tmp_path / "job-tracker" / "README.md").is_file()
