"""CARD: architect -- the Architect NPC: an advisory AI pair-programmer (read-only).

The Architect sits in the Workshop and answers questions. It explains, suggests
commands, and points at reusable parts -- but it NEVER edits files or runs
anything (that stays with you and the FailsafeRunner). It speaks through a seam
(`Advisor`) so the brain is swappable: a local rule-based guide today, a
Claude-backed one later behind the SAME interface.

Safety (docs/proving_ground/SAFETY.md): tests use the local advisor and never touch the
network; only redacted, public project context is ever sent to a real API, and
secrets never are.
"""

from __future__ import annotations

import os
import re
from typing import Any, Protocol

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


# --- the Claude-backed brain (architecture in place; one API key away from live) ---
#
# The seam is complete and tested with a fake; wiring a real brain is an env var
# (CODEFORGE_ARCHITECT=claude) plus ANTHROPIC_API_KEY plus `pip install codeforge[ai]`.
# The Anthropic SDK is touched ONLY here, behind the Advisor protocol, so codeforge core
# never hard-depends on it and CI (no key, fake injected) never reaches the network.

_CLAUDE_MODEL = "claude-opus-4-8"

_ARCHITECT_SYSTEM = (
    "You are the Architect, a senior engineering pair-programmer standing in the Workshop "
    "of CodeForge, a Python MUD engine. Give calm, concrete, read-only guidance: which "
    "command to run, which reusable part fits, how to shape a small change. You never edit "
    "files, never run anything, and never ask for or repeat secrets. Answer in a few plain "
    "sentences."
)

# Anything that looks like a credential is scrubbed before a prompt leaves the machine.
_SECRETISH = re.compile(r"(?i)\b(password|passwd|secret|token|api[_-]?key)\b\S*\s*[:=]?\s*\S+")


class ArchitectError(RuntimeError):
    """The Claude-backed Architect could not be built or reached (e.g. no API key)."""


def _redact(text: str) -> str:
    """Never send a secret to a remote brain (docs/proving_ground/SAFETY.md)."""
    return _SECRETISH.sub("[redacted]", text)


class ClaudeAdvisor:
    """`Advisor` backed by the Anthropic Messages API. The client is INJECTED, so tests use
    a fake and never touch the network. Only redacted prompt text is sent; secrets never
    leave the machine. Same seam as the local brain, so callers never change."""

    def __init__(self, client: Any, model: str = _CLAUDE_MODEL) -> None:
        self._client = client
        self._model = model

    def advise(self, prompt: str) -> str:
        question = _redact(prompt.strip())
        if not question:
            return "The Architect waits. Ask a question."
        message = self._client.messages.create(
            model=self._model,
            max_tokens=400,
            system=_ARCHITECT_SYSTEM,
            messages=[{"role": "user", "content": question}],
        )
        reply = "".join(
            getattr(block, "text", "")
            for block in message.content
            if getattr(block, "type", "") == "text"
        ).strip()
        if not reply:
            return "The Architect has no counsel right now."
        return f"The Architect considers, then says:\n  {reply}"


def anthropic_client() -> Any:
    """Construct an Anthropic client, or fail loud. Shared by every Claude-backed feature
    (the Architect, the Blueprint drafter): one API key away from live: needs
    ANTHROPIC_API_KEY in the env and the `anthropic` package (`pip install codeforge[ai]`).
    Never reached in CI or offline play (tests inject a fake client)."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise ArchitectError("set ANTHROPIC_API_KEY to use a Claude-backed feature")
    try:
        import anthropic
    except ImportError as exc:  # an optional extra, not a core dependency
        raise ArchitectError("Claude features need `pip install codeforge[ai]`") from exc
    return anthropic.Anthropic()


def build_claude_advisor(model: str | None = None) -> Advisor:
    """The production Claude-backed Architect. The default brain stays local; this is only
    reached when CODEFORGE_ARCHITECT=claude and a key is present."""
    return ClaudeAdvisor(anthropic_client(), model or _CLAUDE_MODEL)


_DEFAULT: Advisor = LocalArchitect()


def _resolve_brain() -> tuple[Advisor, str]:
    """Pick the Architect's brain. Claude only when explicitly enabled (CODEFORGE_ARCHITECT
    = claude) AND reachable; otherwise the local guide, so CI and offline play never touch
    the network. A requested-but-unreachable Claude is surfaced honestly, never hidden."""
    if os.environ.get("CODEFORGE_ARCHITECT", "").strip().lower() == "claude":
        try:
            return build_claude_advisor(), ""
        except ArchitectError as exc:
            return _DEFAULT, f"(Architect: Claude requested but {exc}; using the local guide.)"
    return _DEFAULT, ""


def consult(prompt: str, advisor: Advisor | None = None) -> str:
    """Ask the Architect. Pass `advisor` to test with a fake or force a brain; otherwise the
    brain is resolved from the environment (local by default, Claude if enabled)."""
    if advisor is not None:
        return advisor.advise(prompt)
    brain, note = _resolve_brain()
    reply = brain.advise(prompt)
    return f"{note}\n{reply}" if note else reply
