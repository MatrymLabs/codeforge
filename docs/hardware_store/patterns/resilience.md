# Pattern family: Resilience

*Second family doc for the Hardware Store's pattern shelf. Research basis: "Full-Stack Design
Patterns for CodeForge" (section 9, Retry / Exponential Backoff; section 10, Circuit Breaker). This
doc covers the retry/backoff part; the circuit breaker is a later slice in the same family.*

## Provenance

- **Origin:** `independently_implemented_pattern`. Retry with exponential backoff is a standard
  resilience pattern (AWS Prescriptive Guidance, "retry with backoff"). **No code was copied**; the
  behavior was reimplemented from the concept.
- **Independently implemented:** the policy (attempt budget, transient-exception filter, capped
  exponential schedule), the injected-sleep runner, the attempt history, and both adapters.
- **License:** MIT · **owner:** MatrymLabs · **human review:** built and reviewed this session.

## The part: `retry-policy`

`parts/retry.py` -- a frozen `RetryPolicy(max_attempts, base_delay, factor, max_delay, retry_on)`
with `is_transient(exc)` and `delay_for(attempt)` (capped exponential backoff), and
`run_with_retries(fn, policy, *, sleep, on_retry)`. It **retries transient failures**, **re-raises a
permanent one immediately**, and after the last attempt **re-raises the final failure (never
swallowed)**. The **sleep is injected** (default `time.sleep`), so the schedule and attempt count are
deterministic; a bad policy fails loud (`RetryError`).

**Invariants (tested, incl. property-based):** the callable is never called more than
`max_attempts` times; there is exactly one backoff between each pair of tries; a permanent failure is
not retried; the final failure is re-raised, not swallowed. **Idempotency is the caller's
responsibility** -- the part retries, it does not make an operation safe to repeat.

## GAME-TO-PRACTICAL TRANSLATION

- **Game component:** an auto-retried `calibrate` (`parts/calibrate.py`).
- **Core behavior:** try an operation; on a transient failure, back off and try again, up to a budget.
- **Game-specific presentation:** "Aligned on attempt 3." / "Failed after 4 attempts."
- **Reusable domain logic:** the whole `RetryPolicy` + `run_with_retries` (game-free).
- **Practical applications:** flaky HTTP/API calls, database calls, any transient-fault integration.
- **Required abstraction:** an injected sleep and a transient-exception filter; already in the core.
- **Adapters required:** a game verb; a practical caller that records an audit trail.
- **Security implications:** bounded retries (no thundering herd); permanent auth failures never retried.
- **Testing implications:** deterministic via injected sleep; property test on the attempt/backoff counts.
- **Hardware Store candidate:** YES (stocked as `retry-policy`).

## Adapters (one core, two lives)

- **Game:** `parts/calibrate.py` -- the `calibrate` verb retries a flaky instrument. The tick is
  synchronous, so it uses a **zero delay** (a real backoff would block every player); the delay
  behavior is proven in the core + practical tests.
- **Practical:** `parts/resilient_call.py` -- `ResilientCaller(policy).call(fn)` retries an unreliable
  callable and keeps an `Attempt` **history** (the audit trail resilience needs).

## Evidence

- Tests: `tests/test_retry.py` (unit + property + fail-loud), `tests/test_calibrate.py` (game + tick),
  `tests/test_resilient_call.py` (practical + a one-core proof).
- Manifest: `docs/hardware/retry-policy.yaml`. Trace it: `make loop PART=retry-policy`.
- **Maturity: `beta`** -- demonstrated in two contexts and tested, but not `stable` (no jitter,
  cancellation, or async yet -- deferred junctures).

## Deferred (needs Josh's approval)

Jitter, a deadline/cancellation token, an async variant, and a **Circuit Breaker** (the other half of
this family) are deliberate later slices, not part of this one.
