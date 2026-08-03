"""Test twin for adapters/synthesis_ai.py -- the Claude-backed Implementer for the synthesis.

Acceptance: a fake client's structured file output becomes the harness's TargetFiles; the adapter
satisfies the Implementer protocol structurally and calls the schema-enforced API with the right
model; the goal, the fixed tests, and the prior failure output all reach the prompt.

Refusal (hostile, fail loud): a None parsed_output raises; a model that returns no source (only
test files, or nothing) raises rather than handing back an empty build; and the integrity guard
DROPS any returned file that would clobber a spec test -- rewriting the tests to fake green is
forbidden. Offline throughout: the client is a fake, the network is never touched.
"""

from __future__ import annotations

import pytest

from adapters.architect import ArchitectError
from adapters.synthesis_ai import (
    ClaudeImplementer,
    ImplementerError,
    _GeneratedSource,
    _SourceFile,
    build_claude_implementer,
)
from kernel.seedlab.synthesis import Implementer

_GOOD = _GeneratedSource(
    files=[_SourceFile(path="calc.py", content="def add(a, b):\n    return a + b\n")]
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
    def __init__(self, parsed=_GOOD):
        self.messages = _FakeParse(parsed)


# --- acceptance -------------------------------------------------------------


def test_the_adapter_is_an_implementer() -> None:
    assert isinstance(ClaudeImplementer(_FakeClient()), Implementer)


def test_structured_output_becomes_target_files() -> None:
    client = _FakeClient()
    source = ClaudeImplementer(client).implement("an add(a, b)", {"tests/t.py": "x"}, "")
    assert source == {"calc.py": "def add(a, b):\n    return a + b\n"}
    # It called the schema-enforced API with the right model and schema.
    assert client.messages.seen["model"] == "claude-opus-4-8"
    assert client.messages.seen["output_format"] is _GeneratedSource


def test_prompt_carries_goal_tests_and_feedback() -> None:
    client = _FakeClient()
    ClaudeImplementer(client).implement(
        "build add", {"tests/test_calc.py": "assert add(2,3)==5"}, "fail#1"
    )
    prompt = client.messages.seen["messages"][0]["content"]
    assert "build add" in prompt
    assert "tests/test_calc.py" in prompt and "assert add(2,3)==5" in prompt
    assert "fail#1" in prompt  # the prior failure output is fed back


def test_first_attempt_omits_the_feedback_block() -> None:
    client = _FakeClient()
    ClaudeImplementer(client).implement("g", {"tests/t.py": "x"}, "")
    assert "PREVIOUS ATTEMPT" not in client.messages.seen["messages"][0]["content"]


# --- refusal: hostile cases fail loud; the harness's integrity is upheld -----


def test_none_output_fails_loud() -> None:
    with pytest.raises(ImplementerError) as err:
        ClaudeImplementer(_FakeClient(parsed=None)).implement("g", {"tests/t.py": "x"}, "")
    assert "no usable source" in str(err.value)


def test_spec_tests_cannot_be_rewritten_by_the_implementer() -> None:
    # The model tries to overwrite the fixed test plus emit real source.
    sneaky = _GeneratedSource(
        files=[
            _SourceFile(path="tests/t.py", content="def test_x():\n    assert True\n"),
            _SourceFile(path="calc.py", content="def add(a, b):\n    return a + b\n"),
        ]
    )
    source = ClaudeImplementer(_FakeClient(parsed=sneaky)).implement(
        "g", {"tests/t.py": "orig"}, ""
    )
    assert source == {"calc.py": "def add(a, b):\n    return a + b\n"}  # test file dropped


def test_no_source_after_dropping_tests_fails_loud() -> None:
    only_tests = _GeneratedSource(files=[_SourceFile(path="tests/t.py", content="x")])
    with pytest.raises(ImplementerError) as err:
        ClaudeImplementer(_FakeClient(parsed=only_tests)).implement("g", {"tests/t.py": "x"}, "")
    assert "no source files" in str(err.value)


def test_build_requires_a_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ArchitectError):
        build_claude_implementer()
