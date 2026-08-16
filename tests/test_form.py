"""Test twin for kernel/seedlab/form.py -- the Engineering Form.

Acceptance: one domain-neutral engine turns intent into a validated, machine-readable BlueprintSpec
for
different product types from DATA alone -- an MMORPG spec selects the game module, an education spec
selects the education module. The Form is adaptive (a conditional question appears only when its
trigger is answered). New product types are data (proven by loading the shipped catalog).

Refusal (fail loud, never coerce a lie): an unknown product type, a missing required answer, an
out-of-range choice, and an answer to a question outside the chosen product type are all refused.
Grammar before worlds, enforced by construction: a classroom spec NEVER carries the game module.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kernel.seedlab.form import (
    EngineeringForm,
    FormDefinition,
    FormError,
    Question,
)

# A tiny in-code catalog so the unit tests don't depend on the shipped data file. It mirrors the
# real catalog's shape: common questions, a game branch with a conditional, and an education branch.
_CATALOG = {
    "schema": 1,
    "common_question_ids": ["name", "owner", "purpose"],
    "questions": {
        "name": {"prompt": "Name?", "kind": "text"},
        "owner": {"prompt": "Owner?", "kind": "text"},
        "purpose": {"prompt": "Purpose?", "kind": "text"},
        "combat": {"prompt": "Combat?", "kind": "bool"},
        "pvp": {
            "prompt": "PvP?",
            "kind": "choice",
            "choices": ["none", "open"],
            "applies_when": {"combat": True},
        },
        "roles": {"prompt": "Roles?", "kind": "multi", "choices": ["teacher", "parent", "student"]},
    },
    "product_types": {
        "mmorpg": {"name": "MMORPG", "question_ids": ["combat", "pvp"], "domain_modules": ["game"]},
        "education": {
            "name": "Education",
            "question_ids": ["roles"],
            "domain_modules": ["education"],
        },
    },
}


def _form() -> EngineeringForm:
    return EngineeringForm(FormDefinition.from_dict(_CATALOG))


# --- acceptance --------------------------------------------------------------------------------


def test_the_same_engine_builds_a_game_spec_and_selects_the_game_module() -> None:
    spec = _form().build_spec(
        "mmorpg",
        {"name": "Aethryn", "owner": "josh", "purpose": "a world", "combat": True, "pvp": "open"},
    )
    assert spec.product_type == "mmorpg"
    assert spec.name == "Aethryn" and spec.owner == "josh"
    assert spec.domain_modules == ("game",)
    assert spec.answers["combat"] is True and spec.answers["pvp"] == "open"


def test_the_same_engine_builds_a_classroom_spec_and_selects_education() -> None:
    spec = _form().build_spec(
        "education",
        {
            "name": "Grade 3 Science",
            "owner": "ms_frizzle",
            "purpose": "cells",
            "roles": ["teacher", "student"],
        },
    )
    assert spec.product_type == "education"
    assert spec.domain_modules == ("education",)
    assert spec.answers["roles"] == ["teacher", "student"]


def test_a_classroom_spec_never_carries_the_game_module() -> None:
    """Grammar before worlds, by construction: an education Seed's spec selects no game module,
    so a classroom can never load combat downstream."""
    spec = _form().build_spec(
        "education",
        {"name": "Reading", "owner": "t", "purpose": "p", "roles": ["teacher"]},
    )
    assert "game" not in spec.domain_modules


def test_the_form_is_adaptive_a_conditional_question_appears_only_when_triggered() -> None:
    form = _form()
    # With combat unanswered, pvp is NOT active.
    ids_before = [q.id for q in form.questions_for("mmorpg")]
    assert "pvp" not in ids_before and "combat" in ids_before
    # Once combat is true, pvp becomes active.
    ids_after = [q.id for q in form.questions_for("mmorpg", {"combat": True})]
    assert "pvp" in ids_after


def test_an_inactive_conditional_question_is_not_required() -> None:
    """No combat -> pvp is inactive -> a spec without pvp is valid, and pvp is not collected."""
    spec = _form().build_spec(
        "mmorpg",
        {"name": "Peaceful", "owner": "josh", "purpose": "no fighting", "combat": False},
    )
    assert "pvp" not in spec.answers


def test_bool_and_multi_answers_are_coerced_and_normalized() -> None:
    spec = _form().build_spec(
        "mmorpg",
        {"name": "S", "owner": "o", "purpose": "p", "combat": "yes", "pvp": "none"},
    )
    assert spec.answers["combat"] is True  # "yes" -> True


def test_the_shipped_catalog_loads_and_has_the_three_product_types() -> None:
    """New product types are DATA: the real catalog file parses and offers the documented types."""
    form = EngineeringForm.load()
    ids = {pt.id for pt in form.product_types()}
    assert {"mmorpg", "education", "training"} <= ids
    # And the education product type still never selects the game module.
    education = next(pt for pt in form.product_types() if pt.id == "education")
    assert "game" not in education.domain_modules


def test_spec_roundtrips_to_a_machine_readable_dict() -> None:
    spec = _form().build_spec(
        "mmorpg", {"name": "S", "owner": "o", "purpose": "p", "combat": False}
    )
    d = spec.to_dict()
    assert d["product_type"] == "mmorpg" and d["domain_modules"] == ["game"]
    assert d["schema"] == 1


# --- refusal: fail loud ------------------------------------------------------------------------


def test_unknown_product_type_is_refused() -> None:
    with pytest.raises(FormError, match="unknown product type"):
        _form().build_spec("spaceship", {"name": "x", "owner": "o", "purpose": "p"})


def test_a_missing_required_answer_is_refused() -> None:
    with pytest.raises(FormError, match="missing required answer"):
        _form().build_spec("mmorpg", {"name": "x", "owner": "o"})  # no purpose, no combat


def test_an_out_of_range_choice_is_refused() -> None:
    with pytest.raises(FormError, match="not one of"):
        _form().build_spec(
            "mmorpg",
            {"name": "x", "owner": "o", "purpose": "p", "combat": True, "pvp": "faction"},
        )


def test_an_answer_outside_the_product_type_is_refused() -> None:
    """A typo or a cross-product answer (roles on an mmorpg) is refused, not silently dropped."""
    with pytest.raises(FormError, match="not part of product type"):
        _form().build_spec(
            "mmorpg",
            {"name": "x", "owner": "o", "purpose": "p", "combat": False, "roles": ["teacher"]},
        )


def test_a_dangling_question_reference_in_the_catalog_is_refused() -> None:
    bad = {
        "schema": 1,
        "common_question_ids": ["name"],
        "questions": {"name": {"prompt": "Name?", "kind": "text"}},
        "product_types": {"x": {"name": "X", "question_ids": ["ghost"], "domain_modules": []}},
    }
    with pytest.raises(FormError, match="unknown question"):
        FormDefinition.from_dict(bad)


def test_a_catalog_with_no_product_types_is_refused() -> None:
    with pytest.raises(FormError, match="at least one product type"):
        FormDefinition.from_dict(
            {"schema": 1, "common_question_ids": [], "questions": {}, "product_types": {}}
        )


def test_a_choice_question_without_choices_is_refused() -> None:
    with pytest.raises(FormError, match="needs choices"):
        Question(id="q", prompt="?", kind="choice")


def test_load_refuses_a_missing_catalog(tmp_path: Path) -> None:
    with pytest.raises(FormError, match="no Engineering Form catalog"):
        EngineeringForm.load(tmp_path / "absent.json")


# --- coercion + catalog-shape edge cases (every question kind, every failure branch) ------------

_KINDS_CATALOG = {
    "schema": 1,
    "common_question_ids": ["name", "owner", "purpose"],  # the identity fields every Seed carries
    "questions": {
        "name": {"prompt": "Name?", "kind": "text"},
        "owner": {"prompt": "Owner?", "kind": "text"},
        "purpose": {"prompt": "Purpose?", "kind": "text"},
        "size": {"prompt": "Size?", "kind": "number"},
        "flag": {"prompt": "Flag?", "kind": "bool"},
        "tags": {"prompt": "Tags?", "kind": "multi", "choices": ["a", "b"]},
        "note": {"prompt": "Note?", "kind": "text", "required": False},
    },
    "product_types": {
        "thing": {
            "name": "Thing",
            "question_ids": ["size", "flag", "tags", "note"],
            "domain_modules": [],
        }
    },
}


def _kinds_form() -> EngineeringForm:
    return EngineeringForm(FormDefinition.from_dict(_KINDS_CATALOG))


def _answers(**over: object) -> dict[str, object]:
    base: dict[str, object] = {
        "name": "n",
        "owner": "o",
        "purpose": "p",
        "size": 5,
        "flag": True,
        "tags": ["a"],
    }
    base.update(over)
    return base


def test_number_answers_coerce_to_int_and_float() -> None:
    assert _kinds_form().build_spec("thing", _answers(size="5")).answers["size"] == 5
    assert _kinds_form().build_spec("thing", _answers(size="1.5")).answers["size"] == 1.5


def test_a_non_numeric_number_answer_is_refused() -> None:
    with pytest.raises(FormError, match="expected a number"):
        _kinds_form().build_spec("thing", _answers(size="abc"))


def test_an_empty_required_text_answer_is_refused() -> None:
    with pytest.raises(FormError, match="non-empty"):
        _kinds_form().build_spec("thing", _answers(name=""))


def test_a_false_bool_token_coerces_to_false() -> None:
    assert _kinds_form().build_spec("thing", _answers(flag="no")).answers["flag"] is False


def test_a_non_list_multi_answer_is_refused() -> None:
    with pytest.raises(FormError, match="expected a list"):
        _kinds_form().build_spec("thing", _answers(tags="a"))


def test_an_empty_required_multi_answer_is_refused() -> None:
    with pytest.raises(FormError, match="at least one"):
        _kinds_form().build_spec("thing", _answers(tags=[]))


def test_an_out_of_range_multi_choice_is_refused() -> None:
    with pytest.raises(FormError, match="not valid choice"):
        _kinds_form().build_spec("thing", _answers(tags=["z"]))


def test_an_optional_question_may_be_omitted() -> None:
    spec = _kinds_form().build_spec("thing", _answers())  # no "note"
    assert "note" not in spec.answers


def test_an_unknown_question_kind_is_refused() -> None:
    with pytest.raises(FormError, match="unknown kind"):
        Question(id="q", prompt="?", kind="rune")


def test_from_dict_refuses_a_non_mapping_catalog() -> None:
    with pytest.raises(FormError, match="must be a mapping"):
        FormDefinition.from_dict("not a catalog")


def test_from_dict_refuses_a_malformed_catalog_shape() -> None:
    # missing common_question_ids -> a KeyError inside the parse, surfaced as a malformed catalog
    with pytest.raises(FormError, match="malformed catalog"):
        FormDefinition.from_dict(
            {
                "questions": {"name": {"prompt": "?", "kind": "text"}},
                "product_types": {
                    "x": {"name": "X", "question_ids": ["name"], "domain_modules": []}
                },
            }
        )


def test_load_refuses_unreadable_json(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(FormError, match="unreadable Form catalog"):
        EngineeringForm.load(bad)


def test_an_unparseable_bool_answer_is_refused() -> None:
    with pytest.raises(FormError, match="yes/no"):
        _kinds_form().build_spec("thing", _answers(flag="maybe"))
