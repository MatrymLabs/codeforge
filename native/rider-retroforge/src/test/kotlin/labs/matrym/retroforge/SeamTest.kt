package labs.matrym.retroforge

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith

class SeamTest {
    @Test
    fun `a decoded tile reports its own dimensions`() {
        val tile = DecodedTile(listOf(listOf(0, 1), listOf(2, 3)), sourceOffset = 16, codecId = "nes.2bpp")
        assertEquals(2, tile.width)
        assertEquals(2, tile.height)
    }

    @Test
    fun `a ragged tile is refused rather than drawn`() {
        // A ragged tile renders as a plausible picture with a wrong row. Refuse at construction.
        assertFailsWith<IllegalArgumentException> {
            DecodedTile(listOf(listOf(0, 1), listOf(2)), sourceOffset = 0, codecId = "broken")
        }
    }

    @Test
    fun `an empty tile has zero dimensions rather than throwing`() {
        val tile = DecodedTile(emptyList(), sourceOffset = 0, codecId = "nes.2bpp")
        assertEquals(0, tile.width)
        assertEquals(0, tile.height)
    }

    @Test
    fun `a tile carries where it came from`() {
        val tile = DecodedTile(listOf(listOf(3)), sourceOffset = 8208, codecId = "nes.2bpp")
        assertEquals(8208, tile.sourceOffset)
        assertEquals("nes.2bpp", tile.codecId)
    }
}
