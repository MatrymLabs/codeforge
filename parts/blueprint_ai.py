"""CARD: blueprint_ai -- draft a Blueprint from a freeform idea, with Claude (schema-enforced).

The AI force-multiplier, made honest. Given a plain-English idea, a Claude-backed drafter
returns a STRUCTURED Blueprint (schema-enforced JSON via the Anthropic Messages API's
`messages.parse`), which is then re-validated through the same loud gate every human-authored
Blueprint passes (`parts.blueprint.from_dict`). The model fills a schema; it never emits free
prose we parse by hand, and its output is always a Tier-4 DRAFT for a human to review.

Same seam discipline as the Architect (`parts/architect.py`): the Anthropic client is
INJECTED, so tests use a fake and never touch the network; codeforge core never imports
`anthropic`; the feature is one API key away and dormant by default.
"""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel

from parts.architect import CLAUDE_MODEL, anthropic_client
from parts.blueprint import Blueprint, BlueprintError, from_dict

_DRAFT_SYSTEM = (
    "You are a senior software architect. Turn the user's idea into a structured Blueprint: "
    "a permanent lowercase_snake_case blueprint_id, a short title, a one-line intent, a list "
    "of concrete requirements the feature must satisfy, and the implementation tasks. Prefer "
    "the smallest useful version. Requirements describe WHAT must be true; tasks describe the "
    "steps to build it. Do not invent a stack the idea does not imply."
)


class BlueprintDraftError(RuntimeError):
    """The model could not produce a usable, valid Blueprint draft."""


class BlueprintDraft(BaseModel):
    """The schema the model must fill. Re-validated by from_dict before it becomes a Blueprint."""

    blueprint_id: str
    title: str
    intent: str
    requirements: list[str]
    tasks: list[str] = []
    stack: dict[str, str] = {}


class BlueprintDrafter(Protocol):
    """Anything that can turn an idea into a validated Blueprint."""

    def draft(self, idea: str) -> Blueprint: ...


class ClaudeBlueprintDrafter:
    """A `BlueprintDrafter` backed by the Anthropic Messages API with structured output.
    The client is INJECTED, so tests drive a fake and never touch the network."""

    def __init__(self, client: Any, model: str = CLAUDE_MODEL) -> None:
        self._client = client
        self._model = model

    def draft(self, idea: str) -> Blueprint:
        text = idea.strip()
        if not text:
            raise BlueprintDraftError("describe the idea to draft a blueprint")
        response = self._client.messages.parse(
            model=self._model,
            max_tokens=1024,
            system=_DRAFT_SYSTEM,
            messages=[{"role": "user", "content": text}],
            output_format=BlueprintDraft,
        )
        draft = response.parsed_output
        if draft is None:
            # The model declined or returned no schema-valid JSON. Surface it, don't guess.
            raise BlueprintDraftError("the model returned no usable draft")
        try:
            # Force status to 'draft' (AI output is Tier-4) and re-validate through the gate.
            return from_dict({**draft.model_dump(), "status": "draft"})
        except BlueprintError as exc:
            raise BlueprintDraftError(f"the model's draft was invalid: {exc}") from exc


def build_claude_drafter(model: str | None = None) -> BlueprintDrafter:
    """Construct the production Claude drafter. One API key away: needs ANTHROPIC_API_KEY and
    `pip install codeforge[ai]`. Raises ArchitectError if neither is present."""
    return ClaudeBlueprintDrafter(anthropic_client(), model or CLAUDE_MODEL)
