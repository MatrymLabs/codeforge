"""Test twin for outbox.py. Acceptance AND refusal cases, including hostile input
and the durability/at-least-once properties the outbox exists to guarantee.

Run:  python3 -m unittest test_outbox   (or pytest test_outbox.py)
"""

from __future__ import annotations

import unittest

from kernel.shelf.outbox import (
    DEAD,
    PENDING,
    SENT,
    Outbox,
    OutboxError,
    OutboxRecord,
    relay,
)


class AlwaysOk:
    def __init__(self) -> None:
        self.published: list[str] = []

    def __call__(self, record: OutboxRecord) -> None:
        self.published.append(record.id)


class AlwaysFail:
    def __call__(self, record: OutboxRecord) -> None:
        raise RuntimeError("broker down")


class FailThenOk:
    def __init__(self, fail_times: int) -> None:
        self.remaining = fail_times
        self.published: list[str] = []

    def __call__(self, record: OutboxRecord) -> None:
        if self.remaining > 0:
            self.remaining -= 1
            raise RuntimeError("transient")
        self.published.append(record.id)


class Staging(unittest.TestCase):
    def test_stage_is_pending(self):
        box = Outbox()
        rec = box.stage("order.created", b"{}")
        self.assertEqual(rec.status, PENDING)
        self.assertEqual(rec.attempts, 0)
        self.assertEqual(box.unsent(), [rec])

    def test_unsent_preserves_order(self):
        box = Outbox()
        a = box.stage("t", b"1")
        b = box.stage("t", b"2")
        self.assertEqual([r.id for r in box.unsent()], [a.id, b.id])

    # --- refusal ---
    def test_reject_empty_topic(self):
        with self.assertRaises(OutboxError):
            Outbox().stage("", b"x")

    def test_reject_whitespace_topic(self):
        with self.assertRaises(OutboxError):
            Outbox().stage("   ", b"x")

    def test_reject_non_bytes_payload(self):
        with self.assertRaises(OutboxError):
            Outbox().stage("t", "not bytes")

    def test_get_unknown_id(self):
        with self.assertRaises(OutboxError):
            Outbox().get("nope")


class Relaying(unittest.TestCase):
    def test_relay_publishes_and_marks_sent(self):
        box = Outbox()
        box.stage("t", b"1")
        box.stage("t", b"2")
        pub = AlwaysOk()
        summary = relay(box, pub, max_attempts=3)
        self.assertEqual(summary.sent, 2)
        self.assertEqual(len(pub.published), 2)
        self.assertEqual(box.counts()[SENT], 2)
        self.assertEqual(box.unsent(), [])

    def test_double_relay_does_not_republish(self):
        box = Outbox()
        box.stage("t", b"1")
        pub = AlwaysOk()
        relay(box, pub, max_attempts=3)
        summary2 = relay(box, pub, max_attempts=3)  # second pass
        self.assertEqual(summary2.sent, 0)
        self.assertEqual(len(pub.published), 1)  # published exactly once

    def test_failure_keeps_pending_and_counts_attempt(self):
        box = Outbox()
        rec = box.stage("t", b"1")
        summary = relay(box, AlwaysFail(), max_attempts=3)
        self.assertEqual(summary.failed, 1)
        self.assertEqual(box.get(rec.id).status, PENDING)
        self.assertEqual(box.get(rec.id).attempts, 1)

    def test_routes_to_dead_at_max_attempts(self):
        box = Outbox()
        rec = box.stage("t", b"1")
        fail = AlwaysFail()
        relay(box, fail, max_attempts=2)  # attempt 1
        summary = relay(box, fail, max_attempts=2)  # attempt 2 -> dead
        self.assertEqual(box.get(rec.id).status, DEAD)
        self.assertEqual(summary.dead, 1)
        self.assertEqual(box.unsent(), [])  # dead is no longer relayed

    def test_fail_then_succeed(self):
        box = Outbox()
        rec = box.stage("t", b"1")
        pub = FailThenOk(fail_times=2)
        relay(box, pub, max_attempts=5)  # fail 1
        relay(box, pub, max_attempts=5)  # fail 2
        relay(box, pub, max_attempts=5)  # success
        self.assertEqual(box.get(rec.id).status, SENT)
        self.assertEqual(pub.published, [rec.id])

    def test_batch_bounds_work(self):
        box = Outbox()
        for i in range(5):
            box.stage("t", str(i).encode())
        pub = AlwaysOk()
        summary = relay(box, pub, batch=2, max_attempts=3)
        self.assertEqual(summary.sent, 2)
        self.assertEqual(len(box.unsent()), 3)  # remainder still pending

    # --- refusal ---
    def test_reject_bad_batch(self):
        with self.assertRaises(OutboxError):
            relay(Outbox(), AlwaysOk(), batch=0)

    def test_reject_bad_max_attempts(self):
        with self.assertRaises(OutboxError):
            relay(Outbox(), AlwaysOk(), max_attempts=0)

    def test_mark_dead_cannot_be_sent(self):
        box = Outbox()
        rec = box.stage("t", b"1")
        relay(box, AlwaysFail(), max_attempts=1)  # -> dead immediately
        self.assertEqual(box.get(rec.id).status, DEAD)
        with self.assertRaises(OutboxError):
            box.mark_sent(rec.id)


class Durability(unittest.TestCase):
    def test_crash_between_write_and_send_is_recovered(self):
        # Simulate: state written + message staged, then the process "crashes"
        # before any relay runs. The staged record must survive and relay later.
        box = Outbox()
        rec = box.stage("order.created", b"payload")
        # ... crash (no relay ran) ... a fresh relay pass on restart:
        pub = AlwaysOk()
        summary = relay(box, pub, max_attempts=3)
        self.assertEqual(summary.sent, 1)
        self.assertEqual(pub.published, [rec.id])  # event not lost

    def test_at_least_once_with_idempotent_mark(self):
        box = Outbox()
        rec = box.stage("t", b"1")
        box.mark_sent(rec.id)
        box.mark_sent(rec.id)  # idempotent, no raise
        self.assertEqual(box.get(rec.id).status, SENT)


if __name__ == "__main__":
    unittest.main()
