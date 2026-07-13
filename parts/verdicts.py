"""CARD: verdicts -- one home for the readiness verdict words (pass/fail/watch/n/a + the ARC tier).

Before this, PASS/FAIL were re-declared independently in qualitygate, stewardship/gate, and
evolution/fitness, and frameup had to re-declare qualitygate's own "watch" verdict because it
was never exported (`frameup.py: _WATCH = "watch"  # qualitygate uses a bare "watch"...`). That
is exactly how a gate and the frame-up that reads its board drift apart. One source of truth for
the readiness words keeps them in lockstep.

Scope: this is the READINESS/QA vocabulary only. Routing decisions (proceed/revise/escalate/stop,
`parts/hubble`) and health colors (green/yellow/red, `parts/frameup`) are DISTINCT vocabularies
and stay with their own systems -- they answer different questions and should not be merged here.
"""

PASS = "pass"  # nosec B105 - a readiness verdict word, not a password (bandit heuristic false positive)
FAIL = "fail"
WATCH = "watch"  # a soft gap: not a hard fail, but not clean either
NA = "n/a"  # not applicable (e.g. a prototype not built yet, so a file check is moot)

# The ARC readiness tier (Assurance/Readiness/Control). Re-declared verbatim in arc, arc_ledger,
# and change_ledger before this - the exact drift verdicts.py exists to prevent. One home now.
READY = "ready"
WATCHLIST = "watchlist"  # any WATCHLIST or MISSING holds the overall verdict off READY
BLOCKED = "blocked"  # any BLOCKED blocks the overall verdict
MISSING = "missing"  # no wired source / never ran: MISSING is never a pass
ARC_STATUSES = (READY, WATCHLIST, BLOCKED, MISSING)
