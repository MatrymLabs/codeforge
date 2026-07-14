"""CARD: ai_eval -- score an Advisor's answer against a rubric and file it as a Chronicle ai-eval.

Closes the "AI evaluated once" gap: an AI/Advisor output gets a reproducible score filed as an
`ai-eval` Chronicle record, so quality is tracked over time (MLOps eval-regression memory) instead
of judged once and forgotten.

The Advisor is a seam (`parts.architect.Advisor`): the offline `LocalArchitect` scores with no
network, and a real `ClaudeAdvisor` (one API key away) evaluates the LLM through the SAME path -
tests and CI never touch the network. The rubric is an honest keyword-coverage score (the fraction
of required keywords present), deterministic and clearly not a claim of semantic grading.

Provenance: original composition of CodeForge parts (architect, chronicle). No code copied.
"""

from __future__ import annotations

from pathlib import Path

from parts.architect import CLAUDE_MODEL, Advisor
from parts.chronicle import Record, record_ai_eval


class AiEvalError(ValueError):
    """A malformed eval request (an empty rubric): fail loud rather than score nothing."""


def keyword_score(response: str, required: tuple[str, ...]) -> float:
    """The fraction of `required` keywords present in `response` (case-insensitive), 0.0..1.0."""
    if not required:
        raise AiEvalError("a rubric needs at least one required keyword")
    text = response.lower()
    hits = sum(1 for keyword in required if keyword.lower() in text)
    return round(hits / len(required), 4)


def evaluate(
    subject: str,
    advisor: Advisor,
    prompt: str,
    required: tuple[str, ...],
    *,
    model: str = CLAUDE_MODEL,
    threshold: float = 0.5,
    commit: str,
    root: Path | None = None,
) -> Record:
    """Ask `advisor` the `prompt`, score its answer against `required`, and file an ai-eval."""
    response = advisor.advise(prompt)
    score = keyword_score(response, required)
    return record_ai_eval(
        subject, score, model=model, passed=score >= threshold, commit=commit, root=root
    )


# A canned offline self-eval: asked how to run the tests, does the local Architect point at the
# diagnostics tools? A reproducible regression check that needs no network.
SAMPLE = ("architect.testing_guidance", "how do I run the tests?", ("diagnostics", "run"))


def main(argv: list[str] | None = None) -> int:
    """`make ai-eval`: run the sample eval against the offline LocalArchitect and record it."""
    import sys

    from parts.architect import LocalArchitect

    args = list(sys.argv[1:] if argv is None else argv)
    commit = args[0] if args else "unknown"
    subject, prompt, required = SAMPLE
    rec = evaluate(
        subject, LocalArchitect(), prompt, required, model="LocalArchitect", commit=commit
    )
    p = rec.payload
    verdict = "pass" if p["passed"] else "FAIL"
    print(f"  ai-eval {p['subject']}: {p['score']} [{verdict}] via {p['model']} @ {commit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
