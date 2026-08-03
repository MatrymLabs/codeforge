"""Test twin for recognition.py (RD-2026-0007 Evennia harvest).

Acceptance (a stranger sees the sdesc; a recognizer sees their alias; forget reverts; state is
canonical, never mutated by a projection) and refusal (bad labels, blank/overlong, self-recog,
naming an unknown target fail loud). Hostile data: mixed case, symbols, near-misses.
"""

from __future__ import annotations

import unittest

from kernel.shelf import recognition as r


class Acceptance(unittest.TestCase):
    def test_a_stranger_sees_the_short_description(self):
        book = r.Book().with_sdesc("npc_ranger", "a tall man")
        self.assertEqual(r.resolve(book, "hero_ana", "npc_ranger"), "a tall man")

    def test_a_recognizer_sees_their_personal_alias(self):
        book = (
            r.Book()
            .with_sdesc("npc_ranger", "a tall man")
            .with_recog("hero_ana", "npc_ranger", "Aragorn")
        )
        self.assertEqual(r.resolve(book, "hero_ana", "npc_ranger"), "Aragorn")

    def test_recognition_is_per_observer(self):
        book = (
            r.Book()
            .with_sdesc("npc_ranger", "a tall man")
            .with_recog("hero_ana", "npc_ranger", "Aragorn")
        )
        # Ana sees Aragorn; Bob (who never recognized him) still sees the sdesc
        self.assertEqual(r.resolve(book, "hero_ana", "npc_ranger"), "Aragorn")
        self.assertEqual(r.resolve(book, "hero_bob", "npc_ranger"), "a tall man")

    def test_forget_reverts_to_the_sdesc(self):
        book = (
            r.Book()
            .with_sdesc("npc_ranger", "a tall man")
            .with_recog("hero_ana", "npc_ranger", "Aragorn")
            .forget("hero_ana", "npc_ranger")
        )
        self.assertEqual(r.resolve(book, "hero_ana", "npc_ranger"), "a tall man")

    def test_forget_unknown_pair_is_a_noop(self):
        book = r.Book().with_sdesc("npc_ranger", "a tall man")
        self.assertIs(book.forget("hero_ana", "npc_ranger"), book)

    def test_resolve_all_projects_a_room_of_occupants_in_order(self):
        book = (
            r.Book()
            .with_sdesc("npc_ranger", "a tall man")
            .with_sdesc("npc_smith", "a burly smith")
            .with_recog("hero_ana", "npc_smith", "Gimli")
        )
        self.assertEqual(
            r.resolve_all(book, "hero_ana", ["npc_ranger", "npc_smith"]),
            ["a tall man", "Gimli"],
        )

    def test_sdesc_and_alias_are_stripped(self):
        book = (
            r.Book()
            .with_sdesc("npc_ranger", "  a tall man  ")
            .with_recog("hero_ana", "npc_ranger", "  Aragorn  ")
        )
        self.assertEqual(book.sdescs["npc_ranger"], "a tall man")
        self.assertEqual(r.resolve(book, "hero_ana", "npc_ranger"), "Aragorn")


class CanonicalState(unittest.TestCase):
    def test_a_projection_never_mutates_the_book(self):
        book = r.Book().with_sdesc("npc_ranger", "a tall man")
        r.resolve(book, "hero_ana", "npc_ranger")
        r.resolve_all(book, "hero_ana", ["npc_ranger"])
        self.assertEqual(book.recogs, {})  # resolving learned nothing; state is unchanged

    def test_with_recog_is_copy_on_write(self):
        base = r.Book().with_sdesc("npc_ranger", "a tall man")
        derived = base.with_recog("hero_ana", "npc_ranger", "Aragorn")
        self.assertEqual(base.recogs, {})  # the original book is untouched
        self.assertIn("hero_ana", derived.recogs)


class Refusal(unittest.TestCase):
    def test_non_snake_case_target_id_fails_loud(self):
        for bad in ("NpcRanger", "npc ranger", "npc-ranger", "1npc", "", "npc!"):
            with self.assertRaises(r.RecognitionError):
                r.Book().with_sdesc(bad, "a tall man")

    def test_blank_or_overlong_sdesc_fails_loud(self):
        with self.assertRaises(r.RecognitionError):
            r.Book().with_sdesc("npc_ranger", "   ")
        with self.assertRaises(r.RecognitionError):
            r.Book().with_sdesc("npc_ranger", "x" * 61)

    def test_self_recognition_is_refused(self):
        with self.assertRaises(r.RecognitionError):
            r.Book().with_recog("hero_ana", "hero_ana", "Me")

    def test_naming_an_unknown_target_fails_loud_not_empty(self):
        book = r.Book()  # no sdesc, no recog
        with self.assertRaises(r.RecognitionError):
            r.resolve(book, "hero_ana", "npc_ghost")

    def test_symbols_and_near_miss_ids_are_rejected(self):
        book = r.Book().with_sdesc("npc_ranger", "a tall man")
        with self.assertRaises(r.RecognitionError):
            r.resolve(book, "hero-ana", "npc_ranger")  # hyphen, not underscore
        with self.assertRaises(r.RecognitionError):
            r.resolve(book, "hero_ana", "NPC_RANGER")  # uppercase near-miss


if __name__ == "__main__":
    unittest.main()
