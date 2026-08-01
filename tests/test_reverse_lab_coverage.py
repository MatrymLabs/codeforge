"""Edge-branch coverage for the Reverse-Engineering Lab shelf parts.

The nine rung test twins pin behavior; this exercises the remaining render branches
and edge inputs (dynamic constructs, forward references, truncation, unreached states)
so the honest paths are all executed, not just asserted in passing.
"""

from __future__ import annotations

from parts.shelf import (
    api_diff,
    call_graph,
    cli_surface,
    control_flow,
    cross_module,
    model_extractor,
    repo_analyzer,
    source_analyzer,
)


def test_source_analyzer_render_with_unknowns_and_attr_annotation() -> None:
    src = (
        "from dataclasses import dataclass\n"
        "@dataclass\n"
        "class Node:\n"
        "    parent: 'other.Ref'\n"
        "def f():\n"
        "    exec('x')\n"
    )
    out = source_analyzer.render(source_analyzer.analyze(src, module="m"))
    assert "UNKNOWNS" in out
    assert "entities" in out


def test_repo_analyzer_render_cycles_and_unknowns() -> None:
    pkg = {
        "p.a": (
            "from p.b import B\nimport importlib\n"
            "def g(n):\n    return importlib.import_module(n)\n"
        ),
        "p.b": "from p.a import A\n",
    }
    out = repo_analyzer.render(repo_analyzer.analyze_repo(pkg, package="p"))
    assert "IMPORT CYCLES" in out
    assert "UNKNOWNS" in out


def test_model_extractor_render_transitions_and_unreached() -> None:
    src = (
        "from enum import Enum\n"
        "class S(Enum):\n"
        "    A = 1\n"
        "    B = 2\n"
        "    C = 3\n"
        "class M:\n"
        "    def go(self):\n"
        "        self.s = S.A\n"
    )
    report = model_extractor.analyze(src, module="m")
    out = model_extractor.render(report)
    assert "state machine S" in out
    assert "-> A" in out
    assert "unreached states" in out  # B, C never assigned


def test_model_extractor_render_relationships_and_collection_annotation() -> None:
    src = (
        "from dataclasses import dataclass\n"
        "@dataclass\n"
        "class Leaf:\n"
        "    v: int\n"
        "@dataclass\n"
        "class Tree:\n"
        "    root: Leaf\n"
        "    leaves: list[Leaf]\n"
        "    maybe: Leaf | None\n"
    )
    report = model_extractor.analyze(src, module="m")
    kinds = {(r.target, r.kind) for r in report.relationships}
    assert ("Leaf", "reference") in kinds
    assert ("Leaf", "collection") in kinds
    assert ("Leaf", "optional") in kinds
    out = model_extractor.render(report)
    assert "relationships:" in out
    assert "--root" in out


def test_api_diff_kwonly_required_and_removed_varargs() -> None:
    old = "def f(a, *args):\n    return a\n"
    new = "def f(a, *, b):\n    return a\n"
    report = api_diff.diff(old, new, module="m")
    kinds = {c.kind for c in report.breaking}
    assert "removed_varargs" in kinds
    assert "added_required_param" in kinds  # keyword-only required b
    assert "[BREAKING]" in api_diff.render(report)


def test_call_graph_recursive_method_and_dynamic_dunder() -> None:
    src = (
        "class C:\n"
        "    def walk(self):\n"
        "        return self.walk()\n"
        "    def route(self, name):\n"
        "        return getattr(self, name)()\n"
    )
    report = call_graph.analyze(src, module="m")
    assert "C.walk" in report.recursive
    assert report.confidence < 1.0  # getattr() dispatch is an unknown


def test_cross_module_flatten_none_and_relative_escape_and_render() -> None:
    # a call in the attribute chain -> _flatten_attr returns None (no crash)
    pkg = {
        "p.a": "from p.b import build\ndef f():\n    return build()().x\n",
        "p.b": "def build():\n    return object\n",
        "p.sub.c": "from ... import wild\n",
    }
    report = cross_module.analyze_repo(pkg, package="p")
    out = cross_module.render(report)
    assert "cross-module: p" in out
    assert any("escapes the package root" in u for u in report.unknowns)


def test_cross_module_render_many_unused_truncates() -> None:
    pkg = {f"p.m{i}": f"def pub{i}():\n    return {i}\n" for i in range(15)}
    out = cross_module.render(cross_module.analyze_repo(pkg, package="p"))
    assert "more" in out  # >12 unused-public candidates -> "... and N more"


def test_control_flow_yield_from_is_generator() -> None:
    src = "def stream(xs):\n    yield from xs\n"
    p = {x.qualname: x for x in control_flow.analyze(src).functions}
    assert p["stream"].is_generator


def test_cli_surface_dynamic_default_and_nonliteral_subcommand() -> None:
    src = (
        "def build(p, computed):\n"
        "    sub = p.add_subparsers()\n"
        "    sub.add_parser(computed)\n"
        "    p.add_argument('--n', default=computed)\n"
        "    p.add_argument('--flag', required=True)\n"
    )
    report = cli_surface.analyze(src, module="m")
    opts = {o.flags: o for o in report.options}
    assert opts[("--n",)].default == "<dynamic>"
    assert opts[("--flag",)].required
    assert any("non-literal subcommand" in u for u in report.unknowns)
    out = cli_surface.render(report)
    assert "options:" in out
