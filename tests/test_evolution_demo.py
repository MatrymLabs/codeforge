"""Guard for scripts/evolution_demo.py -- catch signature drift that breaks the runnable demo.

The demo's output is git-ignored, so nothing exercised it in CI, and a Blueprint field change once
broke it silently (a required `security` arg was added to the model but not the demo). This pins
that the demo's genome construction still matches the Blueprint model, so `make evolution` stays
runnable for a stranger. It never runs the full bake-off (no report is written under test).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

_DEMO = Path(__file__).resolve().parent.parent / "scripts" / "evolution_demo.py"


def _load_demo() -> Any:
    spec = importlib.util.spec_from_file_location("evolution_demo", _DEMO)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_demo_genome_matches_the_blueprint_model() -> None:
    demo = _load_demo()
    genome = demo._genome(
        "demo_id", "Demo", "prove the framework is signature-agnostic", "a pure fn"
    )
    assert genome.genome_id == "demo_id"
    assert genome.seed.security  # the required field whose absence once broke the demo
    assert genome.seed.requirements  # still a well-formed Blueprint
