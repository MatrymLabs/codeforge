# Runbook: <procedure name>

*A runbook is a checklist for a known operation — so it runs the same way at 3pm and at
3am, by anyone. Copy this file, fill it, keep it beside the system it operates.*

| Field | Value |
|-------|-------|
| **System** | <what this operates — e.g. the demo gateway, the ritual> |
| **Owner** | <who maintains this runbook> |
| **Last reviewed** | <YYYY-MM-DD> |
| **Risk** | low · medium · high |

## When to use this

<The trigger — the symptom, alert, or scheduled event that sends someone here.>

## Preconditions

- [ ] <access / tools / branch state needed before starting>
- [ ] <e.g. `.venv` active, on a clean tree, CI green>

## Procedure

1. <step — exact command, not a description>
   ```bash
   <command>
   ```
2. <step>
3. <step>

## Verify it worked

- [ ] <the observable signal that confirms success — a gate, a log line, a health check>
- [ ] <e.g. `make smoke` passes, `:4000` responds, CI is green>

## Rollback

<How to undo, if the procedure fails or makes things worse. Exact steps.>
```bash
<rollback command>
```

## Escalate if

- <condition that means "stop and get help" — data loss risk, unclear state>
- The rollback itself fails.

## Related

- <linked runbooks, postmortems, dashboards, docs>
