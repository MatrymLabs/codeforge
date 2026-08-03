"""CARD: lock_expr -- a data-defined, composable access-control mini-language.

Authored seed content declares access AS DATA, e.g.
``rank(wizard) OR haskey(brass_key)`` or ``rank(builder) AND NOT flag(banned)``,
instead of hardcoding coarse rank checks or bespoke per-feature guards in Python.

The grammar is a boolean expression of lock-function calls ``name(arg1, arg2)``
combined with ``AND`` / ``OR`` / ``NOT`` and parentheses. Function names and args
are lowercase_snake_case / simple tokens. Precedence: NOT > AND > OR.

Evaluation calls ``funcs[name](ctx, *args)`` for each leaf; an unknown function
name raises loud (never silently False). AND/OR short-circuit; NOT negates.

Clean-room harvest (pattern, not code) from Evennia's
``locks/lockhandler.py`` + ``lockfuncs.py`` (BSD-3-Clause,
Copyright Evennia contributors). No source was copied; only the idea of a
data-defined lock string of boolean-combined lock functions was reused.

Implementation is a hand-written tokenizer plus recursive-descent parser. It
never uses ``eval`` or ``exec``.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Union


class LockError(ValueError):
    """Raised loud on a malformed expression or an unknown lock function.

    A parse failure (unbalanced parens, empty text, stray operator, bad token)
    or an unknown function name at evaluation time never degrades to a silent
    False; access-control that fails quiet is a security defect.
    """


# --- The evaluable tree --------------------------------------------------


@dataclass(frozen=True)
class Call:
    """A single lock-function leaf: ``name(arg1, arg2)``."""

    name: str
    args: tuple[str, ...]


@dataclass(frozen=True)
class Not:
    """Negation of a sub-expression."""

    child: Node


@dataclass(frozen=True)
class And:
    """Short-circuit conjunction of two sub-expressions."""

    left: Node
    right: Node


@dataclass(frozen=True)
class Or:
    """Short-circuit disjunction of two sub-expressions."""

    left: Node
    right: Node


Node = Union[Call, "Not", "And", "Or"]


@dataclass(frozen=True)
class LockExpr:
    """A parsed lock expression, ready to hand to :func:`evaluate`."""

    root: Call | Not | And | Or
    source: str


# --- Tokenizer -----------------------------------------------------------

# Keywords are matched case-sensitively as UPPER so a near-miss like ``and``
# is treated as an identifier and fails loud, never silently as an operator.
_TOKEN_RE = re.compile(
    r"""
      (?P<ws>\s+)
    | (?P<lparen>\()
    | (?P<rparen>\))
    | (?P<comma>,)
    | (?P<ident>[a-z_][a-z0-9_]*)
    | (?P<other>.)
    """,
    re.VERBOSE,
)

_KEYWORDS = {"AND", "OR", "NOT"}


@dataclass(frozen=True)
class _Tok:
    kind: str  # LPAREN RPAREN COMMA AND OR NOT IDENT
    text: str
    pos: int


def _tokenize(expr: str) -> list[_Tok]:
    """Split ``expr`` into tokens or raise :class:`LockError` on a bad glyph."""
    toks: list[_Tok] = []
    for m in _TOKEN_RE.finditer(expr):
        kind = m.lastgroup
        text = m.group()
        pos = m.start()
        if kind == "ws":
            continue
        if kind == "lparen":
            toks.append(_Tok("LPAREN", text, pos))
        elif kind == "rparen":
            toks.append(_Tok("RPAREN", text, pos))
        elif kind == "comma":
            toks.append(_Tok("COMMA", text, pos))
        elif kind == "ident":
            # A bare UPPER keyword arrives here only if lowercased; keywords are
            # a distinct scan below. Recognise the three operators explicitly.
            toks.append(_Tok("IDENT", text, pos))
        else:  # other: catch keywords (UPPER) and reject everything else.
            raise LockError(f"unexpected character {text!r} at position {pos}")
    return toks


def _scan(expr: str) -> list[_Tok]:
    """Tokenize, promoting UPPER keyword words to operator tokens.

    Keywords are UPPER and word-bounded so ``rank`` is never mistaken for a
    keyword and ``and`` (lowercase near-miss) stays an identifier that later
    fails loud as a missing function.
    """
    if not expr.strip():
        raise LockError("empty expression")

    # First lift out UPPER keyword words, tokenizing the gaps as lowercase.
    toks: list[_Tok] = []
    idx = 0
    kw_re = re.compile(r"\b(AND|OR|NOT)\b")
    for m in kw_re.finditer(expr):
        toks.extend(_tokenize(expr[idx : m.start()]))
        toks.append(_Tok(m.group(), m.group(), m.start()))
        idx = m.end()
    toks.extend(_tokenize(expr[idx:]))
    return toks


# --- Recursive-descent parser -------------------------------------------


class _Parser:
    """Recursive descent over the token stream. Precedence: NOT > AND > OR."""

    def __init__(self, toks: list[_Tok], source: str) -> None:
        self._toks = toks
        self._src = source
        self._i = 0

    def _peek(self) -> _Tok | None:
        return self._toks[self._i] if self._i < len(self._toks) else None

    def _next(self) -> _Tok:
        tok = self._peek()
        if tok is None:
            raise LockError(f"unexpected end of expression in {self._src!r}")
        self._i += 1
        return tok

    def parse(self) -> Call | Not | And | Or:
        node = self._or()
        rest = self._peek()
        if rest is not None:
            raise LockError(f"unexpected {rest.text!r} at position {rest.pos} in {self._src!r}")
        return node

    def _or(self) -> Call | Not | And | Or:
        node = self._and()
        while (tok := self._peek()) is not None and tok.kind == "OR":
            self._next()
            node = Or(node, self._and())
        return node

    def _and(self) -> Call | Not | And | Or:
        node = self._not()
        while (tok := self._peek()) is not None and tok.kind == "AND":
            self._next()
            node = And(node, self._not())
        return node

    def _not(self) -> Call | Not | And | Or:
        tok = self._peek()
        if tok is not None and tok.kind == "NOT":
            self._next()
            return Not(self._not())
        return self._atom()

    def _atom(self) -> Call | Not | And | Or:
        tok = self._next()
        if tok.kind == "LPAREN":
            node = self._or()
            close = self._next()
            if close.kind != "RPAREN":
                raise LockError(f"expected ')' at position {close.pos} in {self._src!r}")
            return node
        if tok.kind == "IDENT":
            return self._call(tok)
        raise LockError(f"unexpected {tok.text!r} at position {tok.pos} in {self._src!r}")

    def _call(self, name_tok: _Tok) -> Call:
        opener = self._next()
        if opener.kind != "LPAREN":
            raise LockError(
                f"expected '(' after {name_tok.text!r} at position {opener.pos} in {self._src!r}"
            )
        args: list[str] = []
        tok = self._peek()
        if tok is not None and tok.kind == "RPAREN":
            self._next()
            return Call(name_tok.text, ())
        while True:
            arg = self._next()
            if arg.kind != "IDENT":
                raise LockError(
                    f"expected an argument token at position {arg.pos} in {self._src!r}"
                )
            args.append(arg.text)
            sep = self._next()
            if sep.kind == "RPAREN":
                break
            if sep.kind != "COMMA":
                raise LockError(f"expected ',' or ')' at position {sep.pos} in {self._src!r}")
        return Call(name_tok.text, tuple(args))


# --- Public surface ------------------------------------------------------


def parse(expr: str) -> LockExpr:
    """Parse ``expr`` into an evaluable :class:`LockExpr`.

    Raises :class:`LockError` loud on any malformed syntax: empty text,
    unbalanced parentheses, a trailing operator, or a bad token.
    """
    toks = _scan(expr)
    root = _Parser(toks, expr).parse()
    return LockExpr(root=root, source=expr)


def evaluate(
    expr: LockExpr,
    funcs: dict[str, Callable[..., bool]],
    ctx: object,
) -> bool:
    """Evaluate a parsed ``expr``, calling ``funcs[name](ctx, *args)`` per leaf.

    AND / OR short-circuit; NOT negates. An unknown function name raises
    :class:`LockError` rather than degrading to a silent False.
    """

    def walk(node: Call | Not | And | Or) -> bool:
        if isinstance(node, Call):
            fn = funcs.get(node.name)
            if fn is None:
                raise LockError(f"unknown lock function {node.name!r}")
            return bool(fn(ctx, *node.args))
        if isinstance(node, Not):
            return not walk(node.child)
        if isinstance(node, And):
            return walk(node.left) and walk(node.right)
        # Or
        return walk(node.left) or walk(node.right)

    return walk(expr.root)


def check(
    expr_str: str,
    funcs: dict[str, Callable[..., bool]],
    ctx: object,
) -> bool:
    """Convenience: parse ``expr_str`` then evaluate it in one call."""
    return evaluate(parse(expr_str), funcs, ctx)
