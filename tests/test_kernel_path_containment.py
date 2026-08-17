"""CARD: test_kernel_path_containment -- the store refuses a hostile seed id at the call site.

WHY THIS FILE EXISTS. CodeQL raised `py/path-injection` (HIGH) against
`FileSeedStore.load`, on the line that reads a record from a path derived from a caller-supplied
`seed_id`. The finding is a FALSE POSITIVE: `_path` runs the id through `safe_segment` and bounds
the result with `contained_path`, and CodeQL does not model either as a sanitizer.

A suppression that merely asserts "this is sanitized" is worth nothing, because nothing then fails
if the sanitizer is later removed. `tests/test_safe_path.py` proves the sanitizer in isolation, but
NOTHING proved it at the flagged call site: every existing store test passes a well-formed id.

So this file drives the store itself with hostile input. If anyone strips `safe_segment` or
`contained_path` out of `_path`, these tests fail, the suppression's justification becomes visibly
false, and the gate is heard again. The suppression and this file are one control, not two.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kernel.seedlab.kernel import FileSeedStore
from kernel.seedlab.safe_path import PathEscape

# Hostile ids, per the house rule that test data includes near-misses and not only obvious junk.
HOSTILE_IDS = [
    "../escape",
    "../../etc/passwd",
    "..",
    ".",
    "nested/child",
    "nested\\child",
    "/absolute",
    "C:/absolute",
    "",
    "   ",
    "with\x00nul",
]


@pytest.mark.parametrize("seed_id", HOSTILE_IDS)
def test_load_refuses_a_hostile_seed_id(tmp_path: Path, seed_id: str) -> None:
    """`load` must REFUSE, never read. A traversal id must not reach the filesystem."""
    store = FileSeedStore(tmp_path / "seeds")
    with pytest.raises(PathEscape):
        store.load(seed_id)


def test_a_traversal_id_cannot_read_a_file_outside_the_root(tmp_path: Path) -> None:
    """The sharp version: plant a real file outside the root and prove it stays unreachable."""
    secret = tmp_path / "secret.json"
    secret.write_text('{"stolen": true}', encoding="utf-8")
    store = FileSeedStore(tmp_path / "seeds")

    with pytest.raises(PathEscape):
        store.load("../secret")

    # And the file is still there, unread by the store: refusal, not a partial read.
    assert secret.read_text(encoding="utf-8") == '{"stolen": true}'


def test_a_well_formed_id_still_works(tmp_path: Path) -> None:
    """Calibration. A gate that refuses everything is not a gate, it is a wall."""
    store = FileSeedStore(tmp_path / "seeds")
    assert store.load("seed-jt") is None  # absent, not refused
