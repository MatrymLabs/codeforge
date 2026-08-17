package labs.matrym.retroforge

import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertTrue

class TileProjectionTest {
    @Test
    fun `synthetic ROM tiles are visible through the projection and source stays unchanged`() {
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
        val before = bytes.copyOf()
        val preview = AsciiTileProjection().render(NesRom.load(bytes, "synthetic.nes"), limit = 2)

        println("RF-001 DISPLAY PREVIEW\n$preview")
        assertTrue(preview.contains("source checksum:"))
        assertTrue(preview.contains("tile 0"))
        assertTrue(preview.contains(".+#"))
        assertTrue(preview.contains("++++++++"))
        assertContentEquals(before, bytes)
    }
}
