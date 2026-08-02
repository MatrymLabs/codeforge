"""CARD: conditions -- a safe boolean-expression evaluator for seed-declared gates (allowlist AST).

A seed author gates content on world state with a plain expression (`level >= 5 and rank == "x"`)
evaluated against a whitelisted context. It is safe by an ALLOWLIST, never a blacklist: the parsed
AST may contain ONLY boolean ops (and/or/not), comparisons (== != < <= > >= in not-in), names
(resolved from the context), and literal constants. EVERY other node -- a call, attribute access,
subscript, import, comprehension, f-string, lambda, arithmetic -- is refused at parse time. There is
no reachable path to __import__, an object's __class__, or any attribute or call: those node types
are simply not in the allowlist. Engine-agnostic (stdlib only); reads and evaluates, never mutates.

`validate` parses + checks an expression without a context (a seed-load gate for bad rules).
`evaluate` does that, then resolves names from the context and returns a bool. Both fail loud.
"""

from __future__ import annotations

import ast
from typing import Any

# The ONLY AST node types a condition may contain. An allowlist, so anything unlisted (Call,
# Attribute, Subscript, Import, Lambda, comprehensions, BinOp, f-strings, ...) is refused.
_ALLOWED = (
    ast.Expression,
    ast.BoolOp,
    ast.And,
    ast.Or,
    ast.UnaryOp,
    ast.Not,
    ast.Compare,
    ast.Name,
    ast.Load,
    ast.Constant,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.In,
    ast.NotIn,
)

_COMPARE = {
    ast.Eq: lambda a, b: a == b,
    ast.NotEq: lambda a, b: a != b,
    ast.Lt: lambda a, b: a < b,
    ast.LtE: lambda a, b: a <= b,
    ast.Gt: lambda a, b: a > b,
    ast.GtE: lambda a, b: a >= b,
    ast.In: lambda a, b: a in b,
    ast.NotIn: lambda a, b: a not in b,
}


class ConditionError(ValueError):
    """A condition is malformed or uses a forbidden construct. Fails loud, never guesses a value."""


def validate(expression: str) -> ast.Expression:
    """Parse `expression` and confirm every node is on the allowlist; return the tree. Fails loud.

    A seed-load gate: it never evaluates, so it needs no context -- it just proves the expression is
    a safe condition (no calls/attributes/imports/etc.) before the world trusts it at runtime."""
    if not expression.strip():
        raise ConditionError("empty condition")
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ConditionError(f"cannot parse condition {expression!r}: {exc}") from exc
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED):
            raise ConditionError(
                f"forbidden construct in condition {expression!r}: {type(node).__name__}"
            )
    return tree


def evaluate(expression: str, context: dict[str, Any]) -> bool:
    """Evaluate a safe condition against `context` (a whitelist of names) and return a bool.

    Fails loud on a forbidden construct (via validate), an unknown name, or an uncomparable pair."""
    tree = validate(expression)
    return bool(_eval(tree.body, context))


def _eval(node: ast.AST, ctx: dict[str, Any]) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        if node.id not in ctx:
            raise ConditionError(f"unknown name in condition: {node.id!r}")
        return ctx[node.id]
    if isinstance(node, ast.BoolOp):
        values = [_eval(v, ctx) for v in node.values]
        return all(values) if isinstance(node.op, ast.And) else any(values)
    if isinstance(node, ast.UnaryOp):  # allowlist guarantees op is Not
        return not _eval(node.operand, ctx)
    if isinstance(node, ast.Compare):
        left = _eval(node.left, ctx)
        for op, right_node in zip(node.ops, node.comparators, strict=True):
            right = _eval(right_node, ctx)
            if not _compare(op, left, right):
                return False
            left = right
        return True
    raise ConditionError(f"unsupported condition node: {type(node).__name__}")  # pragma: no cover


def _compare(op: ast.cmpop, left: Any, right: Any) -> bool:
    apply = _COMPARE[type(op)]  # allowlist guarantees op is one of these
    try:
        return bool(apply(left, right))
    except TypeError as exc:
        raise ConditionError(f"cannot compare {left!r} and {right!r}: {exc}") from exc
