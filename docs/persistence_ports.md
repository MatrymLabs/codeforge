# Persistence Ports (the assimilation pattern, batch 1)

This is the first extracted boundary of the **assimilated Python platform** campaign: a worked,
tested example of the doctrine in `docs/technology_intake.md`. Python owns the architecture; a
framework (SQLAlchemy) is kept behind a narrow Python contract, connected by an adapter, provable by
tests, and removable without touching the domain.

## The rule it enforces

A domain module in `parts/world/` describes the *game*, not the *database*. When SQLAlchemy `select`,
sessions, and ORM rows appear inside a domain module, the framework has leaked past its seam
(`parts/world/db.py`): the module can no longer be read, tested, or reused without the framework, and
the game's rules are tangled with one storage technology.

The fix is a **port and adapter**:

- **Port** - a narrow `typing.Protocol` the domain owns and depends on. It speaks the domain's
  language (characters, job records), not the framework's (rows, sessions, queries).
- **Adapter** - a class in its own module that *implements* the port over a specific technology. The
  framework lives here and only here.
- **In-memory adapter** - a pure, dependency-free implementation of the same port, for tests and for
  a save-less world.

The domain imports the port. It never imports the framework.

## The worked example: job progression

Before, `parts/world/job_progress.py` held both the `JobProgress` value object *and* the SQLAlchemy
queries. After:

| Piece | Lives in | Knows about |
| --- | --- | --- |
| `JobProgress` (value object) | `parts/world/job_progress.py` | nothing but itself |
| `JobProgressStore` (the port) | `parts/world/job_progress.py` | the domain contract only |
| `InMemoryJobProgressStore` | `parts/world/job_progress.py` | plain dicts |
| `SqlJobProgressStore` (the adapter) | `parts/world/job_progress_sql.py` | SQLAlchemy + `parts/world/db.py` |
| `load_job_progress` / `save_job_progress` | `parts/world/job_progress.py` | delegate to a store (SQL by default) |

`job_progress.py` now imports no framework. `SqlJobProgressStore` still imports SQLAlchemy **lazily,
inside its methods**, so `import forge` never pays the ~400ms ORM import for the value object alone
(EXP-003 preserved).

## Why the wrappers stayed

`load_job_progress(name)` and `save_job_progress(name, records)` are unchanged for every existing
caller (`parts/world/characters.py`). They now take an optional `store=` argument and default to the
SQL adapter, so behaviour is identical in production and injectable in a test. **Behaviour preserved;
only the seam moved.**

## Why it is provable

`tests/test_job_progress_store.py` runs **one behavioural contract against both adapters** (a
parametrized fixture): unknown character loads empty, save-then-load round-trips, re-saving a job
upserts rather than duplicates. The in-memory run is the contract test; the SQL run over the
quarantined tmp database is the integration test. Both are asserted to satisfy the `JobProgressStore`
port at runtime. If a future adapter (a different backend) is added, it inherits the same contract by
adding one fixture parameter.

## Why it is removable

Deleting `job_progress_sql.py` and pointing `_default_store()` at `InMemoryJobProgressStore` would
leave a working, framework-free game (minus persistence). That is the removability the intake
doctrine requires: the framework is a plugged-in adapter, not a load-bearing part of the domain.

## Batch 2: the account-credential seam (auth, extra care)

The second boundary is auth-critical, so it was extracted with a tighter scope than job progression.
`parts/world/accounts.py` mixed **stdlib crypto** (salted pbkdf2, constant-time compare, a
missing-principal timing decoy, generic refusals - already framework-free) with **SQLAlchemy
`AccountRow` access**. Only the second thing is a leak.

The rule that made it safe: **the security policy never crosses the boundary.** The port
(`AccountCredentialStore`) deals in hex strings, never passwords, and does no hashing. Every crypto
call stays in `accounts.py`, still hit by the timing-spy tests that hook `accounts._hash_secret`
(`tests/test_accounts.py`). The port has three methods:

| Method | Meaning |
| --- | --- |
| `find(account) -> AccountSecret \| None` | the stored salt+hash, or None |
| `create(account, salt_hex, hash_hex)` | insert a new account (caller confirmed it is new) |
| `set_secret(account, salt_hex, hash_hex)` | rotate an existing account; missing is a no-op |

`SqlAccountCredentialStore` (in `parts/world/accounts_sql.py`, MOD-04.063) is the only place that
touches the `accounts` table; `InMemoryAccountCredentialStore` is a dict. Every AccountRow access
(`register`, `inspect_login`, `rotate_account_secret`, `reforge_secret`, `migrate`,
`import_legacy_json`, `account_password_ok`) now runs through the port. The public signatures gained
a trailing optional `store=`, so all callers (`forge`, `cli`, `api`, `gateway`) are unchanged.

`tests/test_account_store.py` runs the contract against both adapters **and** proves the whole
credential path (register -> check -> rotate -> reforge, mixed-case preserved, wrong rejected) runs
over an injected in-memory store with **no database touched**.

**Deliberately left for the next boundary:** character-membership row access - `adopt`, the character
half of `inspect_login`/`migrate`, and the owner-rank query - still reads `CharacterRow` directly.
That is a `characters.py` seam (a membership/character store), not an account-credential one, so it is
a separate batch. Splitting it keeps each batch narrow and preserves the auth path's transaction
semantics.

## The template for the next boundary

1. Find a framework leaking into a `parts/world/` domain module.
2. Name a narrow `Protocol` the domain owns (the port).
3. Move the framework code into a new `*_sql.py` (or `*_<tech>.py`) adapter that implements the port.
4. Add a pure in-memory adapter.
5. Keep the old functions as delegating wrappers so callers do not change.
6. Write one contract test, run against every adapter.
7. File the new adapter in `registry/designations/modules.json`; the world-boundary closure discovers
   it automatically.
8. Run `make check` and ARC. Present evidence. Then, and only then, extract the next boundary.

The next obvious candidate is `parts/world/accounts.py` (auth-critical - a heavier, later batch).
