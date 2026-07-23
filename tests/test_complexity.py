"""Test twin for parts/complexity.py -- cyclomatic complexity, the Analyze third fold."""

import ast

import pytest

from forge import handle_command
from parts.complexity import (
    ComplexityError,
    complexity,
    complexity_of,
    render,
    scan_source,
)
from parts.world.session import Session

_SRC = """
def branchy(x):
    if x:                 # +1
        for i in x:       # +1
            if i and x:   # +1 (if) +1 (and)
                pass
    return x


def flat(y):
    return y + 1
"""


def _func(src: str) -> ast.FunctionDef:
    node = ast.parse(src).body[0]
    assert isinstance(node, ast.FunctionDef)
    return node


def test_flat_function_is_complexity_one():
    assert complexity_of(_func("def f(y):\n    return y + 1\n")) == 1


def test_branches_and_boolops_count():
    # if + for + if + (a and b) = 1 + 4 = 5
    assert complexity_of(_func(_SRC.strip())) == 5


def test_comprehension_counts_loop_and_filters():
    # base 1 + comprehension (1) + one filter (1) = 3
    assert complexity_of(_func("def f(xs):\n    return [x for x in xs if x > 0]\n")) == 3


def test_nested_function_is_scored_separately():
    src = """
def outer(x):
    def inner(y):
        if y:
            return 1
        return 0
    return inner
"""
    by_name = {f.name: f.complexity for f in scan_source(src)}
    assert by_name["outer"] == 1  # outer has no branches of its own
    assert by_name["inner"] == 2  # inner's own `if`


def test_scan_source_sorts_most_complex_first():
    results = scan_source(_SRC)
    assert results[0].name == "branchy"
    assert results[0].complexity > results[-1].complexity


def test_bad_source_fails_loud():
    with pytest.raises(ComplexityError):
        scan_source("def oops(:\n")


def test_render_empty_and_findings():
    assert "lean" in render([], threshold=10)
    from parts.complexity import FunctionComplexity

    out = render([("x.py", FunctionComplexity("f", 12, 3))], threshold=10)
    assert "f" in out and "12" in out


def test_complexity_verb_is_tick_reachable():
    out = handle_command(Session(player_id="matrym", location="courtyard"), "complexity")
    assert "Complexity" in out


def test_complexity_verb_rejects_bad_threshold():
    assert "Usage" in complexity("notanumber")
