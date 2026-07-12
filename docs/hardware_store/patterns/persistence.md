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

`parts/repository.py` -- `Repository[E, K]` is a typed, `@runtime_checkable` **Protocol** (the
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

- **Game component:** a per-player logbook (`parts/logbook.py`).
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

- **Game:** `parts/logbook.py` -- the `journal` verb records numbered entries into a per-player
  repository and lists them. Tick-reachable.
- **Practical:** `parts/asset_registry.py` -- `AssetRegistry` registers, finds, updates, and retires
  assets by id, storage-agnostic (any `Repository` works). Cousins: stock control, a document registry.

## Evidence

- Tests: `tests/test_repository.py` (unit + property + Protocol check), `tests/test_logbook.py`
  (game + tick), `tests/test_asset_registry.py` (practical + a one-core proof).
- Manifest: `docs/hardware/repository.yaml`. Trace it: `make loop PART=repository`.
- **Maturity: `beta`** -- demonstrated in two contexts and tested, but not `stable` (no database
  adapter, UnitOfWork, or transactions yet).

## Deferred (needs Josh's approval)

A SQLAlchemy-backed repository, a `UnitOfWork`/transaction boundary, and async CRUD are later slices.
Rewiring CodeForge's existing character/db persistence onto this part would change the persistence
architecture and is Josh's juncture, not part of this slice.
