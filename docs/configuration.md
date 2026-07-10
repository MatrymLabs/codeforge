# Configuration (typed + validated)

`parts/config.py` is the single, typed catalog of CodeForge's environment. Individual
modules still read their own variable at call time (so tests can monkeypatch them), but the
`Settings` model names every knob in one place, types it, validates it, and renders it with
credentials redacted. It proves typed, validated configuration with **Pydantic** - a
recurring backend/full-stack hiring ask.

## The environment

| Variable | Type | Default | Meaning |
|---|---|---|---|
| `PORT` | int (1-65535) | 8000 | Port for the browser gateway (`codeforge web`). |
| `CODEFORGE_ARCHITECT` | `local` \| `claude` | `local` | The Architect NPC's brain (`docs/architect_brain.md`). |
| `DATABASE_URL` | str | (unset) | PostgreSQL URL; unset -> the SQLite default (`docs/database.md`). |
| `CODEFORGE_DB` | path | (unset) | Override the SQLite file location. |
| `FORGE_SEED` | str | (default seed) | Which seed pack to load. |
| `ANTHROPIC_API_KEY` | secret | (unset) | Reported present/absent only; the value is never shown. |

## Use it

```bash
# In the MUD terminal:
terminal config        # prints the effective, validated config (secrets redacted)
```

```python
from parts.config import Settings

settings = Settings.load()          # reads + validates the process environment
uvicorn.run(app, port=settings.port)  # e.g. the `web` entry point uses this
```

## Why it is safe / honest

- **Fails loud, early, by name.** A non-numeric or out-of-range `PORT` raises `ConfigError`
  at the catalog, not as a raw crash deep in a driver. `architect_brain` is a typed
  `Literal`; an odd value normalizes to `local` (mirroring `parts/architect.py`), never a
  crash.
- **Frozen.** Settings are read once and never mutated in place.
- **Secrets never printed.** `render()` reports the API key as present/absent, and redacts
  the credentials inside a `DATABASE_URL` (scheme + host only).
- **Pydantic earns its place.** It was already a transitive dependency of FastAPI; it is now
  declared and used directly (typed API models + this catalog), justified in the ledger.
