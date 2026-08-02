# Concurrency and thread-safety model

*The 2026-07-28 knowledge convergence audit named this the biggest documentation blind spot: the
TCP gateway is threaded over one shared world, yet the concurrency model lived only in a one-line
gateway docstring. The model itself is sound and already in the code; this doc writes it down so a
reviewer (or a future teammate) can see the guarantee, not infer it.*

## The model in one sentence

**Single-writer tick under one global lock:** every command from every connection runs through the
one engine tick (`handle_command`) while holding a single process-wide `TICK_LOCK`, so world state
is only ever mutated by one thread at a time. This is the classic MUD "one command at a time"
model, and it composes with Architecture Law 1 (state is canonical; text is a projection) and Law 4
(the tick is the only door state mutates through).

## How the transports funnel into one tick

Two transports serve players; both funnel through the same door under the same lock:

- **TCP gateway** (`adapters/gateway.py`): a `socketserver.ThreadingTCPServer` with
  `daemon_threads = True`, so each connection gets its own thread (thread-per-connection). Every
  call to `handle_command` is wrapped `with TICK_LOCK:` (`adapters/gateway.py:41` defines it; the tick
  sites are the login, register, passwd, and main-loop calls). Session lifecycle mutations
  (`SESSIONS[player_id] = session` on entry, `SESSIONS.pop(...)` on exit) are taken under the same
  lock.
- **Browser gateway** (`adapters/web_gateway.py`): FastAPI + WebSocket handlers on a single asyncio
  loop. It imports the **same** `TICK_LOCK` from the TCP gateway and acquires it around its own
  `handle_command` calls. One lock, two transports: a TCP thread and the web loop can never mutate
  the world at the same instant.

Because the asyncio handlers all live on one loop (cooperative, no preemption between `await`
points), the web side needs no lock for its own per-connection counters; a plain int is safe there.
The shared thing that needs protection is the world, and that is what `TICK_LOCK` protects.

## The two invariants that make it correct

1. **All writes are serialized.** No world-state mutation happens except inside `handle_command`,
   and `handle_command` runs under `TICK_LOCK`. So although many threads exist, world state has a
   single writer at any moment. Commands are atomic with respect to each other: a command either has
   fully applied or not started, never half-applied while another command observes the tear.
2. **The lock is never held during I/O.** `TICK_LOCK` wraps only the CPU-bound tick, never a socket
   send. In the main loop the pattern is: acquire the lock, run the tick, release, then send the
   response and push GMCP state. A slow or malicious client blocks only its own connection thread; it
   can never freeze the shared world by holding the lock across a stalled write. This is the property
   that keeps "one big lock" from becoming a denial-of-service surface.

## Reads and the GIL

- **Render reads may be lock-free.** Rendering is a projection (text), so a scene render that is not
  under the lock can at worst show slightly stale text, never corrupt state. Text is a projection;
  cosmetic eventual-consistency on a render is an accepted trade, not a bug.
- **The GIL is not the guarantee.** CPython's global interpreter lock makes individual bytecode
  operations atomic, which is why a lock-free integer counter or a single dict read is safe. It does
  NOT make a multi-step command atomic. `TICK_LOCK` is what makes a whole command atomic against
  other commands; the GIL only protects the primitive operations underneath. Do not confuse the two:
  removing `TICK_LOCK` and "trusting the GIL" would reintroduce mid-command races.

## Other locks (fine-grained, independent)

The gateway also keeps small, independent locks for connection accounting, separate from the world
lock so they never contend with the tick: a connection counter lock and a connection-ledger lock.
These guard bookkeeping (how many clients, the connect/disconnect record), not world state, and are
held only for their own tiny critical sections.

## Tradeoffs, honestly

- **Chosen:** correctness and simplicity over raw throughput. One command at a time caps concurrent
  world mutation to a single core's worth of tick, which is the right call at MUD scale (the tick is
  microseconds; the bottleneck is the network and the player, not the CPU). It eliminates an entire
  class of data-race bugs by construction.
- **The ceiling:** this model does not scale a single world across multiple processes or hosts. A
  sharded / instanced world (per-zone workers, or an actor model) is the path past one lock, and it
  is a **keel-level architecture decision** (ADR + Josh's sign-off), not a quiet refactor. It is
  deliberately deferred: the portfolio and the current player scale do not need it, and pretending a
  single-process demo is horizontally scaled would be a claim without correspondence.

## Rules for anyone touching this

- **Never mutate world state off the tick.** A background thread, a timer, or a driver that writes to
  the world dicts directly bypasses `TICK_LOCK` and breaks the single-writer invariant. Route it
  through `handle_command` (or a tick-internal call that already holds the lock).
- **Never hold `TICK_LOCK` across I/O** (a socket send, a network fetch, a `sleep`). Acquire it for
  the tick, release it, then do I/O.
- **A new transport is a thin caller.** Any future gateway acquires the same `TICK_LOCK` around the
  same `handle_command`; it does not get its own world or its own lock. One world, one door, one
  lock.
