"""Test twin for precondition.py. Acceptance AND refusal cases, including hostile
input (unquoted etag, empty header, weak etag under If-Match, star edge cases,
non-int/negative versions).

Run:  python3 -m unittest test_precondition   (or pytest test_precondition.py)
"""

from __future__ import annotations

import unittest

from parts.shelf.precondition import (
    ETag,
    PreconditionError,
    PreconditionFailed,
    StaleWrite,
    etag_for_payload,
    etag_for_version,
    if_match,
    if_none_match,
    next_version,
    parse_etag,
    require_version,
)


class ETagValue(unittest.TestCase):
    def test_version_etag_format(self):
        self.assertEqual(etag_for_version(3).format(), '"3"')
        self.assertFalse(etag_for_version(3).weak)

    def test_payload_etag_is_stable_and_strong(self):
        a = etag_for_payload(b"hello")
        b = etag_for_payload(b"hello")
        self.assertEqual(a, b)
        self.assertNotEqual(a, etag_for_payload(b"world"))
        self.assertFalse(a.weak)

    def test_weak_payload_etag(self):
        self.assertTrue(etag_for_payload(b"x", weak=True).weak)

    def test_parse_strong_and_weak(self):
        self.assertEqual(parse_etag('"abc"'), ETag("abc", weak=False))
        self.assertEqual(parse_etag('W/"abc"'), ETag("abc", weak=True))

    # --- refusal ---
    def test_reject_unquoted_etag(self):
        with self.assertRaises(PreconditionError):
            parse_etag("abc")

    def test_reject_non_string_etag(self):
        with self.assertRaises(PreconditionError):
            parse_etag(3)

    def test_reject_negative_version(self):
        with self.assertRaises(PreconditionError):
            etag_for_version(-1)

    def test_reject_bool_version(self):
        with self.assertRaises(PreconditionError):
            etag_for_version(True)  # bool is not a valid version

    def test_reject_non_bytes_payload(self):
        with self.assertRaises(PreconditionError):
            etag_for_payload("not bytes")


class IfMatch(unittest.TestCase):
    def setUp(self):
        self.current = etag_for_version(5)  # '"5"'

    def test_match_passes(self):
        if_match(self.current, '"5"')  # no raise

    def test_match_in_list_passes(self):
        if_match(self.current, '"1", "5", "9"')

    def test_mismatch_fails(self):
        with self.assertRaises(PreconditionFailed):
            if_match(self.current, '"4"')

    def test_star_passes_when_exists(self):
        if_match(self.current, "*")

    def test_star_fails_when_absent(self):
        with self.assertRaises(PreconditionFailed):
            if_match(None, "*")

    def test_if_match_on_absent_resource_fails(self):
        with self.assertRaises(PreconditionFailed):
            if_match(None, '"5"')

    def test_weak_etag_never_satisfies_if_match(self):
        # RFC 7232: If-Match uses strong comparison; a weak tag must not match.
        with self.assertRaises(PreconditionFailed):
            if_match(self.current, 'W/"5"')

    def test_weak_current_never_satisfies_if_match(self):
        weak_current = etag_for_payload(b"data", weak=True)
        with self.assertRaises(PreconditionFailed):
            if_match(weak_current, weak_current.format().replace("W/", ""))

    # --- refusal on malformed header ---
    def test_empty_header_rejected(self):
        with self.assertRaises(PreconditionError):
            if_match(self.current, "")

    def test_malformed_member_rejected(self):
        with self.assertRaises(PreconditionError):
            if_match(self.current, '"5", bogus')


class IfNoneMatch(unittest.TestCase):
    def setUp(self):
        self.current = etag_for_version(5)

    def test_star_passes_when_absent(self):
        if_none_match(None, "*")  # safe create

    def test_star_fails_when_exists(self):
        with self.assertRaises(PreconditionFailed):
            if_none_match(self.current, "*")

    def test_match_fails(self):
        with self.assertRaises(PreconditionFailed):
            if_none_match(self.current, '"5"')

    def test_weak_comparison_matches(self):
        # If-None-Match uses weak comparison: a weak tag with the same value matches.
        with self.assertRaises(PreconditionFailed):
            if_none_match(self.current, 'W/"5"')

    def test_no_match_passes(self):
        if_none_match(self.current, '"4"')

    def test_absent_resource_passes(self):
        if_none_match(None, '"5"')


class VersionGuard(unittest.TestCase):
    def test_equal_versions_pass(self):
        require_version(7, 7)  # no raise

    def test_stale_raises(self):
        with self.assertRaises(StaleWrite):
            require_version(6, 7)

    def test_stale_is_precondition_failed(self):
        self.assertTrue(issubclass(StaleWrite, PreconditionFailed))

    def test_next_version_increments(self):
        self.assertEqual(next_version(7), 8)

    def test_reject_non_int(self):
        with self.assertRaises(PreconditionError):
            require_version("7", 7)

    def test_reject_bool(self):
        with self.assertRaises(PreconditionError):
            require_version(True, 1)

    def test_next_version_rejects_negative(self):
        with self.assertRaises(PreconditionError):
            next_version(-1)

    def test_optimistic_write_cycle(self):
        # read v3, guard, write, bump
        stored = 3
        read = 3
        require_version(read, stored)
        stored = next_version(stored)
        self.assertEqual(stored, 4)
        # a second writer who also read v3 is now stale
        with self.assertRaises(StaleWrite):
            require_version(read, stored)


if __name__ == "__main__":
    unittest.main()
