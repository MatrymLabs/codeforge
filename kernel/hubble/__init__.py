"""CARD: hubble -- the clinical diagnostic lens: diagnose before you treat.

Hubble borrows clinical-workflow discipline (see docs/hubble/research_mapping.md): a code or
production issue is a CASE that passes through phases (intake, diagnostics, time-out, proposal,
review, sign-out, monitoring), and diagnosis comes BEFORE intervention. It composes CodeForge's
existing diagnostic surface (doctor, inspect, qa gate, observability) rather than duplicating it.

v1 (this slice) ships the diagnostic decision core: gather findings across dimensions, compute
confidence, and recommend proceed / revise / escalate / stop -- with NON-OVERRIDABLE escalation
on high-risk classes (security, sandbox, retrieval-grounding), the clinical "consult attending"
threshold. It advises; a human decides. No autonomy, no case-file, no replay lab yet.
"""
