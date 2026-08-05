"""CARD: seed_selection -- one precedence contract for product Seed selection.

The game loader retains its historical ``first-forge`` library default so direct
Engine consumers remain compatible. Product startup uses this module instead:

explicit request -> active project -> persisted user choice -> environment -> Aethryn.

Selection is resolved before importing ``kernel.world`` because that package binds
the selected Seed at import time. Persisted choices are deliberately written only
by an explicit selection operation; startup never changes them implicitly.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

PRODUCT_DEFAULT_SEED = "aethryn"
SELECTION_FILE_ENV = "CODEFORGE_SELECTION_FILE"
ACTIVE_PROJECT_SEED_ENV = "CODEFORGE_ACTIVE_SEED"
RUNTIME_SEED_ENV = "FORGE_SEED"
_SEED_ID = re.compile(r"^[a-z][a-z0-9-]*$")


class SeedSelectionError(ValueError):
    """A requested Seed is malformed, unavailable, or has invalid persisted state."""


@dataclass(frozen=True)
class SeedSelection:
    """The selected Seed and the source that won the precedence decision."""

    seed_id: str
    source: str


def discover_seed_ids(root: Path) -> list[str]:
    """List bootable Seed packages from one authoritative content root."""
    if not root.is_dir():
        return []
    return sorted(path.name for path in root.iterdir() if (path / "rooms.yaml").is_file())


def _validate_seed_id(seed_id: str, *, field: str = "seed") -> str:
    value = seed_id.strip()
    if not _SEED_ID.fullmatch(value):
        raise SeedSelectionError(
            f"{field} {seed_id!r} must be lowercase letters, digits, or hyphens"
        )
    return value


def selection_path(env: Mapping[str, str] | None = None) -> Path:
    """Return the user selection file, with an explicit test/deployment override."""
    values = os.environ if env is None else env
    configured = values.get(SELECTION_FILE_ENV, "").strip()
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".config" / "codeforge" / "selection.json"


def read_persisted_seed(path: Path | None = None) -> str | None:
    """Read a persisted selection without changing it; absent files mean no choice."""
    target = path or selection_path()
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SeedSelectionError(f"cannot read persisted Seed selection {target}: {exc}") from exc
    if not isinstance(raw, dict) or not isinstance(raw.get("seed"), str):
        raise SeedSelectionError(f"persisted Seed selection {target} must contain a string 'seed'")
    return _validate_seed_id(raw["seed"], field="persisted seed")


def persist_seed(seed_id: str, path: Path | None = None) -> Path:
    """Persist an explicit user choice atomically and return its path."""
    seed = _validate_seed_id(seed_id)
    target = path or selection_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.tmp")
    payload = {"version": 1, "seed": seed}
    try:
        temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        temporary.replace(target)
    except OSError as exc:
        raise SeedSelectionError(f"cannot persist Seed selection {target}: {exc}") from exc
    return target


def clear_persisted_seed(path: Path | None = None) -> bool:
    """Remove an explicit persisted choice; return whether a file was removed."""
    target = path or selection_path()
    try:
        target.unlink()
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise SeedSelectionError(f"cannot clear persisted Seed selection {target}: {exc}") from exc
    return True


def resolve_seed(
    *,
    explicit: str | None = None,
    active_project: str | None = None,
    persisted: str | None = None,
    environment: str | None = None,
    available: set[str] | frozenset[str] | None = None,
    default: str = PRODUCT_DEFAULT_SEED,
) -> SeedSelection:
    """Resolve one Seed using the platform precedence contract.

    A configured but unavailable Seed fails loudly. The caller can then offer an
    explicit fallback without silently changing the user's selection.
    """
    candidates = (
        ("explicit", explicit),
        ("active-project", active_project),
        ("persisted", persisted),
        ("environment", environment),
        ("default", default),
    )
    for source, candidate in candidates:
        if candidate is None or not candidate.strip():
            continue
        seed = _validate_seed_id(candidate, field=f"{source} seed")
        if available is not None and seed not in available:
            raise SeedSelectionError(
                f"{source} Seed {seed!r} is not installed; available Seeds: "
                f"{', '.join(sorted(available)) or '(none)'}"
            )
        return SeedSelection(seed_id=seed, source=source)
    raise SeedSelectionError("no Seed is configured and no default Seed is available")


def resolve_from_environment(
    available: set[str] | frozenset[str],
    *,
    explicit: str | None = None,
    persisted_path: Path | None = None,
) -> SeedSelection:
    """Resolve startup selection from environment and the user preference file."""
    persisted = read_persisted_seed(persisted_path)
    return resolve_seed(
        explicit=explicit,
        active_project=os.environ.get(ACTIVE_PROJECT_SEED_ENV),
        persisted=persisted,
        environment=os.environ.get(RUNTIME_SEED_ENV),
        available=available,
    )
