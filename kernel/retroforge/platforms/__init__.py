"""Format modules, each named by the TECHNIQUE it decodes rather than by a console brand.

Principal Engineer ruling 2026-08-14. A console name is a brand; `planar 2bpp` is what the format
is. An era name was considered and rejected: three different 8-bit machines store tiles three
incompatible ways, so `eightbit` would name a generality that does not exist.
"""

from kernel.retroforge.platforms.planar_2bpp import (
    HeaderedCartridgeModule,
    Planar2BppTileCodec,
)

__all__ = ["HeaderedCartridgeModule", "Planar2BppTileCodec"]
