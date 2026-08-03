"""CARD test twin for lock_expr -- acceptance + hostile/refusal cases."""

from __future__ import annotations

import unittest
from collections.abc import Callable
from typing import Any

from kernel.shelf.lock_expr import LockError, check, evaluate, parse

# --- Sample lock functions, reading a plain dict ctx ---------------------


def _rank(ctx: Any, r: str) -> bool:
    """True when the actor's rank matches ``r``."""
    return bool(ctx.get("rank") == r)


def _haskey(ctx: Any, k: str) -> bool:
    """True when ``k`` is among the actor's held keys."""
    return k in ctx.get("keys", ())


def _flag(ctx: Any, name: str) -> bool:
    """True when ``name`` is a set flag on the actor."""
    return name in ctx.get("flags", ())


def _boom(ctx: Any) -> bool:
    """A leaf that raises if ever called; used to prove short-circuiting."""
    raise AssertionError("this lock function must not be evaluated")


FUNCS: dict[str, Callable[..., bool]] = {
    "rank": _rank,
    "haskey": _haskey,
    "flag": _flag,
    "boom": _boom,
}


class AcceptanceTests(unittest.TestCase):
    def test_single_func_true(self) -> None:
        self.assertTrue(check("rank(wizard)", FUNCS, {"rank": "wizard"}))

    def test_single_func_false(self) -> None:
        self.assertFalse(check("rank(wizard)", FUNCS, {"rank": "builder"}))

    def test_and_both_true(self) -> None:
        ctx = {"rank": "builder", "keys": ("brass_key",)}
        self.assertTrue(check("rank(builder) AND haskey(brass_key)", FUNCS, ctx))

    def test_and_one_false(self) -> None:
        ctx = {"rank": "builder", "keys": ()}
        self.assertFalse(check("rank(builder) AND haskey(brass_key)", FUNCS, ctx))

    def test_or_one_true(self) -> None:
        ctx = {"rank": "player", "keys": ("brass_key",)}
        self.assertTrue(check("rank(wizard) OR haskey(brass_key)", FUNCS, ctx))

    def test_or_both_false(self) -> None:
        ctx = {"rank": "player", "keys": ()}
        self.assertFalse(check("rank(wizard) OR haskey(brass_key)", FUNCS, ctx))

    def test_not_negates(self) -> None:
        self.assertTrue(check("NOT flag(banned)", FUNCS, {"flags": ()}))
        self.assertFalse(check("NOT flag(banned)", FUNCS, {"flags": ("banned",)}))

    def test_precedence_not_over_and_over_or(self) -> None:
        # NOT binds tightest, then AND, then OR:
        #   rank(wizard) OR (rank(builder) AND (NOT flag(banned)))
        ctx = {"rank": "builder", "flags": ()}
        expr = "rank(wizard) OR rank(builder) AND NOT flag(banned)"
        self.assertTrue(check(expr, FUNCS, ctx))
        # A banned builder who is not a wizard is denied.
        self.assertFalse(check(expr, FUNCS, {"rank": "builder", "flags": ("banned",)}))

    def test_parens_override_precedence(self) -> None:
        # Without parens this is rank(wizard) OR (rank(builder) AND flag(vip)).
        # With parens the OR happens first, then the AND gates the whole thing.
        ctx = {"rank": "wizard", "flags": ()}
        without = "rank(wizard) OR rank(builder) AND flag(vip)"
        withp = "(rank(wizard) OR rank(builder)) AND flag(vip)"
        self.assertTrue(check(without, FUNCS, ctx))
        self.assertFalse(check(withp, FUNCS, ctx))

    def test_args_passed_to_func(self) -> None:
        seen: list[tuple[str, ...]] = []

        def spy(ctx: Any, *args: str) -> bool:
            seen.append(args)
            return True

        check("perm(edit, room, deep)", {"perm": spy}, {})
        self.assertEqual(seen, [("edit", "room", "deep")])

    def test_no_arg_func(self) -> None:
        self.assertTrue(check("always()", {"always": lambda ctx: True}, {}))

    def test_or_short_circuits(self) -> None:
        # Left side true -> boom() on the right must never be called.
        self.assertTrue(check("rank(wizard) OR boom()", FUNCS, {"rank": "wizard"}))

    def test_and_short_circuits(self) -> None:
        # Left side false -> boom() on the right must never be called.
        self.assertFalse(check("rank(wizard) AND boom()", FUNCS, {"rank": "player"}))

    def test_parse_returns_reusable_tree(self) -> None:
        tree = parse("rank(wizard)")
        self.assertTrue(evaluate(tree, FUNCS, {"rank": "wizard"}))
        self.assertFalse(evaluate(tree, FUNCS, {"rank": "player"}))


class RefusalTests(unittest.TestCase):
    def test_empty_string_fails_loud(self) -> None:
        with self.assertRaises(LockError):
            parse("")

    def test_whitespace_only_fails_loud(self) -> None:
        with self.assertRaises(LockError):
            parse("   ")

    def test_unbalanced_open_paren(self) -> None:
        with self.assertRaises(LockError):
            parse("(rank(wizard)")

    def test_unbalanced_close_paren(self) -> None:
        with self.assertRaises(LockError):
            parse("rank(wizard))")

    def test_trailing_operator(self) -> None:
        with self.assertRaises(LockError):
            parse("rank(wizard) AND")

    def test_leading_operator(self) -> None:
        with self.assertRaises(LockError):
            parse("OR rank(wizard)")

    def test_double_operator(self) -> None:
        with self.assertRaises(LockError):
            parse("rank(wizard) AND AND rank(builder)")

    def test_missing_call_parens(self) -> None:
        with self.assertRaises(LockError):
            parse("rank")

    def test_bad_glyph(self) -> None:
        with self.assertRaises(LockError):
            parse("rank(wizard) & haskey(brass_key)")

    def test_unknown_function_raises_not_false(self) -> None:
        # Unknown func must fail loud at evaluation, never degrade to False.
        with self.assertRaises(LockError):
            check("summon(demon)", FUNCS, {})

    def test_case_near_miss_keyword_is_not_operator(self) -> None:
        # Lowercase 'and' is NOT the AND operator; it parses as an identifier
        # that then fails loud (a function call with no parens).
        with self.assertRaises(LockError):
            parse("rank(wizard) and rank(builder)")

    def test_case_near_miss_func_token_unknown(self) -> None:
        # 'Rank' (capitalized) is not a valid lowercase token -> loud failure.
        with self.assertRaises(LockError):
            parse("Rank(wizard)")


if __name__ == "__main__":
    unittest.main()
