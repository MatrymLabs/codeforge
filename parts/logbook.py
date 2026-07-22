"""CARD: logbook -- the game adapter for the repository: a player's numbered logbook.

A player keeps a personal logbook: `journal <text>` records a numbered entry, `journal` lists them.
Each player's entries live in a `Repository` (parts/shelf/repository), so the adapter never
touches raw storage. The SAME repository core backs a records/asset registry in a practical app
(parts/asset_registry); only the adapter differs.
"""

from __future__ import annotations

from dataclasses import dataclass

from parts.session import Session
from parts.shelf.repository import InMemoryRepository


@dataclass(frozen=True)
class LogEntry:
    """One numbered line in a player's logbook."""

    number: int
    text: str


_REPOS: dict[str, InMemoryRepository[LogEntry, int]] = {}
_COUNTERS: dict[str, int] = {}


def _repo(player_id: str) -> InMemoryRepository[LogEntry, int]:
    if player_id not in _REPOS:
        _REPOS[player_id] = InMemoryRepository(lambda e: e.number)
    return _REPOS[player_id]


def journal(session: Session, arg: str = "") -> str:
    """The `journal` verb: list the logbook, or record a new numbered entry."""
    repo = _repo(session.player_id)
    text = arg.strip()
    if not text:
        entries = repo.list()
        if not entries:
            return "Your logbook is empty. Record a line with: journal <text>"
        lines = "\n".join(f"  {e.number}. {e.text}" for e in entries)
        return f"Your logbook ({repo.count()}):\n{lines}"
    number = _COUNTERS.get(session.player_id, 0) + 1
    _COUNTERS[session.player_id] = number
    repo.add(LogEntry(number, text))
    return f"Logged (#{number}): {text}"


def reset_logbooks() -> None:
    """Test hook: clear every player's logbook."""
    _REPOS.clear()
    _COUNTERS.clear()
