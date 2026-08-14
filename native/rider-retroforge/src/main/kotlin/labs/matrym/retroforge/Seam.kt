package labs.matrym.retroforge

/**
 * The seam between the RetroForge core and the Rider projection.
 *
 * The projection is handed tiles that are ALREADY DECODED. It receives palette indices, never
 * bytes and never colours, because the moment this side can see raw ROM bytes somebody will decode
 * them here, and the one architectural rule of this lane is that decoding does not live in UI
 * classes.
 *
 * Indices rather than colours for the same reason the core uses them: a palette swap must not be a
 * re-decode.
 */
data class DecodedTile(
    val indices: List<List<Int>>,
    val sourceOffset: Int,
    val codecId: String,
) {
    val width: Int get() = indices.firstOrNull()?.size ?: 0
    val height: Int get() = indices.size

    init {
        require(indices.all { it.size == width }) { "a tile must be rectangular" }
    }
}

/**
 * What the projection needs from the core, and nothing more.
 *
 * Deliberately narrow. A wide interface here is how format knowledge migrates into the plugin one
 * convenience method at a time.
 */
interface TileSource {
    /** Tiles for the given bank, already decoded by the core. */
    fun tiles(bank: Int): List<DecodedTile>

    /** The source checksum every displayed tile traces back to. */
    fun sourceChecksum(): String
}
