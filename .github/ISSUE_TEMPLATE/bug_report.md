---
name: Bug report
about: Report a defect so it can be reproduced, fixed, and pinned by a test
title: "bug: "
labels: ["bug"]
---

## What happened

A clear, one-sentence description of the defect.

## Steps to reproduce

1. ...
2. ...
3. ...

## Expected vs actual

- **Expected:**
- **Actual:**

## Evidence

Command output, logs, or a failing gate (paste the real output, not a summary). If the tick
is involved, include the exact command text passed to `handle_command`.

## Environment

- Branch / commit:
- How run (`make serve`, `codeforge play`, Docker, live demo):
- OS / Python version:

## Notes (optional)

Hostile-case reminder: mixed case, symbols, and near-misses have hidden real bugs here
before. If the input had any of those, say so.
