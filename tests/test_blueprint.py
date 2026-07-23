"""Test twin for parts/blueprint.py -- the Blueprint model, validator, files, and tick verb.

Acceptance: a well-formed spec loads, round-trips through JSON, renders Markdown, and files
its twins; the `blueprint` verb browses and reads plans and is reachable through the engine
tick. Refusal (hostile cases): bad id, missing intent, empty requirement, wrong-typed stack,
and an unknown status all fail loud with a named error.
"""

import json

import pytest

from forge import handle_command
from parts.blueprint import (
    Blueprint,
    BlueprintError,
    blueprint,
    from_dict,
    load_all,
    load_blueprint,
    to_dict,
    to_markdown,
    write_blueprint,
)
from parts.world.session import Session

_GOOD = {
    "blueprint_id": "sample_plan",
    "title": "A Sample Plan",
    "intent": "Prove the Blueprint spine end to end.",
    "requirements": ["It must validate loudly.", "It must render to HTML."],
    "security": ["Threat model: untrusted input at the gate.", "Trust boundary: the loader."],
    "tasks": ["Write the model.", "Write the renderer."],
    "stack": {"engine": "custom Python", "tests": "pytest"},
    "status": "draft",
}


# --- acceptance -------------------------------------------------------------


def test_a_good_spec_validates_and_round_trips():
    bp = from_dict(_GOOD)
    assert isinstance(bp, Blueprint)
    assert bp.blueprint_id == "sample_plan"
    assert bp.requirements == ("It must validate loudly.", "It must render to HTML.")
    # JSON round-trip is lossless.
    assert from_dict(to_dict(bp)) == bp


def test_markdown_shows_the_plan():
    md = to_markdown(from_dict(_GOOD))
    assert "# A Sample Plan" in md
    assert "1. It must validate loudly." in md
    assert "- [ ] Write the model." in md


def test_tasks_and_stack_are_optional():
    lean = {
        "blueprint_id": "lean",
        "title": "Lean",
        "intent": "min",
        "requirements": ["one"],
        "security": ["threat model: none of note; local-only, no untrusted input"],
    }
    bp = from_dict(lean)
    assert bp.tasks == ()
    assert bp.stack == ()


def test_security_is_required_and_shows_in_markdown():
    bp = from_dict(_GOOD)
    assert bp.security == (
        "Threat model: untrusted input at the gate.",
        "Trust boundary: the loader.",
    )
    md = to_markdown(bp)
    assert "## Security" in md
    assert "- Threat model: untrusted input at the gate." in md
    assert from_dict(to_dict(bp)) == bp  # security round-trips through JSON


def test_write_files_the_json_and_markdown_twins(tmp_path):
    bp = from_dict(_GOOD)
    json_path, md_path = write_blueprint(bp, root=tmp_path)
    assert json_path.exists() and md_path.exists()
    assert json.loads(json_path.read_text())["blueprint_id"] == "sample_plan"
    assert "# A Sample Plan" in md_path.read_text()
    # It reloads through the gate unchanged.
    assert load_blueprint(json_path) == bp


def test_load_all_finds_nested_examples(tmp_path):
    (tmp_path / "blueprints" / "examples").mkdir(parents=True)
    (tmp_path / "blueprints" / "examples" / "x.json").write_text(
        json.dumps({**_GOOD, "blueprint_id": "nested"})
    )
    ids = [b.blueprint_id for b in load_all(root=tmp_path)]
    assert ids == ["nested"]


def test_shipped_example_is_valid():
    # The repo's own example must always pass the gate (VeritasGate on our own artifact).
    ids = [b.blueprint_id for b in load_all()]
    assert "npc_combat" in ids


# --- refusal: hostile cases fail loud ---------------------------------------


@pytest.mark.parametrize(
    "mutation, needle",
    [
        ({"blueprint_id": "Bad-Id"}, "snake_case"),
        ({"blueprint_id": "9lives"}, "snake_case"),
        ({"title": ""}, "title"),
        ({"intent": "   "}, "intent"),
        ({"requirements": []}, "at least one requirement"),
        ({"requirements": ["ok", ""]}, "requirements[1]"),
        ({"requirements": "not a list"}, "must be a list"),
        ({"security": []}, "security"),
        ({"security": ["ok", "  "]}, "security[1]"),
        ({"security": "not a list"}, "must be a list"),
        ({"stack": ["not", "a", "map"]}, "stack"),
        ({"status": "shipped"}, "status must be one of"),
    ],
)
def test_bad_specs_fail_loud(mutation, needle):
    raw = {**_GOOD, **mutation}
    with pytest.raises(BlueprintError) as err:
        from_dict(raw)
    assert needle in str(err.value)


def test_unreadable_file_fails_loud(tmp_path):
    bad = tmp_path / "broken.json"
    bad.write_text("{ not json")
    with pytest.raises(BlueprintError):
        load_blueprint(bad)


# --- the tick verb ----------------------------------------------------------


def test_blueprint_list_reads_the_examples():
    out = blueprint("list")
    assert "npc_combat" in out
    assert "NPCs that fight back" in out


def test_blueprint_show_renders_markdown():
    out = blueprint("show npc_combat")
    assert out.startswith("# NPCs that fight back")


def test_blueprint_show_missing_is_honest():
    assert "No blueprint filed as 'ghost'" in blueprint("show ghost")


def test_blueprint_render_files_html(tmp_path):
    (tmp_path / "blueprints").mkdir()
    (tmp_path / "blueprints" / "sample_plan.json").write_text(json.dumps(_GOOD))
    out = blueprint("render sample_plan", root=tmp_path)
    rendered = tmp_path / "reports" / "blueprints" / "sample_plan.html"
    assert rendered.exists()
    assert str(rendered) in out


def test_unknown_action_is_honest():
    assert "Unknown blueprint action" in blueprint("frobnicate")


# --- reachable through the engine tick (a feature isn't wired until this passes) ---


def test_blueprint_is_reachable_through_the_tick():
    session = Session(player_id="_bp")
    out = handle_command(session, "blueprint list")
    assert "npc_combat" in out
