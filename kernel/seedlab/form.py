"""CARD: form -- the Engineering Form: turn intent into a validated, machine-readable Seed spec.

The platform must serve an MMORPG, a grade-3 classroom, and an HR course from ONE engine. The Form
is how a purpose becomes a structured Seed definition without forking the engine per product type:

  * The CATALOG is DATA (data/seedlab/engineering_form.json) -- common questions, a per-product-type
    branch of questions, and the domain modules each product type selects. A new product type is a
    new entry there, never a code change here. This module knows nothing about combat, lessons, or
    certificates; it only walks the catalog.
  * `EngineeringForm` reads the catalog and, for a chosen product type, yields the ACTIVE questions
    (common + branch, honoring `applies_when` so the form adapts to prior answers), then validates a
    set of answers into a `BlueprintSpec`.
  * `BlueprintSpec` is the machine-readable output that drives the rest of the engine: the product

    the identity fields (name/owner/purpose), the selected `domain_modules`, and the validated
    answers. A classroom spec selects the `education` module and NEVER the game module -- grammar
    before worlds, enforced by construction rather than hoped for.

Fails loud and early: an unknown product type, a missing required answer, an out-of-range choice, or
an answer to a question that isn't part of the chosen product type is refused, never coerced into a
lie. Grammar before worlds: no kernel/world/ import. The catalog path is injectable (tests pass a
definition directly). Status: PROTOTYPED (see docs/seed_platform/RECENTERING.md).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# --- question kinds (the vocabulary of an answer's shape) --------------------------------------
TEXT = "text"
BOOL = "bool"
NUMBER = "number"
CHOICE = "choice"
MULTI = "multi"
_KINDS = (TEXT, BOOL, NUMBER, CHOICE, MULTI)

_SPEC_SCHEMA = 1  # the BlueprintSpec wire version, so a consumer can read (or refuse) it knowingly

_TRUE = {"true", "yes", "1", "on"}
_FALSE = {"false", "no", "0", "off"}


def _default_catalog_path() -> Path:
    """The shipped catalog, anchored to the repo so the Form loads the same file from any cwd."""
    return Path(__file__).resolve().parents[2] / "data" / "seedlab" / "engineering_form.json"


class FormError(Exception):
    """A Form could not be loaded, or an answer set could not be validated. Fails loud."""


@dataclass(frozen=True)
class Question:
    """One question in the Form. `applies_when` makes the Form adaptive: the question is active only
    when every named prior answer matches (e.g. `pvp` applies only when `combat` is true)."""

    id: str
    prompt: str
    kind: str
    required: bool = True
    choices: tuple[str, ...] = ()
    applies_when: tuple[tuple[str, Any], ...] = ()  # (question_id, required_value) pairs

    def __post_init__(self) -> None:
        if self.kind not in _KINDS:
            raise FormError(f"question {self.id!r}: unknown kind {self.kind!r}")
        if self.kind in (CHOICE, MULTI) and not self.choices:
            raise FormError(f"question {self.id!r}: a {self.kind} question needs choices")

    def is_active(self, answers: dict[str, Any]) -> bool:
        """True when this question applies given the answers so far (no condition == always)."""
        return all(answers.get(key) == value for key, value in self.applies_when)


@dataclass(frozen=True)
class ProductType:
    """A kind of Seed: its branch of questions and the domain modules it selects. The modules are
    what keep a classroom off combat -- an education product type simply never lists `game`."""

    id: str
    name: str
    description: str
    question_ids: tuple[str, ...]
    domain_modules: tuple[str, ...]


@dataclass(frozen=True)
class FormDefinition:
    """The whole catalog: the common questions every Seed answers, the question bank, and the
    product types. Built from the data file (or handed directly in a test)."""

    common_question_ids: tuple[str, ...]
    questions: dict[str, Question]
    product_types: dict[str, ProductType]

    @classmethod
    def from_dict(cls, raw: Any) -> FormDefinition:
        """Parse a catalog dict, failing loud on a malformed shape (never a vacuous empty Form)."""
        if not isinstance(raw, dict):
            raise FormError("catalog must be a mapping")
        try:
            questions = {
                qid: Question(
                    id=qid,
                    prompt=q["prompt"],
                    kind=q["kind"],
                    required=q.get("required", True),
                    choices=tuple(q.get("choices", ())),
                    applies_when=tuple((k, v) for k, v in q.get("applies_when", {}).items()),
                )
                for qid, q in raw["questions"].items()
            }
            product_types = {
                pid: ProductType(
                    id=pid,
                    name=p["name"],
                    description=p.get("description", ""),
                    question_ids=tuple(p["question_ids"]),
                    domain_modules=tuple(p.get("domain_modules", ())),
                )
                for pid, p in raw["product_types"].items()
            }
            common = tuple(raw["common_question_ids"])
        except (KeyError, TypeError) as exc:
            raise FormError(f"malformed catalog: {exc}") from exc
        if not product_types:
            raise FormError("a Form needs at least one product type")
        # Every referenced question id must exist -- a dangling branch is a filing error.
        for pid, pt in product_types.items():
            for qid in (*common, *pt.question_ids):
                if qid not in questions:
                    raise FormError(f"product type {pid!r} references unknown question {qid!r}")
        return cls(common, questions, product_types)


@dataclass(frozen=True)
class BlueprintSpec:
    """The Form's machine-readable output: everything the engine needs to configure a Seed and pick
    its domain modules. `answers` holds the validated, coerced field values."""

    schema: int
    product_type: str
    name: str
    owner: str
    purpose: str
    domain_modules: tuple[str, ...]
    answers: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "product_type": self.product_type,
            "name": self.name,
            "owner": self.owner,
            "purpose": self.purpose,
            "domain_modules": list(self.domain_modules),
            "answers": dict(self.answers),
        }


def load_definition(path: Path | None = None) -> FormDefinition:
    """Load the Engineering Form CATALOG (a `FormDefinition`) from the data file, failing loud if it
    is absent or malformed. The public loader for callers that project the Form directly (the
    workspace GMCP `form_schema` / `create_from_form_submit`) rather than walking it through an
    `EngineeringForm`. Path resolved at call time so a test can point at a fixture."""
    catalog_path = path or _default_catalog_path()
    try:
        raw = json.loads(catalog_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FormError(f"no Engineering Form catalog at {catalog_path}") from exc
    except json.JSONDecodeError as exc:
        raise FormError(f"unreadable Form catalog {catalog_path}: {exc}") from exc
    return FormDefinition.from_dict(raw)


class EngineeringForm:
    """Walks the catalog for one product type and validates answers into a BlueprintSpec.

    the same instance builds a game spec and a classroom spec, selecting different modules from data
    alone."""

    def __init__(self, definition: FormDefinition) -> None:
        self._def = definition

    @classmethod
    def load(cls, path: Path | None = None) -> EngineeringForm:
        """Load the Form from the data catalog (default: the shipped file), failing loud if absent
        or malformed -- an empty Form would be a silent hole in the platform's front door."""
        return cls(load_definition(path))

    def product_types(self) -> list[ProductType]:
        """Every product type the Form can build, for a chooser to render."""
        return list(self._def.product_types.values())

    def _product_type(self, product_type: str) -> ProductType:
        pt = self._def.product_types.get(product_type)
        if pt is None:
            known = ", ".join(sorted(self._def.product_types)) or "(none)"
            raise FormError(f"unknown product type {product_type!r}; known: {known}")
        return pt

    def _ordered_questions(self, pt: ProductType) -> list[Question]:
        ids = (*self._def.common_question_ids, *pt.question_ids)
        return [self._def.questions[qid] for qid in ids]

    def questions_for(
        self, product_type: str, answers: dict[str, Any] | None = None
    ) -> list[Question]:
        """The ACTIVE questions for a product type given the answers so far (common first, then the
        branch), honoring `applies_when` so the Form adapts as a caller answers. With no answers, an
        unconditional question is active and a conditional one is not (its trigger unanswered)."""
        answers = answers or {}
        pt = self._product_type(product_type)
        return [q for q in self._ordered_questions(pt) if q.is_active(answers)]

    def build_spec(self, product_type: str, answers: dict[str, Any]) -> BlueprintSpec:
        """Validate `answers` into a BlueprintSpec for `product_type`. Fails loud on an unknown

        type, an answer to a question outside this product type, a missing required answer, or an
        out-of-range value. Inactive conditional questions are neither required nor collected."""
        pt = self._product_type(product_type)
        valid_ids = {*self._def.common_question_ids, *pt.question_ids}
        unknown = set(answers) - valid_ids
        if unknown:
            raise FormError(
                f"answer(s) not part of product type {product_type!r}: {', '.join(sorted(unknown))}"
            )
        collected: dict[str, Any] = {}
        for question in self._ordered_questions(pt):
            if not question.is_active(answers):
                continue  # a conditional question whose trigger is not met: skip, do not require
            if question.id not in answers:
                if question.required:
                    raise FormError(f"missing required answer: {question.id!r} ({question.prompt})")
                continue
            collected[question.id] = _coerce(question, answers[question.id])
        return BlueprintSpec(
            schema=_SPEC_SCHEMA,
            product_type=pt.id,
            name=str(collected["name"]),
            owner=str(collected["owner"]),
            purpose=str(collected["purpose"]),
            domain_modules=pt.domain_modules,
            answers=collected,
        )


def _coerce(question: Question, value: Any) -> Any:  # noqa: PLR0911, PLR0912
    """Validate + normalize one answer to its question's kind, failing loud on anything unfit. The
    Form never silently accepts a wrong-shaped answer -- a bad classroom answer is not a game."""
    kind = question.kind
    if kind == TEXT:
        text = str(value).strip()
        if question.required and not text:
            raise FormError(f"{question.id!r}: a non-empty answer is required")
        return text
    if kind == BOOL:
        if isinstance(value, bool):
            return value
        token = str(value).strip().lower()
        if token in _TRUE:
            return True
        if token in _FALSE:
            return False
        raise FormError(f"{question.id!r}: expected a yes/no answer, got {value!r}")
    if kind == NUMBER:
        try:
            return int(value) if str(value).strip().lstrip("-").isdigit() else float(value)
        except (TypeError, ValueError) as exc:
            raise FormError(f"{question.id!r}: expected a number, got {value!r}") from exc
    if kind == CHOICE:
        if value not in question.choices:
            raise FormError(
                f"{question.id!r}: {value!r} is not one of {', '.join(question.choices)}"
            )
        return value
    if kind == MULTI:
        if not isinstance(value, (list, tuple)):
            raise FormError(f"{question.id!r}: expected a list of choices, got {value!r}")
        chosen = list(value)
        if question.required and not chosen:
            opts = ", ".join(question.choices)
            raise FormError(f"{question.id!r}: choose at least one of {opts}")
        bad = [v for v in chosen if v not in question.choices]
        if bad:
            raise FormError(f"{question.id!r}: not valid choice(s): {', '.join(map(str, bad))}")
        return chosen
    raise FormError(f"{question.id!r}: unhandled kind {kind!r}")  # pragma: no cover (guarded above)
