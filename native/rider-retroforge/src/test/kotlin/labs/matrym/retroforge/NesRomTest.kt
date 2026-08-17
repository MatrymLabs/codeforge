package labs.matrym.retroforge

import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith

class NesRomTest {
    @Test
    fun `synthetic iNES ROM loads decodes CHR and records provenance without mutation`() {
        val bytes = syntheticRom()
        val before = bytes.copyOf()

        val rom = NesRom.load(bytes, sourcePath = "synthetic.nes")

        assertEquals(16 * 1024, rom.header.prgRomBytes)
        assertEquals(8 * 1024, rom.header.chrRomBytes)
        assertEquals(1, rom.header.mapper)
        assertEquals("vertical", rom.header.mirroring)
        assertEquals(512, rom.tiles(0).size)
        assertEquals(
            listOf(1, 2, 3, 0, 1, 2, 3, 0),
            rom
                .tiles(0)
                .first()
                .indices
                .first(),
        )
        assertEquals(listOf(2, 2, 2, 2, 2, 2, 2, 2), rom.tiles(0)[1].indices.first())
        assertEquals("synthetic.nes", rom.manifest.sourcePath)
        assertEquals("nes", rom.manifest.platform)
        assertEquals(512, rom.manifest.assets.size)
        assertEquals(rom.sourceChecksum(), rom.manifest.sourceChecksum)
        assertEquals(
            rom.sourceChecksum(),
            rom.manifest.assets
                .first()
                .sourceChecksum,
        )
        assertContentEquals(before, bytes)
    }

    @Test
    fun `invalid iNES magic is refused`() {
        assertFailsWith<IllegalArgumentException> { NesRom.load(ByteArray(16)) }
    }

    private fun syntheticRom(): ByteArray {
        val bytes = ByteArray(16 + 16 * 1024 + 8 * 1024)
        bytes[0] = 'N'.code.toByte()
        bytes[1] = 'E'.code.toByte()
        bytes[2] = 'S'.code.toByte()
        bytes[3] = 0x1a
        bytes[4] = 1 // one 16 KiB PRG unit
        bytes[5] = 1 // one 8 KiB CHR unit
        bytes[6] = 0x11 // vertical mirroring, mapper low nibble 1
        bytes[7] = 0x00

        val chr = 16 + 16 * 1024
        for (row in 0 until 8) {
            bytes[chr + row] = 0xaa.toByte() // low plane: 1,0,1,0,...
            bytes[chr + 8 + row] = 0x66 // high plane: 0,1,1,0,...
            bytes[chr + 16 + 8 + row] = 0xff.toByte() // second tile: index 2
        }
        return bytes
    }
}
