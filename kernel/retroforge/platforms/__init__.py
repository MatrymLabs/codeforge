"""Platform modules: one per console, each describing that console's published formats."""

from kernel.retroforge.platforms.nes import Nes2BppTileCodec, NesPlatformModule

__all__ = ["Nes2BppTileCodec", "NesPlatformModule"]
