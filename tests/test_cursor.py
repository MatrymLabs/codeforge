"""Test twin for cursor.py. Acceptance AND refusal cases, including hostile input
(malformed token, tampered signature, wrong key, bad page size) and the
offset-drift property that keyset pagination exists to fix.

Run:  python3 -m unittest test_cursor   (or pytest test_cursor.py)
"""

from __future__ import annotations

import unittest
from dataclasses import dataclass

from parts.shelf.cursor import (
    MAX_PAGE_SIZE,
    CursorError,
    decode_cursor,
    encode_cursor,
    paginate_keyset,
    validate_size,
)


@dataclass
class Row:
    created: str  # sort key (isoformat string)
    id: int  # tiebreaker


def rows(n: int, start_id: int = 1) -> list[Row]:
    # ordered ascending by (created, id) as the equivalent SQL ORDER BY would be
    return [Row(created=f"2026-08-01T00:00:{i:02d}", id=start_id + i) for i in range(n)]


KEY = b"a-signing-key"


class CodecRoundtrip(unittest.TestCase):
    def test_unsigned_roundtrip(self):
        token = encode_cursor("2026-08-01T00:00:05", 42)
        self.assertEqual(decode_cursor(token), ("2026-08-01T00:00:05", 42))

    def test_signed_roundtrip(self):
        token = encode_cursor("k", 7, key=KEY)
        self.assertEqual(decode_cursor(token, key=KEY), ("k", 7))

    def test_int_and_float_values(self):
        self.assertEqual(decode_cursor(encode_cursor(3, 9)), (3, 9))
        self.assertEqual(decode_cursor(encode_cursor(1.5, 9)), (1.5, 9))

    def test_token_is_opaque(self):
        token = encode_cursor("secret-sort", 1)
        self.assertNotIn("secret-sort", token)  # base64, not plaintext

    # --- refusal ---
    def test_reject_empty(self):
        with self.assertRaises(CursorError):
            decode_cursor("")

    def test_reject_non_string(self):
        with self.assertRaises(CursorError):
            decode_cursor(123)

    def test_reject_malformed_base64(self):
        with self.assertRaises(CursorError):
            decode_cursor("!!!not-base64!!!")

    def test_reject_non_json_payload(self):
        with self.assertRaises(CursorError):
            decode_cursor(_b64_of(b"\xff\xff"))  # valid base64, not JSON

    def test_reject_unexpected_signature_when_unsigned(self):
        with self.assertRaises(CursorError):
            decode_cursor(encode_cursor("k", 1, key=KEY))  # signed token, no key given

    def test_reject_missing_signature_when_signed(self):
        with self.assertRaises(CursorError):
            decode_cursor(encode_cursor("k", 1), key=KEY)  # unsigned token, key expected

    def test_reject_tampered_payload(self):
        token = encode_cursor("k", 1, key=KEY)
        payload, sig = token.split(".")
        tampered = _flip(payload) + "." + sig
        with self.assertRaises(CursorError):
            decode_cursor(tampered, key=KEY)

    def test_reject_wrong_key(self):
        token = encode_cursor("k", 1, key=KEY)
        with self.assertRaises(CursorError):
            decode_cursor(token, key=b"different-key")


class PageSize(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(validate_size(50), 50)

    def test_reject_zero(self):
        with self.assertRaises(CursorError):
            validate_size(0)

    def test_reject_negative(self):
        with self.assertRaises(CursorError):
            validate_size(-1)

    def test_reject_over_max(self):
        with self.assertRaises(CursorError):
            validate_size(MAX_PAGE_SIZE + 1)

    def test_reject_bool(self):
        with self.assertRaises(CursorError):
            validate_size(True)


class Paginate(unittest.TestCase):
    def setUp(self):
        self.sort_key = lambda r: r.created
        self.tiebreak = lambda r: r.id

    def _page(self, data, size, after=None, sign_key=None):
        return paginate_keyset(
            data,
            sort_key=self.sort_key,
            tiebreak=self.tiebreak,
            size=size,
            after=after,
            sign_key=sign_key,
        )

    def test_first_page(self):
        page = self._page(rows(10), 3)
        self.assertEqual([r.id for r in page.items], [1, 2, 3])
        self.assertTrue(page.has_more)
        self.assertIsNotNone(page.next_cursor)

    def test_walk_all_pages(self):
        data = rows(10)
        seen: list[int] = []
        cursor = None
        while True:
            page = self._page(data, 3, after=cursor)
            seen.extend(r.id for r in page.items)
            if not page.has_more:
                break
            cursor = page.next_cursor
        self.assertEqual(seen, list(range(1, 11)))  # every row once, in order

    def test_last_page_has_no_more(self):
        page = self._page(rows(3), 5)
        self.assertEqual([r.id for r in page.items], [1, 2, 3])
        self.assertFalse(page.has_more)
        self.assertIsNone(page.next_cursor)

    def test_no_offset_drift_on_insert(self):
        # Read page 1, then a NEW row is inserted before the boundary. Keyset
        # pagination must not skip or repeat items across the page break.
        data = rows(6)  # ids 1..6
        page1 = self._page(data, 3)  # ids 1,2,3
        # insert a row that sorts before the boundary (earlier timestamp)
        inserted = Row(created="2026-08-01T00:00:00", id=999)
        grown = sorted(data + [inserted], key=lambda r: (r.created, r.id))
        page2 = self._page(grown, 3, after=page1.next_cursor)
        # boundary was id=3 @ ...:02; page 2 continues strictly after it
        self.assertEqual([r.id for r in page2.items], [4, 5, 6])
        # an OFFSET(3) here would have returned [3,4,5] (repeat 3, skip 6) - the bug we fix

    def test_signed_pagination_roundtrips(self):
        data = rows(5)
        page1 = self._page(data, 2, sign_key=KEY)
        page2 = self._page(data, 2, after=page1.next_cursor, sign_key=KEY)
        self.assertEqual([r.id for r in page1.items], [1, 2])
        self.assertEqual([r.id for r in page2.items], [3, 4])

    def test_bad_size_rejected(self):
        with self.assertRaises(CursorError):
            self._page(rows(3), 0)


# --- helpers ---
def _b64_of(raw: bytes) -> str:
    import base64

    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _flip(b64: str) -> str:
    # change one character to a different valid base64url char to corrupt payload
    swap = "A" if b64[0] != "A" else "B"
    return swap + b64[1:]


if __name__ == "__main__":
    unittest.main()
