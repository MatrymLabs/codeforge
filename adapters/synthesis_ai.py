"""CARD: synthesis_ai -- the real Claude Implementer for the reverse-TDD harness (schema-enforced).

The synthesis harness (kernel/seedlab/synthesis.py) drives spec-derived tests to green by iterating
an `Implementer`: something that, given a goal + the tests + the previous run's failure output,
produces the target's SOURCE files. Slice 1 proved the loop with fakes and over real code; this is
the production brain: a Claude-backed Implementer that fills a STRUCTURED file schema (via the
Anthropic Messages API's `messages.parse`) -- typed files, never prose we hand-parse.

Same seam discipline as the Architect and the Blueprint drafter (adapters/architect.py,
adapters/blueprint_ai.py): the Anthropic client is INJECTED, so tests drive a fake and never touch
the network; codeforge core never imports `anthropic`; the feature is one API key away
(`pip install codeforge[ai]` + ANTHROPIC_API_KEY) and dormant by default (CI has no key).

Integrity guard (the whole point of the harness): the Implementer must not rewrite the spec tests to
fake green. Any returned file whose path is one of the fixed tests is DROPPED before it can clobber
the spec -- the tests encode the acceptance criteria and only source may change.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from adapters.architect import CLAUDE_MODEL, anthropic_client
from kernel.seedlab.synthesis import Implementer, TargetFiles

_IMPLEMENT_SYSTEM = (
    "You are a careful Python implementer working under a reverse-TDD harness. You are given a "
    "goal, a set of test files that encode the acceptance criteria, and (after the first "
    "attempt) the failure output from the previous run. Produce the SOURCE files that make those "
    "tests pass. Write real, honest logic: never a stub that hard-codes the expected answers, "
    "never a placeholder that returns 'ok'. Do NOT emit or modify any test file: the tests are "
    "fixed and rewriting them to pass is forbidden. Return only the source files needed, each with "
    "its relative path and full content. Prefer the smallest correct implementation. Validate "
    "inputs at the boundaries and fail loud on bad input. Do not invent dependencies not implied."
)


class ImplementerError(RuntimeError):
    """The Claude-backed Implementer could not produce usable source (a refusal, or no files)."""


class _SourceFile(BaseModel):
    """One generated file: its relative path and full UTF-8 content."""

    path: str
    content: str


class _GeneratedSource(BaseModel):
    """The schema the model must fill: the source files (never the tests)."""

    files: list[_SourceFile]


def _prompt(goal: str, tests: TargetFiles, feedback: str) -> str:
    """Assemble the user turn: the goal, the fixed tests to satisfy, and any prior failure."""
    lines = [f"GOAL:\n{goal}", "", "TESTS YOUR SOURCE MUST PASS (do not modify these):"]
    for rel, text in sorted(tests.items()):
        lines.append(f"--- {rel} ---\n{text}")
    if feedback.strip():
        lines += ["", "YOUR PREVIOUS ATTEMPT FAILED. Test output:", feedback.strip()]
    return "\n".join(lines)


class ClaudeImplementer:
    """An `Implementer` backed by the Anthropic Messages API with structured output. The client is
    INJECTED, so tests drive a fake and never touch the network. Satisfies the harness's Implementer
    protocol structurally, so `synthesize` never changes."""

    def __init__(self, client: Any, model: str = CLAUDE_MODEL) -> None:
        self._client = client
        self._model = model

    def implement(self, goal: str, tests: TargetFiles, feedback: str) -> TargetFiles:
        response = self._client.messages.parse(
            model=self._model,
            max_tokens=4096,
            system=_IMPLEMENT_SYSTEM,
            messages=[{"role": "user", "content": _prompt(goal, tests, feedback)}],
            output_format=_GeneratedSource,
        )
        generated = response.parsed_output
        if generated is None:
            # The model declined or returned no schema-valid JSON. Surface it, don't guess.
            raise ImplementerError("the model returned no usable source")
        # Integrity: drop anything that would clobber a spec test -- source changes, tests never do.
        source: TargetFiles = {f.path: f.content for f in generated.files if f.path not in tests}
        if not source:
            raise ImplementerError("the model produced no source files to build")
        return source


def build_claude_implementer(model: str | None = None) -> Implementer:
    """Construct the production Claude Implementer. One API key away: needs ANTHROPIC_API_KEY and
    `pip install codeforge[ai]`. Raises ArchitectError (via anthropic_client) if either absent."""
    return ClaudeImplementer(anthropic_client(), model or CLAUDE_MODEL)
