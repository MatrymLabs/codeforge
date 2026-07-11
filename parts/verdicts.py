"""CARD: verdicts -- the shared readiness verdict vocabulary: one home for pass/fail/watch/n/a.

Before this, PASS/FAIL were re-declared independently in qualitygate, stewardship/gate, and
evolution/fitness, and frameup had to re-declare qualitygate's own "watch" verdict because it
was never exported (`frameup.py: _WATCH = "watch"  # qualitygate uses a bare "watch"...`). That
is exactly how a gate and the frame-up that reads its board drift apart. One source of truth for
the readiness words keeps them in lockstep.

Scope: this is the READINESS/QA vocabulary only. Routing decisions (proceed/revise/escalate/stop,
`parts/hubble`) and health colors (green/yellow/red, `parts/frameup`) are DISTINCT vocabularies
and stay with their own systems -- they answer different questions and should not be merged here.
"""

PASS = "pass"
FAIL = "fail"
WATCH = "watch"  # a soft gap: not a hard fail, but not clean either
NA = "n/a"  # not applicable (e.g. a prototype not built yet, so a file check is moot)
