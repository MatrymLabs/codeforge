"""Test twin for parts/shelf/conditions.py -- the safe condition evaluator (allowlist AST).

Acceptance: comparisons, boolean ops, membership, and chained compares evaluate against a context.
Refusal (the whole point): every escape a malicious seed might try -- calls, attribute walks,
subscripts, comprehensions, lambdas, f-strings, arithmetic, ternaries -- is refused at parse time by
the allowlist, not by a blacklist. Unknown names, empty strings, syntax errors, and uncomparable
pairs all fail loud.
"""

from __future__ import annotations

import pytest

from parts.shelf.conditions import ConditionError, evaluate, validate

_CTX = {"level": 10, "rank": "wizard", "inventory": ["ember", "copper_key"], "locked": False}


@pytest.mark.parametrize(
    "expr, expected",
    [
        ("level >= 5", True),
        ("level >= 20", False),
        ("level == 10", True),
        ("rank == 'wizard'", True),
        ("rank != 'player'", True),
        ("rank == 'wizard' and level >= 10", True),
        ("rank == 'wizard' and level >= 20", False),
        ("rank == 'peasant' or level >= 5", True),
        ("not locked", True),
        ("'ember' in inventory", True),
        ("'sword' in inventory", False),
        ("'sword' not in inventory", True),
        ("5 <= level <= 20", True),  # chained comparison
        ("5 <= level <= 8", False),
    ],
)
def test_valid_conditions_evaluate(expr: str, expected: bool) -> None:
    assert evaluate(expr, _CTX) is expected


# Every one of these is a construct a hostile seed might use to escape the sandbox. All must be
# refused at parse time (the allowlist), before any evaluation -- this is the security contract.
@pytest.mark.parametrize(
    "expr",
    [
        "__import__('os').system('rm -rf /')",  # Call + Attribute
        "().__class__.__bases__",  # Attribute walk to object internals
        "level.__class__",  # Attribute
        "open('/etc/passwd')",  # Call
        "[x for x in inventory]",  # ListComp
        "{k: v for k, v in inventory}",  # DictComp
        "(x for x in inventory)",  # GeneratorExp
        "lambda: 1",  # Lambda
        "1 + 1",  # BinOp (arithmetic)
        "level > -5",  # UnaryOp USub (negatives are arithmetic; not allowed)
        "f'{rank}'",  # JoinedStr (f-string)
        "1 if level else 2",  # IfExp (ternary)
        "inventory[0]",  # Subscript
        "rank = 'wizard'",  # assignment (syntax error in eval mode)
    ],
)
def test_forbidden_constructs_are_refused(expr: str) -> None:
    with pytest.raises(ConditionError):
        evaluate(expr, _CTX)
    # validate refuses the same expressions WITHOUT a context (the seed-load gate)
    with pytest.raises(ConditionError):
        validate(expr)


def test_an_unknown_name_fails_loud() -> None:
    # validate accepts the structure (a Name is allowed); evaluate refuses the missing binding
    validate("mystery >= 5")  # structurally fine
    with pytest.raises(ConditionError, match="unknown name"):
        evaluate("mystery >= 5", _CTX)


def test_an_empty_condition_fails_loud() -> None:
    with pytest.raises(ConditionError, match="empty condition"):
        evaluate("   ", _CTX)


def test_a_syntax_error_fails_loud() -> None:
    with pytest.raises(ConditionError, match="cannot parse"):
        validate("level >=")


def test_an_uncomparable_pair_fails_loud() -> None:
    # rank is a string; comparing it with >= to an int is a TypeError, surfaced as a ConditionError
    with pytest.raises(ConditionError, match="cannot compare"):
        evaluate("rank >= 5", _CTX)


def test_validate_returns_the_tree_for_a_good_expression() -> None:
    import ast

    tree = validate("level >= 5 and rank == 'wizard'")
    assert isinstance(tree, ast.Expression)
