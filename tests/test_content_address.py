"""Test twin for content_address.py. Structurally-identical code shares an address,
formatting/comments/binding-name don't change it, normalize_locals collides clones with
different local names but never touches globals/attributes, the Store dedups + finds
clones, and bad source is refused.

Run:  python3 -m unittest test_content_address
"""

from __future__ import annotations

import unittest

from parts.shelf.content_address import (
    ContentAddressError,
    Store,
    canonicalize,
    content_hash,
    render_store,
)


class Addressing(unittest.TestCase):
    def test_formatting_and_comments_do_not_change_the_address(self):
        a = "def f(x):\n    return x + 1\n"
        b = "def f( x ):\n    # a comment\n    return x+1\n"
        self.assertEqual(content_hash(a), content_hash(b))

    def test_binding_rename_is_free(self):
        # renaming the definition itself must not change its address
        self.assertEqual(
            content_hash("def foo():\n    return 1\n"),
            content_hash("def bar():\n    return 1\n"),
        )

    def test_different_bodies_differ(self):
        self.assertNotEqual(
            content_hash("def f():\n    return 1\n"),
            content_hash("def f():\n    return 2\n"),
        )

    def test_address_is_a_sha256_hex(self):
        h = content_hash("x = 1\n")
        self.assertEqual(len(h), 64)
        int(h, 16)  # valid hex


class NormalizeLocals(unittest.TestCase):
    def test_local_variable_names_collide_when_normalized(self):
        a = "def f(count):\n    total = count * 2\n    return total\n"
        b = "def f(n):\n    result = n * 2\n    return result\n"
        self.assertNotEqual(content_hash(a), content_hash(b))  # off: names differ
        self.assertEqual(
            content_hash(a, normalize_locals=True),
            content_hash(b, normalize_locals=True),
        )  # on: same structure, clone

    def test_globals_and_attributes_are_not_renamed(self):
        # two functions differing only in a GLOBAL name must NOT collide (globals matter)
        a = "def f(x):\n    return CONFIG_A + x\n"
        b = "def f(x):\n    return CONFIG_B + x\n"
        self.assertNotEqual(
            content_hash(a, normalize_locals=True),
            content_hash(b, normalize_locals=True),
        )

    def test_different_structure_still_differs_when_normalized(self):
        a = "def f(x):\n    return x + 1\n"
        b = "def f(x):\n    return x - 1\n"
        self.assertNotEqual(
            content_hash(a, normalize_locals=True),
            content_hash(b, normalize_locals=True),
        )


class ContentStore(unittest.TestCase):
    def test_dedup_and_unique_count(self):
        store = Store()
        store.add("alpha", "def a():\n    return 1\n")
        store.add("beta", "def b():\n    return 1\n")  # same body, rename-free -> same address
        store.add("gamma", "def c():\n    return 2\n")
        self.assertEqual(len(store), 3)
        self.assertEqual(store.unique_count(), 2)

    def test_clones_grouped(self):
        store = Store()
        store.add("alpha", "def a():\n    return 1\n")
        store.add("beta", "def b():\n    return 1\n")
        clones = store.clones()
        self.assertEqual(len(clones), 1)
        self.assertEqual(set(clones[0]), {"alpha", "beta"})

    def test_is_known(self):
        store = Store()
        store.add("alpha", "def a():\n    return 1\n")
        self.assertTrue(store.is_known("def renamed():\n    return 1\n"))
        self.assertFalse(store.is_known("def a():\n    return 99\n"))

    def test_digest_of_and_names_for(self):
        store = Store()
        d = store.add("alpha", "def a():\n    return 1\n")
        self.assertEqual(store.digest_of("alpha"), d.digest)
        self.assertIn("alpha", store.names_for(d.digest))
        self.assertIsNone(store.digest_of("missing"))

    def test_clone_store_with_normalize_locals(self):
        store = Store(normalize_locals=True)
        store.add("byCount", "def f(count):\n    return count + 1\n")
        store.add("byN", "def f(n):\n    return n + 1\n")
        self.assertEqual(store.unique_count(), 1)  # structural clones despite local names


class RenderAndRefusal(unittest.TestCase):
    def test_render_reports_clones(self):
        store = Store()
        store.add("alpha", "def a():\n    return 1\n")
        store.add("beta", "def b():\n    return 1\n")
        out = render_store(store)
        self.assertIn("clone groups", out)
        self.assertIn("alpha", out)

    def test_render_no_clones(self):
        store = Store()
        store.add("alpha", "def a():\n    return 1\n")
        self.assertIn("no clones", render_store(store))

    def test_canonicalize_is_deterministic(self):
        src = "def f(x):\n    return x\n"
        self.assertEqual(canonicalize(src), canonicalize(src))

    def test_syntax_error_refused(self):
        with self.assertRaises(ContentAddressError):
            content_hash("def broken(:\n    pass\n")


if __name__ == "__main__":
    unittest.main()
