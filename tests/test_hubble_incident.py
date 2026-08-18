"""Test twin for kernel/hubble/incident.py (RD-2026-0002 #14).

Acceptance (a valid incident holds its fields; JSON round-trips), the corrective-controls point
(follow-up checks become pinnable controls; none pinned is itself the signal), the AI-specific
`hallucination` type, and refusal (bad severity/type/missing id/summary fail loud).
"""

from __future__ import annotations

import unittest

from kernel.hubble import incident as inc


def _incident(**overrides):
    base = dict(  # noqa: C408
        incident_id="INC-001",
        severity="sev2_high",
        type="regression",
        summary="a bad change reached main",
        follow_up_checks=("pin the n==0 case", "add a canary"),
    )
    base.update(overrides)
    return inc.Incident(**base)


class Validity(unittest.TestCase):
    def test_a_valid_incident_holds_its_fields(self):
        i = _incident()
        self.assertEqual(i.incident_id, "INC-001")
        self.assertEqual(len(i.follow_up_checks), 2)

    def test_hallucination_is_a_valid_ai_specific_type(self):
        self.assertEqual(_incident(type="hallucination").type, "hallucination")

    def test_containment_flags_default_false(self):
        i = _incident()
        self.assertFalse(i.rollback_executed)
        self.assertFalse(i.kill_switch_used)


class CorrectiveControls(unittest.TestCase):
    def test_follow_up_checks_become_pinnable_controls(self):
        controls = inc.corrective_controls(_incident())
        self.assertEqual(len(controls), 2)
        self.assertTrue(all(c.kind == "regression_test" for c in controls))
        self.assertTrue(all(c.incident_id == "INC-001" for c in controls))

    def test_no_follow_ups_yields_no_controls_the_absence_is_the_signal(self):
        self.assertEqual(inc.corrective_controls(_incident(follow_up_checks=())), [])


class RoundTrip(unittest.TestCase):
    def test_to_dict_from_dict_round_trips(self):
        i = _incident(
            type="hallucination", rollback_executed=True, root_causes=("ungrounded edit",)
        )
        self.assertEqual(inc.from_dict(inc.to_dict(i)), i)

    def test_from_dict_rejects_a_string_where_a_list_is_expected(self):
        d = inc.to_dict(_incident())
        d["root_causes"] = "not a list"
        with self.assertRaises(inc.IncidentError):
            inc.from_dict(d)


class Refusal(unittest.TestCase):
    def test_unknown_severity_fails_loud(self):
        with self.assertRaises(inc.IncidentError):
            _incident(severity="sev9_apocalypse")

    def test_unknown_type_fails_loud(self):
        with self.assertRaises(inc.IncidentError):
            _incident(type="gremlins")

    def test_missing_id_and_summary_fail_loud(self):
        with self.assertRaises(inc.IncidentError):
            _incident(incident_id="  ")
        with self.assertRaises(inc.IncidentError):
            _incident(summary="")

    def test_from_dict_missing_id_fails_loud(self):
        with self.assertRaises(inc.IncidentError):
            inc.from_dict({"severity": "sev1_critical", "type": "outage", "summary": "x"})

    def test_from_dict_on_a_non_mapping_fails_loud(self):
        with self.assertRaises(inc.IncidentError):
            inc.from_dict(["not", "a", "dict"])

    def test_from_dict_defaults_absent_lists_to_empty(self):
        i = inc.from_dict(
            {"incident_id": "X", "severity": "sev4_low", "type": "outage", "summary": "s"}
        )
        self.assertEqual(i.root_causes, ())
        self.assertEqual(i.follow_up_checks, ())


if __name__ == "__main__":
    unittest.main()
