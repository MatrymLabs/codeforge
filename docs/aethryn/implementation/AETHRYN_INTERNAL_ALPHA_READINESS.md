# Aethryn / CodeForge Internal Alpha Readiness

**As of:** 2026-08-07
**Status:** Internal alpha candidate — local stack is exercising the real client, gateway,
Seed, and assembled engine. This is not a production or launch claim.

## Green evidence

| Surface | Evidence | Result |
| --- | --- | --- |
| Client | `QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q` in `codeforge-client-unified` | `1339 passed, 4 skipped` |
| Gateway smoke | `make smoke` | `66/66` end-to-end steps |
| Domain / persistence alpha matrix | Aethryn corpus, economy, trade, shop, crafting, auction, recovery, play smoke, and playthrough suites | `75 passed` |
| Live gateway alpha subset | Aethryn entry, movement, combat, restart, session authority, and research mount paths | `5 passed, 2 skipped` |
| Engine consistency gates | census, emitter parity, truth, frame-up, linker, and registry suites | `78 passed` |
| EvidenceGate | `python -m kernel.evidence_gate` | `ALL VERIFIED` |
| Frame-up | live composed readiness view | `GREEN` |

The smoke path covers First Forge, Aethryn/Veridia, multiplayer presence/chat, and the Spine
travel route through the Voidscar. The research fixture is mounted locally and projects through
the gateway into the client parser.

## Remaining alpha acceptance work

These are not local code failures, but they remain before calling the stack broadly ready:

- Run a human accessibility witness: screen reader navigation and real reduced-motion behavior.
- Run a sustained load/soak pass against the gateway and record resource/error telemetry.
- Perform a real external backup/restore drill and capture recovery evidence.
- Mount the research source in the deployment environment, not only the local `.seedlab` mount.
- Execute one controlled hosted deployment with the required cloud credentials and verify health,
  reconnect, persistence, and rollback behavior.

## Broad-suite note

The bounded whole-engine command collected 5,395 selected items but reached its 420-second bound
at approximately 73% without producing a final report. It must be partitioned or given a longer
CI budget before it can serve as a whole-repository green gate. The focused alpha matrix above is
the current acceptance gate for local internal testing.
