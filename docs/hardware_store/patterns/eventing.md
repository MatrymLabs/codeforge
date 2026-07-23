# Pattern family: Eventing (typed pub/sub)

*Eleventh family doc for the Hardware Store's pattern shelf. Harvested from the sibling repo
`codeforge-client`, where a typed event bus was proven first driving the MUD client's state reducer.
Another turn of the gap-analysis loop: a pattern the client exposed graduates back into the CodeForge
Hardware Store.*

## Provenance

- **Origin:** `harvested_pattern`. The client's transports translate bytes into typed events that a
  bus fans to the reducer and UI; that bus proved the behavior. This part reimplements the standard
  typed pub/sub idea in the forge voice. **No code was copied.**
- **Distinct from `parts/events`:** that part is in-world echo/broadcast; this is a general typed
  publish/subscribe with no game coupling.
- **License:** MIT · **owner:** MatrymLabs · **human review:** built and reviewed this session.

## The part: `typed-event-bus`

`parts/shelf/signal_bus.py` -- a `SignalBus`: `subscribe(signal_type, handler)` registers a handler for an
exact signal type; `publish(signal)` delivers it to that type's subscribers in subscription order;
`subscribers(type)` counts them. Signals are frozen dataclasses subclassing `Signal`.

**Invariants (tested):** a signal reaches only its exact-type subscribers; publishing with no
subscribers is a no-op; multiple handlers fire in subscription order; the subscriber count is honest.

## GAME-TO-PRACTICAL TRANSLATION

- **Game component:** a gate-`chime` (`parts/world/chime.py`).
- **Core behavior:** decouple a publisher from any number of independent reacting subscribers.
- **Game-specific presentation:** "The gate-chime rings for a merchant." per published arrival.
- **Reusable domain logic:** the whole `SignalBus` (game-free).
- **Practical applications:** webhook fan-out, audit trails, decoupled domain-event notification.
- **Security implications:** a raising handler propagates (synchronous by design); wrap handlers if a
  faulty subscriber must not break publication.
- **Testing implications:** exact-type routing, no-subscriber no-op, ordered dispatch.
- **Hardware Store candidate:** YES (stocked as `typed-event-bus`).

## Adapters (one core, two lives)

- **Game:** `parts/world/chime.py` -- the `chime` verb subscribes a chime that rings when a
  `TravellerArrived` world signal is published. Tick-reachable.
- **Practical:** `parts/notifier.py` -- a `Notifier` publishes an `OrderPlaced` domain event and fans
  it to every subscribed handler (audit, receipt, metrics).

## Evidence

- Tests: `tests/test_signal_bus.py` (core), `tests/test_chime.py` (game + tick),
  `tests/test_notifier.py` (practical + a one-core proof).
- Manifest: `docs/hardware/typed-event-bus.yaml`. Trace it: `make loop PART=typed-event-bus`.
- **Maturity: `beta`** -- proven in two contexts and tested; not `stable` (no wildcard subscriptions
  or async dispatch yet).

## Deferred (needs Josh's approval)

Wildcard/base-type subscriptions, a `once()` helper, and async dispatch are later slices.
