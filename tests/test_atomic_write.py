"""Test twin for kernel/shelf/atomic_write.py -- the atomic file-write durability primitive.

Acceptance: text and bytes are written; an existing file is overwritten with the new contents; no
temp file is left behind after a successful write; the fsync path still writes.

Refusal / robustness (fail loud, leave nothing partial): a write whose final replace fails raises,
cleans up its temp file (no orphan), and a missing parent directory raises without creating the
target.
"""

from __future__ import annotations

import pytest

from kernel.shelf.atomic_write import atomic_write_bytes, atomic_write_text

# --- acceptance --------------------------------------------------------------------------------


def test_writes_text(tmp_path):
    target = tmp_path / "f.txt"
    atomic_write_text(target, "hello")
    assert target.read_text(encoding="utf-8") == "hello"


def test_writes_bytes(tmp_path):
    target = tmp_path / "f.bin"
    atomic_write_bytes(target, b"\x00\x01\x02")
    assert target.read_bytes() == b"\x00\x01\x02"


def test_overwrites_an_existing_file(tmp_path):
    target = tmp_path / "f.txt"
    atomic_write_text(target, "v1")
    atomic_write_text(target, "v2")
    assert target.read_text(encoding="utf-8") == "v2"


def test_leaves_no_orphan_temp_after_success(tmp_path):
    target = tmp_path / "f.txt"
    atomic_write_text(target, "hello")
    # the temp sibling is created in the target's dir and must be gone after the atomic replace
    assert list(tmp_path.glob("*.tmp")) == []
    assert [p.name for p in tmp_path.iterdir()] == ["f.txt"]


def test_fsync_path_still_writes(tmp_path):
    target = tmp_path / "f.txt"
    atomic_write_text(target, "durable", fsync=True)
    assert target.read_text(encoding="utf-8") == "durable"


# --- refusal / robustness ----------------------------------------------------------------------


def test_a_failed_replace_raises_and_cleans_up_its_temp(tmp_path):
    # Make the target an existing directory: os.replace(tempfile, dir) fails, exercising the cleanup
    # path. The write must raise and leave NO orphan temp behind.
    target = tmp_path / "adir"
    target.mkdir()
    with pytest.raises(OSError):
        atomic_write_text(target, "x")
    assert list(tmp_path.glob("*.tmp")) == []  # temp cleaned up despite the failure


def test_a_missing_parent_dir_raises_without_creating_the_target(tmp_path):
    target = tmp_path / "nope" / "f.txt"  # parent 'nope' does not exist
    with pytest.raises(FileNotFoundError):
        atomic_write_text(target, "x")
    assert not target.exists()
