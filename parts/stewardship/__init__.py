"""CARD: stewardship -- the Stewardship Gate: lean FWA (fraud/waste/abuse) reduction.

A layered assurance system for AI-assisted delivery (see docs/stewardship/research_mapping.md).
The doctrine: make changes traceable, permissions narrow, AI output provisional, policies
executable, risk visible, high-impact changes review-heavy, failures reusable, controls
measurable -- WITHOUT taxing ordinary low-risk work (the report's alert-fatigue warning).

v1 (this slice) ships the executable core: a typed ChangeDescriptor, a RiskRouter that routes
review depth by risk, and the StewardshipGate that composes a change's existing signals (tests,
SAST, secrets, dependency admission, AI disclosure) into one visible merge-eligibility verdict.
It never re-scans and never auto-merges: it advises; a human (and CI) still decides.
"""
