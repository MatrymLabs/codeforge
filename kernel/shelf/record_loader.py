"""CARD: record_loader -- load validated JSON records from a file or a directory.

Harvested from a real duplication the clone scan flagged: `blueprint` and `learning_record` each
read a JSON file (catching OSError/JSONDecodeError, failing loud) and glob a directory of them. This
is that pattern once, parameterized by a validator and the error type to raise, so a subsystem
supplies only its schema. The loop closing on itself: the clone scan found the duplicate logic, and
extracting it here removes it - proven by re-running the scan.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path


def load_record[T](
    path: Path, parse: Callable[[object], T], *, error: type[Exception], label: str = "record"
) -> T:
    """Read and validate one JSON record file. An unreadable file fails loud as `error`."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise error(f"unreadable {label} at {path}: {exc}") from exc
    return parse(raw)


def load_dir[T](
    directory: Path,
    parse: Callable[[object], T],
    *,
    error: type[Exception],
    label: str = "record",
    recursive: bool = False,
) -> list[T]:
    """Load every JSON record in `directory`, sorted by path. A missing directory is empty."""
    if not directory.is_dir():
        return []
    pattern = "**/*.json" if recursive else "*.json"
    return [
        load_record(p, parse, error=error, label=label) for p in sorted(directory.glob(pattern))
    ]
