"""Test twin for kernel/shelf/dead_letter.py: the dead-letter queue.

Acceptance AND refusal cases, plus a composition test that connects a real producer and consumer:
a flaky handler wrapped with retry that buries a permanently-failing message, then recovers it on
replay once the cause is fixed (the at-least-once family: retry + idempotency + dead-letter).
"""

from __future__ import annotations

import pytest

from kernel.shelf.dead_letter import DeadLetterError, DeadLetterQueue

# --- Acceptance ------------------------------------------------------------------------------


def test_bury_and_inspect() -> None:
    dlq: DeadLetterQueue[str] = DeadLetterQueue()
    letter = dlq.bury("msg-1", "downstream timeout", attempts=3)
    assert letter.message == "msg-1"
    assert letter.reason == "downstream timeout"
    assert letter.attempts == 3
    assert len(dlq) == 1
    assert dlq.is_empty() is False
    assert dlq.letters()[0].message == "msg-1"


def test_bounded_drops_oldest_and_counts_it() -> None:
    dlq: DeadLetterQueue[int] = DeadLetterQueue(capacity=2)
    dlq.bury(1, "x")
    dlq.bury(2, "x")
    dlq.bury(3, "x")  # over capacity -> oldest (1) is dropped, counted
    assert [dl.message for dl in dlq.letters()] == [2, 3]  # most recent kept
    assert dlq.dropped == 1
    assert len(dlq) == 2


def test_letters_snapshot_is_immutable() -> None:
    dlq: DeadLetterQueue[int] = DeadLetterQueue()
    dlq.bury(1, "x")
    snap = dlq.letters()
    dlq.bury(2, "x")
    assert len(snap) == 1  # the earlier snapshot is unchanged
    assert isinstance(snap, tuple)


def test_replay_recovers_accepted_and_keeps_failing() -> None:
    dlq: DeadLetterQueue[str] = DeadLetterQueue()
    dlq.bury("good", "was down", attempts=2)
    dlq.bury("bad", "was down", attempts=2)

    def handler(msg: str) -> None:
        if msg == "bad":
            raise RuntimeError("still broken")

    result = dlq.replay(handler)
    assert result.recovered == ("good",)
    assert len(result.still_dead) == 1
    assert result.still_dead[0].message == "bad"
    assert result.still_dead[0].attempts == 3  # incremented
    assert result.still_dead[0].reason == "still broken"  # reason updated to the new failure
    # The queue now holds only the still-dead letter.
    assert [dl.message for dl in dlq.letters()] == ["bad"]


def test_replay_of_empty_queue_is_noop() -> None:
    dlq: DeadLetterQueue[int] = DeadLetterQueue()
    result = dlq.replay(lambda m: None)
    assert result.recovered == () and result.still_dead == ()


# --- Refusal ---------------------------------------------------------------------------------


@pytest.mark.parametrize("cap", [0, -1])
def test_nonpositive_capacity_refused(cap: int) -> None:
    with pytest.raises(DeadLetterError):
        DeadLetterQueue(capacity=cap)


def test_bool_capacity_refused() -> None:
    # bool is an int subtype (mypy accepts it), but True is not a valid capacity at runtime.
    with pytest.raises(DeadLetterError):
        DeadLetterQueue(capacity=True)


@pytest.mark.parametrize("reason", ["", "   "])
def test_empty_reason_refused(reason: str) -> None:
    dlq: DeadLetterQueue[int] = DeadLetterQueue()
    with pytest.raises(DeadLetterError):
        dlq.bury(1, reason)


def test_negative_attempts_refused() -> None:
    dlq: DeadLetterQueue[int] = DeadLetterQueue()
    with pytest.raises(DeadLetterError):
        dlq.bury(1, "x", attempts=-1)


# --- Composition: the at-least-once consumer (retry -> dead-letter -> replay) -----------------


def test_at_least_once_consumer_flow() -> None:
    # A message that fails every attempt is retried a bounded number of times, then buried.
    dlq: DeadLetterQueue[str] = DeadLetterQueue()
    world_is_broken = {"state": True}

    def process(msg: str) -> None:
        if world_is_broken["state"]:
            raise RuntimeError("downstream 503")

    def consume(msg: str, *, max_attempts: int = 3) -> None:
        last_reason = ""
        for _attempt in range(1, max_attempts + 1):
            try:
                process(msg)
                return  # success  # noqa: TRY300
            except Exception as exc:  # noqa: BLE001 - the consumer decides retry vs bury
                last_reason = str(exc)
        dlq.bury(msg, last_reason, attempts=max_attempts)  # retries exhausted -> dead-letter

    consume("order-42")
    assert len(dlq) == 1
    assert dlq.letters()[0].attempts == 3
    assert dlq.letters()[0].reason == "downstream 503"

    # The cause is fixed; replay redrives the buried message and it recovers.
    world_is_broken["state"] = False
    result = dlq.replay(process)
    assert result.recovered == ("order-42",)
    assert dlq.is_empty() is True
