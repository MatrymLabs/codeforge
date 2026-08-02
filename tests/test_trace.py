"""Test twin for trace.py. Acceptance AND refusal cases, including hostile input
(uppercase hex, all-zero ids, truncation, non-hex, version ff, non-string).

Runs standalone with no project config:  python -m pytest test_trace.py
                                     or:  python -m unittest test_trace
"""

from __future__ import annotations

import re
import unittest
from dataclasses import FrozenInstanceError

from kernel.shelf.trace import (
    FLAG_SAMPLED,
    Trace,
    TraceError,
    child_span,
    continue_trace,
    current,
    enter_span,
    parse_traceparent,
    start_trace,
    use_trace,
)


def counting_rng():
    """A deterministic id factory: 01, 02, 03 ... zero-padded to the byte count.

    Injected so tests can pin ids instead of drawing entropy.
    """
    counter = {"n": 0}

    def rng(n_bytes: int) -> str:
        counter["n"] += 1
        return f"{counter['n']:0{n_bytes * 2}x}"

    return rng


class TraceConstruction(unittest.TestCase):
    def test_start_trace_mints_valid_ids(self):
        t = start_trace(rng=counting_rng())
        self.assertEqual(len(t.trace_id), 32)
        self.assertEqual(len(t.span_id), 16)
        self.assertIsNone(t.parent_span_id)
        self.assertTrue(t.sampled)

    def test_default_rng_produces_distinct_traces(self):
        a, b = start_trace(), start_trace()
        self.assertNotEqual(a.trace_id, b.trace_id)
        self.assertNotEqual(a.span_id, b.span_id)

    def test_trace_is_frozen(self):
        t = start_trace(rng=counting_rng())
        with self.assertRaises(FrozenInstanceError):
            t.trace_id = "x" * 32

    # --- refusal cases ---
    def test_reject_short_trace_id(self):
        with self.assertRaises(TraceError):
            Trace(trace_id="abc", span_id="0" * 15 + "1")

    def test_reject_uppercase_hex(self):
        with self.assertRaises(TraceError):
            Trace(trace_id="A" * 32, span_id="0" * 15 + "1")

    def test_reject_non_hex(self):
        with self.assertRaises(TraceError):
            Trace(trace_id="g" * 32, span_id="0" * 15 + "1")

    def test_reject_all_zero_trace_id(self):
        with self.assertRaises(TraceError):
            Trace(trace_id="0" * 32, span_id="0" * 15 + "1")

    def test_reject_all_zero_span_id(self):
        with self.assertRaises(TraceError):
            Trace(trace_id="0" * 31 + "1", span_id="0" * 16)

    def test_reject_all_zero_parent(self):
        with self.assertRaises(TraceError):
            Trace(trace_id="0" * 31 + "1", span_id="0" * 15 + "1", parent_span_id="0" * 16)


class Traceparent(unittest.TestCase):
    def test_roundtrip(self):
        t = start_trace(rng=counting_rng())
        parsed = parse_traceparent(t.traceparent())
        self.assertEqual(parsed.trace_id, t.trace_id)
        self.assertEqual(parsed.span_id, t.span_id)

    def test_format_shape(self):
        t = start_trace(rng=counting_rng())
        self.assertRegex(t.traceparent(), re.compile(r"\A00-[0-9a-f]{32}-[0-9a-f]{16}-01\Z"))

    def test_unsampled_flag(self):
        t = start_trace(rng=counting_rng(), sampled=False)
        self.assertTrue(t.traceparent().endswith("-00"))
        self.assertFalse(parse_traceparent(t.traceparent()).sampled)

    def test_sampled_flag_parsed(self):
        self.assertTrue(parse_traceparent("00-" + "a" * 32 + "-" + "b" * 16 + "-01").sampled)
        self.assertEqual(FLAG_SAMPLED, 0x01)

    # --- refusal cases ---
    def test_reject_non_string(self):
        with self.assertRaises(TraceError):
            parse_traceparent(1234)

    def test_reject_empty(self):
        with self.assertRaises(TraceError):
            parse_traceparent("")

    def test_reject_truncated(self):
        with self.assertRaises(TraceError):
            parse_traceparent("00-" + "a" * 32 + "-" + "b" * 16)  # missing flags

    def test_reject_uppercase_header(self):
        with self.assertRaises(TraceError):
            parse_traceparent("00-" + "A" * 32 + "-" + "b" * 16 + "-01")

    def test_reject_version_ff(self):
        with self.assertRaises(TraceError):
            parse_traceparent("ff-" + "a" * 32 + "-" + "b" * 16 + "-01")

    def test_reject_all_zero_trace_in_header(self):
        with self.assertRaises(TraceError):
            parse_traceparent("00-" + "0" * 32 + "-" + "b" * 16 + "-01")


class Propagation(unittest.TestCase):
    def test_continue_makes_child_under_inbound_span(self):
        rng = counting_rng()
        edge = start_trace(rng=rng)
        local = continue_trace(edge.traceparent(), rng=rng)
        self.assertEqual(local.trace_id, edge.trace_id)  # same trace
        self.assertEqual(local.parent_span_id, edge.span_id)  # inbound is parent
        self.assertNotEqual(local.span_id, edge.span_id)  # new span

    def test_child_span_keeps_trace_changes_span(self):
        rng = counting_rng()
        parent = start_trace(rng=rng)
        kid = child_span(parent, rng=rng)
        self.assertEqual(kid.trace_id, parent.trace_id)
        self.assertEqual(kid.parent_span_id, parent.span_id)
        self.assertNotEqual(kid.span_id, parent.span_id)

    def test_continue_rejects_bad_header(self):
        with self.assertRaises(TraceError):
            continue_trace("not-a-traceparent")


class Ambient(unittest.TestCase):
    def test_current_defaults_none(self):
        self.assertIsNone(current())

    def test_use_trace_sets_and_restores(self):
        t = start_trace(rng=counting_rng())
        self.assertIsNone(current())
        with use_trace(t):
            self.assertIs(current(), t)
        self.assertIsNone(current())

    def test_enter_span_fresh_when_no_current(self):
        with enter_span(rng=counting_rng()) as span:
            self.assertIsNotNone(current())
            self.assertIsNone(span.parent_span_id)
        self.assertIsNone(current())

    def test_enter_span_children_current(self):
        rng = counting_rng()
        root = start_trace(rng=rng)
        with use_trace(root):
            with enter_span(rng=rng) as span:
                self.assertEqual(span.trace_id, root.trace_id)
                self.assertEqual(span.parent_span_id, root.span_id)
            self.assertIs(current(), root)  # restored to the gateway span

    def test_log_fields(self):
        t = start_trace(rng=counting_rng())
        self.assertEqual(t.log_fields(), {"trace_id": t.trace_id, "span_id": t.span_id})


if __name__ == "__main__":
    unittest.main()
