"""Test twin for kernel/seedlab/safe_path.py -- the gate that keeps a Seed id inside its store.

Acceptance: an ordinary id resolves to a path under the root, several segments nest, and the
returned path is absolute and resolved.

Refusal (fail loud): `..` alone, `..` buried in a longer traversal, a separator of either
platform, an absolute path, a drive-qualified path, empty and whitespace-only names, a NUL byte,
and a symlink that points outside the root. Every refusal is PathEscape, never a silent rewrite.

The hostile cases are the point. This module exists because CodeQL found 12 high-severity
path-injection sinks in the Seed stores, and because the sanitiser that WAS present mapped
`..` to `..` unchanged, since every character in it was on the allowlist.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from kernel.seedlab.safe_path import PathEscape, contained_path, safe_segment

# --- acceptance: ordinary ids are honoured ------------------------------------------------------


def test_a_plain_id_lands_under_the_root(tmp_path: Path) -> None:
    got = contained_path(tmp_path, "seed-jt")
    assert got == (tmp_path / "seed-jt").resolve()
    assert got.is_absolute()


def test_several_segments_nest_in_order(tmp_path: Path) -> None:
    got = contained_path(tmp_path, "seed-jt", "model-01.json")
    assert got == (tmp_path / "seed-jt" / "model-01.json").resolve()


def test_ids_that_merely_look_alarming_are_allowed(tmp_path: Path) -> None:
    # A dot or a dash inside a name is not traversal; only the exact `.`/`..` names are.
    for ok in ("seed.jt", "..seed", "seed..", "a..b", "-seed-", "_seed_"):
        assert contained_path(tmp_path, ok).parent == tmp_path.resolve()


def test_safe_segment_returns_the_value_unchanged(tmp_path: Path) -> None:
    assert safe_segment("seed-jt") == "seed-jt"  # a gate, not a rewriter


# --- refusal: the traversal that actually shipped ------------------------------------------------


def test_the_bare_parent_directory_is_refused(tmp_path: Path) -> None:
    # The regression that motivated this module: `_safe_segment("..")` returned ".." unchanged.
    with pytest.raises(PathEscape, match="traversal"):
        contained_path(tmp_path, os.pardir)


def test_the_current_directory_is_refused(tmp_path: Path) -> None:
    with pytest.raises(PathEscape, match="traversal"):
        contained_path(tmp_path, os.curdir)


def test_a_climbing_relative_path_is_refused(tmp_path: Path) -> None:
    with pytest.raises(PathEscape, match="separator"):
        contained_path(tmp_path, "../../etc/passwd")


def test_a_separator_inside_a_segment_is_refused(tmp_path: Path) -> None:
    for hostile in ("a/b", "a\\b", "seed/../../root"):
        with pytest.raises(PathEscape, match="separator"):
            contained_path(tmp_path, hostile)


def test_an_absolute_path_is_refused(tmp_path: Path) -> None:
    with pytest.raises(PathEscape):
        contained_path(tmp_path, "/etc/passwd")


def test_an_empty_or_blank_segment_is_refused(tmp_path: Path) -> None:
    for blank in ("", "   ", "\t"):
        with pytest.raises(PathEscape, match="empty"):
            contained_path(tmp_path, blank)


def test_a_nul_byte_is_refused(tmp_path: Path) -> None:
    with pytest.raises(PathEscape, match="NUL"):
        contained_path(tmp_path, "seed\x00.json")


def test_no_segments_at_all_is_refused(tmp_path: Path) -> None:
    with pytest.raises(PathEscape, match="at least one"):
        contained_path(tmp_path)


def test_the_error_names_what_was_refused(tmp_path: Path) -> None:
    with pytest.raises(PathEscape, match="model id"):
        contained_path(tmp_path, os.pardir, what="model id")


# --- refusal: the second check, which the first cannot make -------------------------------------


def test_a_symlink_pointing_outside_the_root_is_refused(tmp_path: Path) -> None:
    """A segment can be a perfectly plain name and still leave the root.

    This is why the bounds check exists alongside the shape check: `escape` is a legal filename,
    so `safe_segment` passes it, and only resolving it reveals that it leaves the store.
    """
    root = tmp_path / "store"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        (root / "escape").symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):  # pragma: no cover - platform without symlinks
        pytest.skip("this platform does not allow creating symlinks")
    with pytest.raises(PathEscape, match="escapes its root"):
        contained_path(root, "escape", "secret.json")
