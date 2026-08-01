"""Test twin for workflow_linter.py. Acceptance (each rule fires on a real risk) and
refusal (a clean, least-privilege, SHA-pinned workflow yields nothing; bad input raises).

Run:  python3 -m unittest test_workflow_linter
"""

from __future__ import annotations

import unittest

from parts.shelf.workflow_linter import (
    Budget,
    WorkflowLintError,
    lint_workflow,
    worst_severity,
)

_SHA = "a" * 40


def _rules(findings):
    return {f.rule for f in findings}


CLEAN = {
    "permissions": {"contents": "read"},
    "jobs": {
        "build": {
            "steps": [
                {"uses": f"actions/checkout@{_SHA}"},
                {"run": "make check"},
            ]
        }
    },
}


class Clean(unittest.TestCase):
    def test_least_privilege_pinned_workflow_is_clean(self):
        self.assertEqual(lint_workflow(CLEAN), [])
        self.assertIsNone(worst_severity([]))

    def test_local_action_needs_no_pin(self):
        doc = {
            "permissions": {"contents": "read"},
            "jobs": {"j": {"steps": [{"uses": "./.github/actions/x"}]}},
        }
        self.assertNotIn("unpinned-action", _rules(lint_workflow(doc)))


class Rules(unittest.TestCase):
    def test_no_permissions_flagged(self):
        doc = {"jobs": {"j": {"steps": []}}}
        self.assertIn("no-permissions", _rules(lint_workflow(doc)))

    def test_write_all_is_high(self):
        doc = {"permissions": "write-all", "jobs": {}}
        findings = lint_workflow(doc)
        self.assertIn("broad-permissions", _rules(findings))
        self.assertEqual(worst_severity(findings), "high")

    def test_top_level_write_scope_flagged(self):
        doc = {"permissions": {"contents": "write"}, "jobs": {}}
        self.assertIn("broad-permissions", _rules(lint_workflow(doc)))

    def test_unpinned_action_is_high(self):
        doc = {
            "permissions": {"contents": "read"},
            "jobs": {"j": {"steps": [{"uses": "actions/checkout@v4"}]}},
        }
        findings = lint_workflow(doc)
        self.assertIn("unpinned-action", _rules(findings))
        self.assertEqual(worst_severity(findings), "high")

    def test_branch_pin_is_unpinned(self):
        doc = {
            "permissions": {"contents": "read"},
            "jobs": {"j": {"steps": [{"uses": "foo/bar@main"}]}},
        }
        self.assertIn("unpinned-action", _rules(lint_workflow(doc)))

    def test_secret_sprawl(self):
        secrets = {f"S{i}": f"${{{{ secrets.S{i} }}}}" for i in range(10)}
        doc = {"permissions": {"contents": "read"}, "env": secrets, "jobs": {}}
        self.assertIn("secret-sprawl", _rules(lint_workflow(doc, budget=Budget(max_secrets=8))))

    def test_job_complexity(self):
        doc = {
            "permissions": {"contents": "read"},
            "jobs": {f"j{i}": {"steps": []} for i in range(15)},
        }
        self.assertIn("job-complexity", _rules(lint_workflow(doc, budget=Budget(max_jobs=12))))

    def test_step_complexity(self):
        doc = {"permissions": {"contents": "read"}, "jobs": {"j": {"steps": [{"run": "x"}] * 30}}}
        self.assertIn(
            "step-complexity", _rules(lint_workflow(doc, budget=Budget(max_steps_per_job=25)))
        )

    def test_budget_can_relax_pins(self):
        doc = {
            "permissions": {"contents": "read"},
            "jobs": {"j": {"steps": [{"uses": "foo/bar@v1"}]}},
        }
        self.assertNotIn(
            "unpinned-action", _rules(lint_workflow(doc, budget=Budget(require_sha_pins=False)))
        )


class Refusal(unittest.TestCase):
    def test_non_mapping_raises(self):
        with self.assertRaises(WorkflowLintError):
            lint_workflow(["not", "a", "mapping"])

    def test_missing_jobs_is_tolerated(self):
        # a workflow with no jobs key is odd but not a crash
        self.assertIsInstance(lint_workflow({"permissions": {"contents": "read"}}), list)


if __name__ == "__main__":
    unittest.main()
