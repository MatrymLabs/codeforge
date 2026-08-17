package labs.matrym.retroforge

import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue

/**
 * A synthetic iNES image whose CHR is chosen so the two bit-planes are distinguishable in the
 * render. Tile 0 gets plane0 = 0xAA and plane1 = 0x66, which combine to palette indices
 * 1,2,3,0 repeated, exercising all four values. Tile 1 gets plane1 = 0xFF alone, so every pixel
 * is index 2. A projection that ignored a plane, or swapped them, could not produce both.
 */
private fun syntheticRom(): ByteArray {
    val bytes = ByteArray(16 + 16 * 1024 + 8 * 1024)
    bytes[0] = 'N'.code.toByte()
    bytes[1] = 'E'.code.toByte()
    bytes[2] = 'S'.code.toByte()
    bytes[3] = 0x1a
    bytes[4] = 1
    bytes[5] = 1
    val chr = 16 + 16 * 1024
    repeat(8) { row ->
        bytes[chr + row] = 0xaa.toByte()
        bytes[chr + 8 + row] = 0x66
        bytes[chr + 16 + 8 + row] = 0xff.toByte()
    }
    return bytes
}

/** The pixel rows of each rendered tile, in order, with the framing stripped. */
private fun renderedTiles(preview: String): List<List<String>> {
    val tiles = mutableListOf<List<String>>()
    var rows: MutableList<String>? = null
    preview.lineSequence().forEach { line ->
        when {
            line.startsWith("tile ") && line.endsWith("(") -> rows = mutableListOf()
            line == ")" -> rows?.let { tiles.add(it) }.also { rows = null }
            else -> rows?.add(line)
        }
    }
    return tiles
}

/** A source that hands back exactly the tiles it was given, for the refusal cases. */
private class FixedTiles(
    private val supplied: List<DecodedTile>,
) : TileSource {
    override fun tiles(bank: Int): List<DecodedTile> = supplied

    override fun sourceChecksum(): String = "fixed"
}

private fun flatTile(
    value: Int,
    size: Int = 8,
) = DecodedTile(
    indices = List(size) { List(size) { value } },
    sourceOffset = 0,
    codecId = "test",
)

class TileProjectionTest {
    @Test
    fun `synthetic ROM tiles are visible through the projection and source stays unchanged`() {
        val bytes = syntheticRom()
        val before = bytes.copyOf()
        val preview = AsciiTileProjection().render(NesRom.load(bytes, "synthetic.nes"), limit = 2)

        println("RF-001 DISPLAY PREVIEW\n$preview")
        assertTrue(preview.contains("source checksum:"))
        assertTrue(preview.contains("tile 0"))
        assertTrue(preview.contains(".+#"))
        assertTrue(preview.contains("++++++++"))
        assertContentEquals(before, bytes)
    }

    /**
     * The geometry of the display, which the `contains` assertions above cannot see.
     *
     * `contains("++++++++")` is satisfied by ANY row of eight or more plus signs, so a projection
     * that emitted 8x16, or put all 64 pixels on one line, would pass every other assertion here.
     * A tile is 8x8 and something has to say so.
     *
     * The expected shape is read off the DecodedTile rather than hardcoded, so this measures the
     * projection against the source it was handed, not against a number typed into a test.
     */
    @Test
    fun `each rendered tile has exactly the rows and columns of its decoded source`() {
        val source = NesRom.load(syntheticRom(), "synthetic.nes")
        val decoded = source.tiles(0).take(2)
        val rendered = renderedTiles(AsciiTileProjection().render(source, limit = 2))

        assertEquals(2, rendered.size, "limit=2 must render exactly two tiles")
        decoded.forEachIndexed { index, tile ->
            assertEquals(8, tile.height, "the NES 2bpp invariant: a tile is 8 rows")
            assertEquals(8, tile.width, "the NES 2bpp invariant: a tile is 8 columns")
            assertEquals(tile.height, rendered[index].size, "tile $index lost or gained rows")
            rendered[index].forEachIndexed { row, line ->
                assertEquals(tile.width, line.length, "tile $index row $row is the wrong width")
            }
        }
    }

    @Test
    fun `limit is honoured rather than ignored`() {
        val source = NesRom.load(syntheticRom(), "synthetic.nes")
        assertEquals(1, renderedTiles(AsciiTileProjection().render(source, limit = 1)).size)
    }

    // --- refusal: both `require` gates, shown to fail for the bad state they claim to catch ------

    @Test
    fun `a symbol set too small for 2bpp is refused at construction`() {
        val blast =
            assertFailsWith<IllegalArgumentException> {
                AsciiTileProjection(symbols = " .+")
            }
        assertTrue(blast.message!!.contains("four display symbols"))
    }

    @Test
    fun `a symbol set of exactly four is accepted, so the gate refuses too-small and nothing more`() {
        val rendered = renderedTiles(AsciiTileProjection(symbols = "abcd").render(FixedTiles(listOf(flatTile(3)))))
        assertEquals(listOf(List(8) { "dddddddd" }), rendered)
    }

    @Test
    fun `a non-positive limit is refused`() {
        val source = FixedTiles(listOf(flatTile(1)))
        listOf(0, -1).forEach { bad ->
            val blast =
                assertFailsWith<IllegalArgumentException> {
                    AsciiTileProjection().render(source, limit = bad)
                }
            assertTrue(blast.message!!.contains("limit must be positive"), "limit=$bad")
        }
    }
}
