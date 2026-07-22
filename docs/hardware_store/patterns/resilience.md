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

## The part: `circuit-breaker`

`parts/circuit_breaker.py` -- the other half of the resilience family. It guards calls to a flaky
dependency: **CLOSED** it passes calls and counts consecutive failures; at a threshold it trips to
**OPEN** and rejects calls immediately (`CircuitOpen`, no waiting on a dead service); after a reset
timeout it moves to **HALF_OPEN** and lets one probe through -- success closes it, failure re-opens
it. Provenance: `independently_implemented_pattern` (Azure resilience pattern; no code copied).

**Composition, not reinvention:** the three-state lifecycle IS a state machine, so the breaker is
built ON the Hardware Store's own `state-machine` part (`parts/statemachine`) -- a part from a part.
The manufacturing loop's assembly stage shows that real dependency. The clock is injected, so the
trip and recovery are deterministic; a property test proves it opens exactly when a run of
`threshold` consecutive failures occurs.

- **Game:** `parts/relay.py` -- a `channel` verb draws power through a relay that trips after
  repeated surges, then cools and re-tests. Tick-reachable.
- **Practical:** `parts/service_breaker.py` -- `ServiceBreakers` keeps one breaker per named upstream
  so a broken payment gateway trips independently of a slow search service.
- Evidence: `tests/test_circuit_breaker.py`, `tests/test_relay.py`, `tests/test_service_breaker.py`;
  manifest `docs/hardware/circuit-breaker.yaml`; `make loop PART=circuit-breaker`. Maturity `beta`.

## The part: `deadline`

`parts/deadline.py` -- the timeout primitive of the resilience family, sized for a single-threaded
engine. A hard timeout interrupts a thread; a `Deadline(seconds, clock=...)` interrupts nothing. It
is a budget you POLL -- `remaining()`, `expired()`, or `check()` (which raises `DeadlineExceeded`) --
between steps, so a long job yields the moment its budget is spent. The clock is injected (default
`time.monotonic`), so the budget is deterministic under test.

**Composition:** `run_with_retries(fn, policy, deadline=Deadline(5.0))` caps the TOTAL wall-clock time
of a retry loop. Without it, retry bounds only the attempt COUNT; a slow dependency under a generous
`max_attempts` could still run for minutes. The deadline stops retrying the moment the budget is
spent and re-raises the last transient failure, unswallowed.

**Invariants (tested):** the budget clamps at zero (never negative, even if the clock steps back); a
zero budget is expired immediately; a negative / non-finite / bool / non-numeric budget fails loud at
construction (`DeadlineError`).

- **Practical:** a time-bounded retry (`run_with_retries(..., deadline=...)`) -- retry within an SLA,
  not just an attempt count.
- **General:** any long span whose caller must stay responsive -- a real-time timed challenge, a
  batch that must finish inside a window.
- Evidence: `tests/test_deadline.py`, plus the composition tests in `tests/test_retry.py`. Maturity `beta`.

## Deferred (needs Josh's approval)

For retry: jitter, a cancellation token, an async variant. For the circuit breaker: half-open
concurrency control, a rolling-window failure rate, and metrics hooks. For the deadline: a hard-timeout
variant that interrupts a thread, and propagating one deadline across nested calls (a context). All
deliberate later slices.
