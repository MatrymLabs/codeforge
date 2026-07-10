# Postmortem: <incident title>

*Blameless. The system let a human make a mistake; we fix the system, not the human. The
goal is prevention, not blame.*

| Field | Value |
|-------|-------|
| **Date** | <YYYY-MM-DD> |
| **Status** | draft · reviewed · closed |
| **Authors** | <who wrote this> |
| **Severity** | SEV1 (outage) · SEV2 (degraded) · SEV3 (minor) |

## Summary

<Two sentences: what broke, and the impact.>

## Impact

<Who/what was affected, for how long, and how badly. Be specific and honest.>

## Timeline (UTC)

| Time | Event |
|------|-------|
| <hh:mm> | <what happened> |
| <hh:mm> | <detected> |
| <hh:mm> | <mitigated> |
| <hh:mm> | <resolved> |

## Root cause

<The actual cause, traced to the system - not "someone forgot." Usually a missing gate,
an asymmetry, or an unsafe default that *allowed* the mistake.>

## Detection

<How we found out. If detection was slow or accidental, that's itself a finding.>

## Resolution

<What fixed it, and how we confirmed the fix.>

## What went well / what went wrong / where we got lucky

- **Went well:** <the guardrails that did their job>
- **Went wrong:** <the gaps that let it through>
- **Got lucky:** <what could have been worse but wasn't>

## Action items

| Action | Type | Owner | Status |
|--------|------|-------|--------|
| <preventive fix - make the mistake impossible> | prevent | <who> | done · open |
| <detection improvement> | detect | <who> | open |

## Lessons

<The one or two durable takeaways. What rule changed so this class of incident can't recur.>
