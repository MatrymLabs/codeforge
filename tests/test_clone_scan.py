"""Test twin for parts/clone_scan.py -- structural duplicate-logic detection."""

import pytest

from forge import handle_command
from parts.clone_scan import CloneError, find_clones, render, scan_repo, shape
from parts.world.session import Session

# Same structure and operators, different names and literals: a type-2 clone.
_A = """
def alpha(items):
    total = 0
    for it in items:
        if it > 0:
            total = total + it
    return total
"""
_B = """
def beta(values):
    acc = 5
    for v in values:
        if v > 0:
            acc = acc + v
    return acc
"""
_C = "def gamma(x):\n    return x + 1\n"


def test_shape_ignores_names_and_literals():
    import ast

    a = ast.parse(_A).body[0]
    b = ast.parse(_B).body[0]
    assert isinstance(a, ast.FunctionDef) and isinstance(b, ast.FunctionDef)
    assert shape(a) == shape(b)  # structurally identical despite different names/literals


def test_finds_a_type2_clone_pair():
    groups = find_clones({"a.py": _A, "b.py": _B}, min_nodes=5)
    assert len(groups) == 1
    names = {o.name for o in groups[0].occurrences}
    assert names == {"alpha", "beta"}


def test_distinct_shapes_are_not_grouped():
    assert find_clones({"a.py": _A, "c.py": _C}, min_nodes=1) == []


def test_min_nodes_filters_trivial_functions():
    assert find_clones({"a.py": _A, "b.py": _B}, min_nodes=1000) == []


def test_bad_source_fails_loud():
    with pytest.raises(CloneError):
        find_clones({"bad.py": "def oops(:\n"})


def test_render_empty_and_findings():
    assert "DRY" in render([])
    groups = find_clones({"a.py": _A, "b.py": _B}, min_nodes=5)
    out = render(groups)
    assert "alpha" in out and "beta" in out


def test_repo_scan_returns_groups():
    # Over the real parts library: returns a (possibly empty) list without error.
    assert isinstance(scan_repo(), list)


def test_clones_verb_is_tick_reachable():
    out = handle_command(Session(player_id="matrym", location="courtyard"), "clones")
    assert "Clone scan" in out


def test_clones_verb_accepts_a_min_nodes_arg():
    from parts.clone_scan import clones

    assert "Clone scan" in clones("500")  # a high bar: valid int, likely no clones


def test_clones_verb_rejects_a_bad_arg():
    from parts.clone_scan import clones

    assert "Usage" in clones("notanumber")
