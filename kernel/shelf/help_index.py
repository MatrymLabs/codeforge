"""CARD: help_index -- structured, searchable help built from command metadata.

Clean-room, pattern-not-code harvest of the help-system SHAPE (per-command
entries, topic lookup with near-match suggestions, grouped overview) from
Evennia's help subsystem (BSD-3-Clause). No Evennia source was copied; this is
an independent frameless implementation driven by codeforge's command spine
metadata (name, purpose, namespace).

Attribution: pattern inspired by Evennia (https://www.evennia.com/),
BSD-3-Clause. This file is an original clean-room implementation.

The problem this solves: codeforge's `help` verb is one static blob that
ignores its argument. This part derives real per-command and topic help from
the metadata the command spine already carries, so `help <command>` answers
the question actually asked.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# A command NAME as it appears on the spine: an optional ADMIN "@" sigil, then one or more lowercase
# words (letters, digits, underscores, hyphens) separated by single spaces. This accepts the real
# verb grammar (look, registry show, @sg, pm status, qa gate all, @flush-encounters, docs check)
# while still rejecting uppercase, a leading digit, or stray symbols. Kept permissive-but-shaped so
# the index stays a general command/topic index, not a codeforge-specific one.
_COMMAND_NAME = re.compile(r"^@?[a-z][a-z0-9_-]*( [a-z0-9][a-z0-9_-]*)*$")


class HelpError(ValueError):
    """Loud failure for unknown topics, duplicate names, or bad labels.

    A ValueError subclass so callers can catch it precisely while still
    treating it as the bad-input signal it is.
    """


@dataclass(frozen=True)
class HelpEntry:
    """One command's help record, harvested from command-spine metadata.

    name: the command name/verb as it appears on the spine.
    purpose: the one-line CARD-style summary.
    namespace: the spine namespace ("core" / "admin" / "seed").
    body: optional longer help text; empty when the command has none.
    """

    name: str
    purpose: str
    namespace: str
    body: str = ""


@dataclass(frozen=True)
class HelpIndex:
    """An immutable, searchable index of HelpEntry records keyed by name."""

    _entries: dict[str, HelpEntry] = field(default_factory=dict)

    @staticmethod
    def build(entries: list[HelpEntry]) -> HelpIndex:
        """Forge an index from entries, failing loud on bad or duplicate names.

        Inputs: a list of HelpEntry.
        Output: a HelpIndex.
        Raises HelpError on an invalid command name or a duplicate name, so a
        malformed command table shouts at construction, not at lookup.
        """
        table: dict[str, HelpEntry] = {}
        for entry in entries:
            if not _COMMAND_NAME.match(entry.name):
                raise HelpError(f"help entry name is not a valid command name: {entry.name!r}")
            if entry.name in table:
                raise HelpError(f"duplicate help entry name: {entry.name!r}")
            table[entry.name] = entry
        return HelpIndex(table)

    def topic(self, name: str) -> HelpEntry:
        """Return the exact HelpEntry for one command name.

        Raises HelpError if the name is unknown; the message names the closest
        prefix/substring matches so the caller can recover from a typo.
        """
        entry = self._entries.get(name)
        if entry is not None:
            return entry
        near = self._near_matches(name)
        if near:
            hint = ", ".join(near)
            raise HelpError(f"no help topic {name!r}; did you mean: {hint}")
        raise HelpError(f"no help topic {name!r}")

    def search(self, query: str) -> list[str]:
        """Return sorted command names whose name or purpose contains query.

        Case-insensitive substring match. An empty (or whitespace-only) query
        fails loud rather than silently matching everything.
        """
        needle = query.strip().lower()
        if not needle:
            raise HelpError("search query is empty")
        hits = [
            name
            for name, entry in self._entries.items()
            if needle in name.lower() or needle in entry.purpose.lower()
        ]
        return sorted(hits)

    def overview(self) -> str:
        """Render a grouped listing of `name - purpose`, sorted by namespace.

        Namespaces are grouped in sorted order; commands within each group are
        sorted by name. Returns a plain "(no help entries)" line when empty.
        """
        if not self._entries:
            return "(no help entries)"
        groups: dict[str, list[HelpEntry]] = {}
        for entry in self._entries.values():
            groups.setdefault(entry.namespace, []).append(entry)
        blocks: list[str] = []
        for namespace in sorted(groups):
            lines = [f"[{namespace}]"]
            for entry in sorted(groups[namespace], key=lambda e: e.name):
                lines.append(f"  {entry.name} - {entry.purpose}")
            blocks.append("\n".join(lines))
        return "\n\n".join(blocks)

    def render_topic(self, name: str) -> str:
        """Render a human-readable help block for one command.

        Raises HelpError (via topic) if the name is unknown.
        """
        entry = self.topic(name)
        lines = [
            f"{entry.name} ({entry.namespace})",
            entry.purpose,
        ]
        if entry.body:
            lines.append("")
            lines.append(entry.body)
        return "\n".join(lines)

    def _near_matches(self, name: str, limit: int = 3) -> list[str]:
        """Suggest known names by prefix then substring, sorted and de-duped."""
        needle = name.strip().lower()
        if not needle:
            return []
        prefix = sorted(n for n in self._entries if n.startswith(needle))
        substring = sorted(n for n in self._entries if needle in n and not n.startswith(needle))
        ordered = prefix + substring
        return ordered[:limit]
