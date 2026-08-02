# Pattern family: Persistence

*Third family doc for the Hardware Store's pattern shelf. Research basis: "Full-Stack Design Patterns
for CodeForge" (section 5, Persistence / Repository Pattern), which cites Fowler's Repository as
"mediating between the domain and data mapping layers, acting like an in-memory collection."*

## Provenance

- **Origin:** `independently_implemented_pattern`. The Repository pattern (Fowler, *Patterns of
  Enterprise Application Architecture*) is a documented concept. **No code was copied**; the behavior
  was reimplemented from first principles.
- **Independently implemented:** the `Repository` Protocol, the in-memory store, the injected
  identity function, the error model, and both adapters.
- **License:** MIT · **owner:** MatrymLabs · **human review:** built and reviewed this session.

## The part: `repository`

`kernel/shelf/repository.py` -- `Repository[E, K]` is a typed, `@runtime_checkable` **Protocol** (the
replaceable storage boundary: `add`, `get`, `require`, `update`, `remove`, `list`, `count`).
`InMemoryRepository[E, K]` is the dependency-free, dict-backed implementation. It is
**identity-agnostic**: entities need no base class and no `.id`; an injected `key_of` reads each
entity's key, so one repository stores anything. Misuse fails loud (`DuplicateKey`, `NotFound`).

**Invariants (tested, incl. property-based):** add-then-get round-trips; no accidental data loss
(add all, get all unchanged, remove all, count is zero); a duplicate key is refused; the in-memory
repo satisfies the `Repository` Protocol. **The domain stays independent of storage** -- a real
database repository is a later adapter satisfying the same Protocol, and the domain code (e.g. the
asset registry) does not change.

## GAME-TO-PRACTICAL TRANSLATION

- **Game component:** a per-player logbook (`kernel/logbook.py`).
- **Core behavior:** store and retrieve entities by identity, behind a collection interface.
- **Game-specific presentation:** "Logged (#3): ..." / a numbered listing.
- **Reusable domain logic:** the whole `Repository` + `InMemoryRepository` (game-free).
- **Practical applications:** asset/records/document registries, ledgers, case stores.
- **Required abstraction:** a Protocol boundary + an injected identity function; already in the core.
- **Adapters required:** a game verb; a practical registry class.
- **Security implications:** no I/O; a database adapter must not leak raw queries (parameterized only).
- **Testing implications:** CRUD round-trips; property test on conservation (no data loss).
- **Hardware Store candidate:** YES (stocked as `repository`).

## Adapters (one core, two lives)

- **Game:** `kernel/logbook.py` -- the `journal` verb records numbered entries into a per-player
  repository and lists them. Tick-reachable.
- **Practical:** `kernel/asset_registry.py` -- `AssetRegistry` registers, finds, updates, and retires
  assets by id, storage-agnostic (any `Repository` works). Cousins: stock control, a document registry.

## Evidence

- Tests: `tests/test_repository.py` (unit + property + Protocol check), `tests/test_logbook.py`
  (game + tick), `tests/test_asset_registry.py` (practical + a one-core proof).
- Manifest: `docs/hardware/repository.yaml`. Trace it: `make loop PART=repository`.
- **Maturity: `beta`** -- demonstrated in two contexts and tested, but not `stable` (no database
  adapter, UnitOfWork, or transactions yet).

## The part: `cache-aside`

`kernel/shelf/cache_aside.py` -- the read-path companion to the repository: read a value fast without
re-hitting the source of truth every time, while bounding how stale that value can get. On a read,
`get(key, loader)` returns the cached value if it is a hit within its TTL; on a miss or an expired
entry it calls `loader` (the source of truth), stores the result with a fresh expiry, and returns
it. This is the documented cache-aside (lazy-loading) pattern used with Redis.

The discipline it enforces (the optimization ethos: "cache only when invalidation is clear") is that
every value has **two** eviction levers, both first-class: a **TTL** (staleness bounded by time) and
an explicit **`invalidate(key)`** (a known change evicts immediately rather than waiting out the
clock). It tracks hit/miss stats so the cache's value is measured, not assumed.

**Invariants (tested, with a fake clock -- no real sleep):** a hit avoids the loader (proven by a
call count); an entry past its TTL reloads; the TTL boundary is strict (at exactly the TTL it is
expired); `invalidate` evicts before the TTL; a loader that raises caches nothing (a failed load is
never a cached failure); a non-positive TTL fails loud.

- **Practical:** cache a slow query, an expensive computation, or a third-party lookup behind a
  bounded TTL, invalidating on write.
- **Composition:** it sits in front of the `repository` (read-through), and pairs with `token-bucket`
  rate limiting and `rank-gate` RBAC to form the read side of a typical service.
- **Honest limit:** in-memory and single-process; a networked deployment maps the same contract onto
  Redis (`GET` -> on miss load + `SETEX`, and `DEL` for `invalidate`).
- Evidence: `tests/test_cache_aside.py`. Maturity `shipped`.

## Deferred (needs Josh's approval)

A SQLAlchemy-backed repository, a `UnitOfWork`/transaction boundary, and async CRUD are later slices.
Rewiring CodeForge's existing character/db persistence onto this part would change the persistence
architecture and is Josh's juncture, not part of this slice.
