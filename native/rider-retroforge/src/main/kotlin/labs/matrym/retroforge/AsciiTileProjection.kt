package labs.matrym.retroforge

/** A human-visible projection of decoded palette indices, with provenance kept on the display. */
class AsciiTileProjection(
    private val symbols: String = " .+#",
) {
    init {
        require(symbols.length >= 4) { "the NES 2bpp projection needs four display symbols" }
    }

    fun render(
        source: TileSource,
        bank: Int = 0,
        limit: Int = Int.MAX_VALUE,
    ): String {
        require(limit > 0) { "limit must be positive" }
        val tiles = source.tiles(bank).take(limit)
        return buildString {
            append("source checksum: ").append(source.sourceChecksum()).append('\n')
            tiles.forEachIndexed { index, tile ->
                append("tile ").append(index).append(" (\n")
                tile.indices.forEach { row ->
                    append(
                        row.joinToString(separator = "") { pixel ->
                            symbols.getOrElse(pixel) { error("palette index $pixel is outside the 2bpp range") }.toString()
                        },
                    ).append('\n')
                }
                append(")\n")
            }
        }
    }
}
