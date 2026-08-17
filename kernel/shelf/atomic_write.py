"""CARD: atomic_write -- write a file so a reader (or a crash) never sees a half-written file.

Reverse-engineered from the write-to-temp-then-rename durability idiom, whose atomicity rests on
POSIX rename(2) / os.replace being an atomic operation within one filesystem: write the full
contents to a sibling temp file, then atomically replace the target. A crash mid-write leaves either
the intact old file or the intact new file, never a truncated one; a concurrent reader always sees a
complete file.

Extracted on its THIRD real occurrence: the Seed store, the model store, and the backup manager each
re-derived `tmp.write_text(...); tmp.replace(target)` independently. This is the one certified
primitive they now share (second-consumer pull gate, well cleared).

Honest scope: this guarantees ATOMICITY (no partial file), not fsync-DURABILITY (a power loss right
after replace may still lose the last write from the OS cache) -- matching the behavior of the
callers it replaces. Pass `fsync=True` when a store needs the stronger guarantee. Engine-free
(stdlib only), so it pours to the Hardware Store shelf and runs with no engine present. Clean-room
(original; the rename-for-atomicity technique is public POSIX semantics, not copied code).
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def atomic_write_text(
    path: str | os.PathLike[str], text: str, *, encoding: str = "utf-8", fsync: bool = False
) -> None:
    """Atomically write `text` to `path`. The temp file is created in the TARGET's own directory (so
    the final replace is a same-filesystem rename, which is atomic) and cleaned up if anything
    fails. With `fsync=True` the bytes are flushed to disk before the replace, for power-loss
    durability."""
    _atomic_write(Path(path), text.encode(encoding), fsync=fsync)


def atomic_write_bytes(path: str | os.PathLike[str], data: bytes, *, fsync: bool = False) -> None:
    """Atomically write raw `data` to `path` (the same atomicity guarantee as atomic_write_text)."""
    _atomic_write(Path(path), data, fsync=fsync)


def _atomic_write(target: Path, data: bytes, *, fsync: bool) -> None:
    # mkstemp in the target's directory gives a unique temp name (no collision between concurrent
    # writers) on the SAME filesystem, so os.replace below is a genuine atomic rename.
    fd, tmp_name = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.", suffix=".tmp")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            if fsync:
                handle.flush()
                os.fsync(handle.fileno())
        os.replace(  # noqa: PTH105
            tmp, target
        )  # atomic within one filesystem; never a half-written target
    except BaseException:
        tmp.unlink(missing_ok=True)  # a failed write leaves no orphan temp behind
        raise
