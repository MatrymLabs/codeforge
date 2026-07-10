"""Test twin for parts/blueprint_ai.py -- the Claude-backed Blueprint drafter.

Acceptance: a fake client's structured output becomes a validated Blueprint (status forced to
draft); the `blueprint draft` verb is reachable and honest without a key. Refusal (hostile):
an empty idea never calls the API, a None parsed_output fails loud, and a schema-valid but
Blueprint-invalid draft (bad id) fails loud through the same gate a human's would.
"""

import pytest

from forge import handle_command
from parts.architect import ArchitectError
from parts.blueprint import Blueprint
from parts.blueprint_ai import (
    BlueprintDraft,
    BlueprintDraftError,
    ClaudeBlueprintDrafter,
    build_claude_drafter,
)
from parts.session import Session

_GOOD_DRAFT = BlueprintDraft(
    blueprint_id="ai_idea",
    title="An AI-drafted plan",
    intent="Prove the drafter end to end.",
    requirements=["It must validate through the same gate."],
    tasks=["Build it."],
    stack={"engine": "custom Python"},
)


class _FakeParse:
    def __init__(self, parsed):
        self._parsed = parsed
        self.seen: dict = {}

    def parse(self, **kwargs):
        self.seen = kwargs

        class _Resp:
            parsed_output = self._parsed

        return _Resp()


class _FakeClient:
    def __init__(self, parsed=_GOOD_DRAFT):
        self.messages = _FakeParse(parsed)


# --- acceptance -------------------------------------------------------------


def test_draft_becomes_a_validated_blueprint():
    client = _FakeClient()
    bp = ClaudeBlueprintDrafter(client).draft("an idea for a feature")
    assert isinstance(bp, Blueprint)
    assert bp.blueprint_id == "ai_idea"
    assert bp.status == "draft"  # AI output is always a Tier-4 draft
    # It called the structured-output API with the schema and the right model.
    assert client.messages.seen["model"] == "claude-opus-4-8"
    assert client.messages.seen["output_format"] is BlueprintDraft


# --- refusal: hostile cases fail loud, no network on empty ------------------


def test_empty_idea_never_calls_the_api():
    client = _FakeClient()
    with pytest.raises(BlueprintDraftError):
        ClaudeBlueprintDrafter(client).draft("   ")
    assert client.messages.seen == {}


def test_none_output_fails_loud():
    with pytest.raises(BlueprintDraftError) as err:
        ClaudeBlueprintDrafter(_FakeClient(parsed=None)).draft("idea")
    assert "no usable draft" in str(err.value)


def test_schema_valid_but_blueprint_invalid_draft_fails_loud():
    # The model returns a schema-valid object with a bad id; the Blueprint gate still refuses.
    bad = BlueprintDraft(blueprint_id="Bad-Id", title="X", intent="y", requirements=["r"])
    with pytest.raises(BlueprintDraftError) as err:
        ClaudeBlueprintDrafter(_FakeClient(parsed=bad)).draft("idea")
    assert "invalid" in str(err.value)


def test_build_claude_drafter_refuses_without_a_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ArchitectError):
        build_claude_drafter()


# --- the tick verb: reachable + honest offline ------------------------------


def test_blueprint_draft_is_honest_without_a_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    session = Session(player_id="_draft")
    out = handle_command(session, "blueprint draft an idea for combat")
    assert "needs the Claude Architect" in out


def test_blueprint_draft_prompts_for_an_idea():
    session = Session(player_id="_draft2")
    assert "Describe the idea" in handle_command(session, "blueprint draft")
