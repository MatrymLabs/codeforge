"""Test twin for jobqueue.py. Acceptance AND refusal cases, including the
visibility-lease redelivery and fencing-token properties the queue exists to
guarantee.

Run:  python3 -m unittest test_jobqueue   (or pytest test_jobqueue.py)
"""

from __future__ import annotations

import unittest

from parts.shelf.jobqueue import (
    AVAILABLE,
    CLAIMED,
    DEAD,
    Job,
    JobQueue,
    JobQueueError,
    StaleLease,
)


class FakeClock:
    """A hand-advanced clock so lease expiry is deterministic."""

    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


class Enqueue(unittest.TestCase):
    def test_enqueue_returns_id_and_is_available(self):
        q = JobQueue()
        jid = q.enqueue(b"work")
        self.assertTrue(jid)
        self.assertEqual(q.stats()[AVAILABLE], 1)

    def test_reject_non_bytes(self):
        with self.assertRaises(JobQueueError):
            JobQueue().enqueue("not bytes")

    def test_reject_bad_max_attempts(self):
        with self.assertRaises(JobQueueError):
            JobQueue(max_attempts=0)


class ClaimAck(unittest.TestCase):
    def test_claim_then_ack(self):
        q = JobQueue()
        q.enqueue(b"a")
        job = q.claim(lease=30)
        assert job is not None
        self.assertIsInstance(job, Job)
        self.assertEqual(q.stats()[CLAIMED], 1)
        q.ack(job.id, job.lease_token)
        self.assertEqual(q.stats(), {AVAILABLE: 0, CLAIMED: 0, DEAD: 0})

    def test_claim_none_when_empty(self):
        self.assertIsNone(JobQueue().claim(lease=30))

    def test_claim_none_when_all_claimed(self):
        q = JobQueue()
        q.enqueue(b"a")
        q.claim(lease=30)
        self.assertIsNone(q.claim(lease=30))  # the only job is already claimed

    def test_fifo_order(self):
        q = JobQueue()
        q.enqueue(b"first")
        q.enqueue(b"second")
        self.assertEqual(q.claim(lease=30).payload, b"first")
        self.assertEqual(q.claim(lease=30).payload, b"second")

    def test_reject_bad_lease(self):
        with self.assertRaises(JobQueueError):
            JobQueue().claim(lease=0)

    def test_ack_unknown_job(self):
        with self.assertRaises(JobQueueError):
            JobQueue().ack("nope", 1)


class VisibilityAndFencing(unittest.TestCase):
    def test_expired_lease_is_reclaimed_and_redelivered(self):
        clock = FakeClock()
        q = JobQueue(clock=clock)
        q.enqueue(b"a")
        job = q.claim(lease=30)
        assert job is not None
        clock.advance(31)  # the worker "crashed"; its lease elapsed
        self.assertEqual(q.reclaim_expired(), 1)
        self.assertEqual(q.stats()[AVAILABLE], 1)  # redelivered
        again = q.claim(lease=30)
        self.assertEqual(again.id, job.id)

    def test_stale_worker_ack_is_fenced_after_reclaim(self):
        clock = FakeClock()
        q = JobQueue(clock=clock)
        q.enqueue(b"a")
        first = q.claim(lease=30)
        assert first is not None
        clock.advance(31)
        q.reclaim_expired()  # fences: mints a new token
        # the original (crashed-then-revived) worker tries to ack with its old token
        with self.assertRaises(StaleLease):
            q.ack(first.id, first.lease_token)

    def test_not_yet_expired_is_not_reclaimed(self):
        clock = FakeClock()
        q = JobQueue(clock=clock)
        q.enqueue(b"a")
        q.claim(lease=30)
        clock.advance(10)
        self.assertEqual(q.reclaim_expired(), 0)

    def test_reclaimed_job_new_worker_can_ack(self):
        clock = FakeClock()
        q = JobQueue(clock=clock)
        q.enqueue(b"a")
        q.claim(lease=30)
        clock.advance(31)
        q.reclaim_expired()
        second = q.claim(lease=30)
        q.ack(second.id, second.lease_token)  # the live worker's token is current
        self.assertEqual(q.stats()[AVAILABLE], 0)


class RetryAndDead(unittest.TestCase):
    def test_nack_retries(self):
        q = JobQueue(max_attempts=3)
        q.enqueue(b"a")
        job = q.claim(lease=30)
        self.assertEqual(q.nack(job.id, job.lease_token), AVAILABLE)
        again = q.claim(lease=30)
        self.assertEqual(again.attempts, 1)  # attempt counted

    def test_dead_at_max_attempts(self):
        q = JobQueue(max_attempts=2)
        q.enqueue(b"a")
        job = q.claim(lease=30)
        q.nack(job.id, job.lease_token)  # attempt 1 -> available
        job2 = q.claim(lease=30)
        self.assertEqual(q.nack(job2.id, job2.lease_token), DEAD)  # attempt 2 -> dead
        self.assertEqual(q.stats()[DEAD], 1)
        self.assertIsNone(q.claim(lease=30))  # dead is not claimable

    def test_nack_stale_token_fenced(self):
        clock = FakeClock()
        q = JobQueue(clock=clock)
        q.enqueue(b"a")
        first = q.claim(lease=30)
        clock.advance(31)
        q.reclaim_expired()
        with self.assertRaises(StaleLease):
            q.nack(first.id, first.lease_token)


if __name__ == "__main__":
    unittest.main()
