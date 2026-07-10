# Reports (runtime evidence)

Saved outputs from Workshop runs - diagnostics, AI advice, repo audits, security
scans, and domain evidence. Long output is summarized in-world; the **full log
lands here**, so a run is auditable after the fact rather than lost to the scroll.

This is **Phase 7** of the [holodeck roadmap](../docs/holodeck/ROADMAP.md). The
folders below are created on demand as each producer ships; the contents are
**git-ignored** (generated, reproducible), while this README stays tracked.

Planned structure:

```
reports/
  tests/          # pytest runs
  diagnostics/    # lint / type / compile checks
  ai/             # Architect NPC exchanges (redacted)
  repo_audits/    # forge-audit / doctor scorecards
  ritual/         # dated startup/shutdown after-action records (make ritual)
  security/       # bandit / pip-audit output
  compliance/     # readiness evidence (dated + hashed)
  catalog/        # hardware-catalog snapshots
  finance/        # finance-track evidence
  records/        # records-track evidence
```

Rules (see [`../docs/holodeck/SAFETY.md`](../docs/holodeck/SAFETY.md)):
- outputs are **saved, not spammed**; the MUD shows a summary, the file holds the full log;
- compliance / finance / records evidence is **dated + hashed** and traceable to a commit;
- nothing here implies certification - it is readiness/evidence only.
