# Pattern family: Rate limiting

*The first family doc for the Hardware Store's pattern shelf. Research basis:
"Full-Stack Design Patterns for CodeForge" (section 7, Rate Limiting / Throttling), which cites the
token-bucket and leaky-bucket algorithms as the standard implementations.*

## Provenance

- **Origin:** `independently_implemented_pattern`. The token-bucket algorithm is public-domain
  computer science (rate limiting by a refilling bucket of tokens). **No code was copied**; the
  behavior was reimplemented from the concept.
- **Source studied:** the token-bucket algorithm as surveyed in the research report (section 7) and
  standard references; no licensed source consulted.
- **Independently implemented:** the refill math, the injected-clock design, the `ThrottleDecision`
  interface, and both adapters.
- **License:** MIT · **owner:** MatrymLabs · **human review:** built and reviewed this session.

## The part: `token-bucket`

`parts/shelf/token_bucket.py` -- a `TokenBucket(rate, capacity, clock)` that refills at `rate` tokens/sec
up to `capacity`, and a `ThrottleDecision(allowed, tokens_left, retry_after, reason)`. `check()`
peeks; `consume()` takes tokens if available, else refuses with the exact `retry_after`. The clock is
**injected** (default `time.monotonic`), so behavior is deterministic and the conservation-law
property test can drive any timeline. Bad rate/capacity/cost fail loud (`RateLimitError`).

**Invariant (property-tested):** starting full, total consumed never exceeds
`capacity + rate * elapsed` -- the limiter can never be tricked past its configured rate.

## GAME-TO-PRACTICAL TRANSLATION

- **Game component:** a rate-limited `shout` (`parts/chat_throttle.py`).
- **Core behavior:** allow an action only if the bucket holds a token; refill over time.
- **Game-specific presentation:** "Your voice is hoarse. You can shout again in Ns."
- **Reusable domain logic:** the whole `TokenBucket` (game-free).
- **Practical applications:** API quotas, login-attempt throttling, email-send caps, job submission.
- **Required abstraction:** an injected clock and a cost-per-action; already in the core.
- **Adapters required:** a per-player game adapter; a per-key practical adapter.
- **Security implications:** it is a *policy decision only*; it never authenticates or hashes.
- **Testing implications:** deterministic via injected clock; property test on the rate invariant.
- **Hardware Store candidate:** YES (stocked as `token-bucket`).

## Adapters (one core, two lives)

- **Game:** `parts/chat_throttle.py` -- the `shout` verb, a burst of 3 refilling one every 20s.
  Tick-reachable (`handle_command(session, "shout ...")`).
- **Practical:** `parts/login_guard.py` -- `LoginGuard.attempt(key)`, a burst of 5 refilling one
  every 30s, per account or IP. A plain function, no game.

## Evidence

- Tests: `tests/test_token_bucket.py` (unit + property + fail-loud), `tests/test_chat_throttle.py`
  (game + tick), `tests/test_login_guard.py` (practical + a one-core proof).
- Manifest: `docs/hardware/token-bucket.yaml`. Trace it: `make loop PART=token-bucket`.
- **Maturity: `beta`** -- demonstrated in two contexts and tested, but not `stable` (no concurrency
  story yet; a distributed/thread-safe variant is a deferred juncture).

## Deferred (needs Josh's approval)

A Redis-backed distributed limiter (external service) and a thread-safe/async variant (concurrency)
are deliberate later junctures, not part of this slice.
