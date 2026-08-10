"""Test twin for type_smell.py (RD-2026-0001).

Acceptance (each detector fires on a real smell), refusal (malformed source fails loud;
clean/typed code is silent), and hostile cases (dunders, self/cls, *args/**kwargs, nested
functions, Any nested in a generic, two-types-one-name).

Run:  python3 -m unittest test_type_smell
"""

from __future__ import annotations

import unittest

from kernel.shelf import type_smell as ts


def ids(src: str) -> list[str]:
    return [s.smell_id for s in ts.analyze(src)]


class UntypedPublicApi(unittest.TestCase):
    def test_public_fn_with_params_and_no_annotations_is_untyped(self):
        self.assertIn("TYPE_SMELL.UNTYPED_PUBLIC_API", ids("def parse(row, sep): return row"))

    def test_private_fn_is_out_of_scope(self):
        self.assertEqual(ids("def _parse(row, sep): return row"), [])

    def test_no_param_function_is_not_flagged_untyped(self):
        # a return-only obligation is intentionally out of this lens's scope (too noisy)
        self.assertEqual(ids("def ping(): return 1"), [])

    def test_self_is_not_counted_as_a_parameter(self):
        src = "class C:\n    def run(self): return 1"
        self.assertNotIn("TYPE_SMELL.UNTYPED_PUBLIC_API", ids(src))


class PartialAnnotation(unittest.TestCase):
    def test_typed_params_but_missing_return_is_partial(self):
        self.assertIn("TYPE_SMELL.PARTIAL_ANNOTATION", ids("def f(x: int, y: int): return x"))

    def test_some_params_typed_others_not_is_partial(self):
        self.assertIn("TYPE_SMELL.PARTIAL_ANNOTATION", ids("def f(x: int, y) -> int: return x"))

    def test_fully_annotated_is_clean(self):
        self.assertEqual(ids("def f(x: int, y: str) -> bool: return True"), [])


class AnyOnPublic(unittest.TestCase):
    def test_any_param_flagged(self):
        self.assertIn(
            "TYPE_SMELL.ANY_ON_PUBLIC",
            ids("from typing import Any\ndef f(x: Any) -> int: return 1"),
        )

    def test_any_return_flagged(self):
        self.assertIn(
            "TYPE_SMELL.ANY_ON_PUBLIC",
            ids("from typing import Any\ndef f(x: int) -> Any: return x"),
        )

    def test_any_nested_in_generic_flagged(self):
        self.assertIn(
            "TYPE_SMELL.ANY_ON_PUBLIC",
            ids("from typing import Any\ndef f(x: list[Any]) -> int: return 1"),
        )

    def test_typing_dot_any_flagged(self):
        self.assertIn(
            "TYPE_SMELL.ANY_ON_PUBLIC", ids("import typing\ndef f(x: typing.Any) -> int: return 1")
        )


class InconsistentParamType(unittest.TestCase):
    def test_same_name_two_types_flagged_once(self):
        src = "def a(user: str) -> int: return 1\ndef b(user: int) -> int: return user"
        got = ids(src)
        self.assertEqual(got.count("TYPE_SMELL.INCONSISTENT_PARAM_TYPE"), 1)

    def test_same_name_same_type_is_clean_of_inconsistency(self):
        src = "def a(user: str) -> int: return 1\ndef b(user: str) -> int: return 1"
        self.assertNotIn("TYPE_SMELL.INCONSISTENT_PARAM_TYPE", ids(src))

    def test_message_names_both_types_and_lines(self):
        src = "def a(user: str) -> int: return 1\ndef b(user: int) -> int: return user"
        s = next(x for x in ts.analyze(src) if x.smell_id == "TYPE_SMELL.INCONSISTENT_PARAM_TYPE")
        self.assertIn("str", s.message)
        self.assertIn("int", s.message)


class Hostile(unittest.TestCase):
    def test_malformed_source_fails_loud(self):
        with self.assertRaises(ts.TypeSmellError):
            ts.analyze("def f(:\n  pass")

    def test_varargs_and_kwargs_count_as_typed_or_untyped(self):
        # *args/**kwargs with no annotation on an otherwise-typed fn -> partial
        self.assertIn(
            "TYPE_SMELL.PARTIAL_ANNOTATION", ids("def f(x: int, *args, **kwargs) -> int: return x")
        )

    def test_nested_public_function_is_analyzed(self):
        src = "def outer() -> None:\n    def inner(a): return a\n    inner(1)"
        self.assertIn("TYPE_SMELL.UNTYPED_PUBLIC_API", ids(src))

    def test_async_function_is_analyzed(self):
        self.assertIn("TYPE_SMELL.UNTYPED_PUBLIC_API", ids("async def fetch(url): return url"))

    def test_dunder_is_out_of_scope(self):
        src = "class C:\n    def __init__(self, x): self.x = x"
        self.assertEqual(ids(src), [])

    def test_empty_module_is_clean(self):
        self.assertEqual(ts.analyze(""), [])


class Api(unittest.TestCase):
    def test_smell_ids_matches_detectors(self):
        self.assertEqual(len(ts.smell_ids()), 4)

    def test_render_clean_and_dirty(self):
        self.assertIn("CLEAN", ts.render([]))
        self.assertIn("TYPE_SMELL", ts.render(ts.analyze("def f(a, b): return a")))

    def test_findings_sorted_by_line(self):
        src = "def z(a): return a\ndef y(b): return b"
        lines = [s.line for s in ts.analyze(src)]
        self.assertEqual(lines, sorted(lines))


if __name__ == "__main__":
    unittest.main()
