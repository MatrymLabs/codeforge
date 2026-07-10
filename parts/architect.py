"""CARD: architect -- the Architect NPC: an advisory AI pair-programmer (read-only).

The Architect sits in the Workshop and answers questions. It explains, suggests
commands, and points at reusable parts -- but it NEVER edits files or runs
anything (that stays with you and the FailsafeRunner). It speaks through a seam
(`Advisor`) so the brain is swappable: a local rule-based guide today, a
Claude-backed one later behind the SAME interface.

Safety (docs/holodeck/SAFETY.md): tests use the local advisor and never touch the
network; only redacted, public project context is ever sent to a real API, and
secrets never are.
"""

from __future__ import annotations

import re
from typing import Protocol

from parts.hardware import Part, load_catalog, part_haystack


class Advisor(Protocol):
    """Anything that can turn a question into advice. The Architect's brain."""

    def advise(self, prompt: str) -> str: ...


def _matching_parts(text: str) -> list[Part]:
    """Catalog parts whose haystack shares a meaningful word with the prompt."""
    words = {word for word in re.findall(r"[a-z]{4,}", text.lower())}
    if not words:
        return []
    return [part for part in load_catalog() if words & set(part_haystack(part).split())]


class LocalArchitect:
    """A rule-based Workshop guide: no network, no secrets. It points you at the
    right command or reusable part based on what you ask -- advisory only."""

    def advise(self, prompt: str) -> str:
        text = prompt.strip().lower()
        if not text:
            return (
                "The Architect waits. Ask a question, e.g.:\n"
                "  ai how do I find a part for audit logging?\n"
                "  ai how do I run the tests?"
            )
        tips: list[str] = []
        if any(w in text for w in ("test", "lint", "type", "check", "diagnos", "gate", "run")):
            tips.append(
                "Run the read-only checks with `diagnostics`, or one at a time - "
                "`run lint`, `run types`, `run tests`."
            )
        if any(w in text for w in ("part", "catalog", "reuse", "component", "hardware", "module")):
            tips.append("Browse the hardware store with `catalog`; search it with `reuse <term>`.")
        matches = _matching_parts(text)
        if matches:
            named = ", ".join(f"[{part.id}] {part.name}" for part in matches[:3])
            tips.append(f"From the catalog, these may fit: {named}.")
        if any(w in text for w in ("lost", "start", "begin", "where", "help", "how do", "new")):
            tips.append(
                "You're in the Workshop. `workshop` lists your tools, `console` the "
                "diagnostics, `catalog` the reusable parts."
            )
        if not tips:
            tips.append(
                "I can point you at tools and parts. Try `workshop`, `catalog`, or "
                "`diagnostics` - or ask about a domain (audit, rbac, validation)."
            )
        body = "\n".join(f"  · {tip}" for tip in tips)
        return f"The Architect considers, then says:\n{body}"


_DEFAULT: Advisor = LocalArchitect()


def consult(prompt: str, advisor: Advisor | None = None) -> str:
    """Ask the Architect. Swap `advisor` to test with a fake or use another brain."""
    return (advisor or _DEFAULT).advise(prompt)
