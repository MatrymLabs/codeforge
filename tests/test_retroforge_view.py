"""Test twin for kernel/retroforge/view.py, the L1 surface.

The load-bearing cases are the REFUSALS and the offsets. A viewer that prints something pretty for
any input is a demo; one that refuses a non-cartridge, refuses to report success if the source
changed, and labels every tile with the address it came from is a tool.

Every fixture here is synthetic and built in memory. No cartridge image is read from disk or
committed, which the RetroForge legal block treats as a never-automate item.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kernel.retroforge.view import SHADES, TILE_SIDE, render_sheet, render_tile, view

_TILE = bytes(
    (
        *(0x80, 0x40, 0x20, 0x10, 0x08, 0x04, 0x02, 0xFF),
        *(0x80, 0x40, 0x20, 0x10, 0x08, 0x04, 0x02, 0x00),
    )
)


def _rom(tiles: int = 4) -> bytes:
    header = b"NES\x1a" + bytes([1, 1]) + bytes(10)
    return header + bytes(16 * 1024) + (_TILE * tiles).ljust(8 * 1024, b"\x00")


def _write(tmp_path: Path, data: bytes, name: str = "synthetic.nes") -> Path:
    path = tmp_path / name
    path.write_bytes(data)
    return path


def test_a_cartridge_renders_and_reports_success(tmp_path: Path, capsys) -> None:
    assert view(_write(tmp_path, _rom()), tile_count=2, columns=2) == 0
    out = capsys.readouterr().out
    assert "headered-cartridge" in out
    assert "source unchanged" in out


def test_every_tile_is_labelled_with_its_rom_offset(tmp_path: Path, capsys) -> None:
    """The half of click-to-offset a console can honestly do. A tile you cannot locate in the file
    is a picture; a tile with its address is a finding."""
    view(_write(tmp_path, _rom()), tile_count=2, columns=2)
    out = capsys.readouterr().out
    assert "@0x4010" in out  # 16-byte header + 16KB PRG
    assert "@0x4020" in out  # one tile later, 16 bytes on


def test_a_non_cartridge_is_refused_not_rendered(tmp_path: Path, capsys) -> None:
    """A viewer that renders anything handed to it teaches nothing about what it read."""
    assert view(_write(tmp_path, b"SEGA" + _rom()[4:]), tile_count=1) == 1
    assert "not a headered cartridge" in capsys.readouterr().err


def test_an_unreadable_path_fails_cleanly(tmp_path: Path, capsys) -> None:
    assert view(tmp_path / "nope.nes") == 2
    assert "cannot read" in capsys.readouterr().err


def test_render_tile_maps_every_palette_index_to_ink() -> None:
    tile = tuple(tuple(range(4)) * 2 for _ in range(TILE_SIDE))
    rendered = render_tile(tile)
    assert len(rendered) == TILE_SIDE
    assert set("".join(rendered)) <= set(SHADES)


def test_the_sheet_lays_tiles_out_in_the_requested_columns() -> None:
    tiles = [tuple((0,) * TILE_SIDE for _ in range(TILE_SIDE))] * 4
    lines = render_sheet(tiles, [0, 16, 32, 48], columns=2)
    offset_rows = [ln for ln in lines if ln.startswith("@")]
    assert len(offset_rows) == 2  # 4 tiles, 2 per row
    assert "@0x0" in offset_rows[0] and "@0x10" in offset_rows[0]


@pytest.mark.parametrize("count", [1, 3, 8])
def test_the_tile_count_is_honoured(tmp_path: Path, capsys, count: int) -> None:
    view(_write(tmp_path, _rom(8)), tile_count=count, columns=4)
    assert f"showing {count} tile(s)" in capsys.readouterr().out
