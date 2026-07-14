"""Test twin for parts/ai_eval.py -- score an Advisor's answer and file it as a Chronicle ai-eval.

Acceptance: keyword_score is the fraction of the rubric present; evaluate() drives an injected
Advisor (never the network), scores its answer, and files an ai-eval record; the offline
LocalArchitect self-eval records a real, reproducible score. Refusal: an empty rubric fails loud.
Every test uses tmp_path, so the real (git-tracked) chronicle/ dir is never touched.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from parts.ai_eval import SAMPLE, AiEvalError, evaluate, keyword_score, main
from parts.chronicle import ai_evals


class _FakeAdvisor:
    """An `Advisor` that returns a canned answer - the network-free seam a test injects."""

    def __init__(self, answer: str) -> None:
        self.answer = answer
        self.asked: list[str] = []

    def advise(self, prompt: str) -> str:
        self.asked.append(prompt)
        return self.answer


def test_keyword_score_is_the_fraction_present() -> None:
    assert keyword_score("retry with backoff and jitter", ("retry", "backoff", "jitter")) == 1.0
    assert keyword_score("retry with backoff", ("retry", "backoff", "jitter")) == round(2 / 3, 4)
    assert keyword_score("nothing relevant", ("retry",)) == 0.0


def test_keyword_score_is_case_insensitive() -> None:
    assert keyword_score("Use RETRY here", ("retry",)) == 1.0


def test_empty_rubric_fails_loud() -> None:
    with pytest.raises(AiEvalError, match="at least one required keyword"):
        keyword_score("anything", ())


def test_evaluate_scores_an_injected_advisor_and_files_a_record(tmp_path: Path) -> None:
    advisor = _FakeAdvisor("you should add retry with backoff")
    rec = evaluate(
        "q.retry",
        advisor,
        "how do I retry?",
        ("retry", "backoff", "jitter"),
        model="FakeAdvisor",
        threshold=0.5,
        commit="c",
        root=tmp_path,
    )
    assert advisor.asked == ["how do I retry?"]  # the seam was driven, not the network
    assert rec.payload["subject"] == "q.retry"
    assert rec.payload["score"] == round(2 / 3, 4)
    assert rec.payload["passed"] is True  # 0.667 >= 0.5
    assert ai_evals("q.retry", root=tmp_path)[0].payload["model"] == "FakeAdvisor"


def test_evaluate_below_threshold_records_a_fail(tmp_path: Path) -> None:
    advisor = _FakeAdvisor("unrelated answer")
    rec = evaluate("q", advisor, "?", ("retry",), threshold=0.5, commit="c", root=tmp_path)
    assert rec.payload["score"] == 0.0 and rec.payload["passed"] is False


def test_the_offline_sample_scores_the_local_architect(tmp_path: Path) -> None:
    # The canned SAMPLE, scored against the offline LocalArchitect (no network), records a real
    # reproducible score. (main() itself writes to the real store, so we drive evaluate directly
    # with a tmp root rather than call it here.)
    from parts.architect import LocalArchitect

    subject, prompt, required = SAMPLE
    rec = evaluate(
        subject,
        LocalArchitect(),
        prompt,
        required,
        model="LocalArchitect",
        commit="c",
        root=tmp_path,
    )
    assert rec.payload["subject"] == subject
    assert rec.payload["score"] == 1.0  # LocalArchitect names `diagnostics` and `run` for this ask


def test_main_is_callable_offline(monkeypatch) -> None:
    # Prove `make ai-eval`'s entrypoint runs offline without touching the real store: stub the
    # recorder so nothing is written, and confirm it drives the LocalArchitect and returns 0.
    import parts.ai_eval as mod

    monkeypatch.setattr(mod, "record_ai_eval", lambda *a, **k: _Stub())
    assert main(["deadbee"]) == 0


class _Stub:
    payload = {"subject": SAMPLE[0], "score": 1.0, "model": "LocalArchitect", "passed": True}
