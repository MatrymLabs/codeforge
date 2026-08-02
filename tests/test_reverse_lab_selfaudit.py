"""The Reverse-Engineering Lab, pointed at CodeForge itself - the real consumer.

CodeForge is a self-auditing engineering stack, so its own Lab shelf must be able to
reverse-engineer its own code. This test runs the unifier over a real slice of the
shelf and pins that the synthesized report is COHERENT and HONEST: it resolves the
internal architecture, finds the data model, ranks keystones, and never rounds its
confidence up past its weakest rung.

Fast by design - it audits the Lab's own modules (a real, self-referential slice), not
the whole 296-module engine (that belongs in a `tools/` run, not a unit test).
"""

from __future__ import annotations

import pathlib

from kernel.shelf import repo_report

_SHELF = pathlib.Path(__file__).resolve().parent.parent / "parts" / "shelf"
_LAB_MODULES = (
    "source_analyzer",
    "repo_analyzer",
    "model_extractor",
    "api_diff",
    "call_graph",
    "cross_module",
    "control_flow",
    "cli_surface",
    "repo_report",
)


def _lab_package() -> dict[str, str]:
    """Load the Lab shelf modules as a {dotted_name: source} package."""
    return {
        f"kernel.shelf.{name}": (_SHELF / f"{name}.py").read_text(encoding="utf-8")
        for name in _LAB_MODULES
    }


def test_lab_reverse_engineers_itself() -> None:
    report = repo_report.synthesize(_lab_package(), package="kernel.shelf.reverse")
    assert report.module_count == len(_LAB_MODULES)
    # the unifier imports the single-snapshot rungs, so those rungs are the real hubs
    assert any("cross_module" in h or "call_graph" in h for h in report.hubs)
    # the Lab defines many public analyzer symbols
    assert report.public_symbols > 20


def test_overall_confidence_is_the_weakest_rung() -> None:
    report = repo_report.synthesize(_lab_package(), package="kernel.shelf.reverse")
    assert report.rung_confidence, "every rung must report a confidence"
    assert report.overall_confidence == min(report.rung_confidence.values())
    assert 0.0 < report.overall_confidence <= 1.0


def test_render_is_a_full_one_pass_report() -> None:
    out = repo_report.render(repo_report.synthesize(_lab_package(), package="lab"))
    for section in ("ARCHITECTURE", "DATA MODEL", "API SURFACE", "CODE HEALTH", "INVOCATION"):
        assert section in out
    assert "overall confidence" in out


def test_a_single_broken_module_never_aborts_the_audit() -> None:
    pkg = _lab_package()
    pkg["kernel.shelf.reverse.broken"] = "def oops(:\n    pass\n"
    report = repo_report.synthesize(pkg, package="lab")
    # honesty: a blind spot lowers confidence but the report still lands
    assert report.module_count == len(_LAB_MODULES) + 1
    assert report.overall_confidence < 1.0
