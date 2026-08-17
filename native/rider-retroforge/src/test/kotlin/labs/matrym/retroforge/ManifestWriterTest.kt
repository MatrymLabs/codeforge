package labs.matrym.retroforge

import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class ManifestWriterTest {
    @Test
    fun syntheticRomManifestSerializesTraceableStableJsonWithoutMutation() {
        val bytes = syntheticRom()
        val before = bytes.copyOf()
        val rom = NesRom.load(bytes, sourcePath = "C:\\Users\\Josh\\retro\"forge.nes")

        val first = ManifestWriter.serialize(rom.manifest)
        val second = ManifestWriter.serialize(rom.manifest)

        assertTrue(first.contains("\"sourceChecksum\":\"" + rom.sourceChecksum() + "\""))
        assertEquals(rom.manifest.assets.size, first.split("\"assetId\"").size - 1)
        assertEquals(first, second)
        assertTrue(
            first.contains(
                "\"sourcePath\":\"C:\\\\Users\\\\Josh\\\\retro\\\"forge.nes\"",
            ),
        )
        assertContentEquals(before, bytes)
    }

    private fun syntheticRom(): ByteArray {
        val bytes = ByteArray(16 + 16 * 1024 + 8 * 1024)
        bytes[0] = 'N'.code.toByte()
        bytes[1] = 'E'.code.toByte()
        bytes[2] = 'S'.code.toByte()
        bytes[3] = 0x1a
        bytes[4] = 1
        bytes[5] = 1
        bytes[6] = 0x11
        bytes[7] = 0x00
        val chr = 16 + 16 * 1024
        repeat(8) { row ->
            bytes[chr + row] = 0xaa.toByte()
            bytes[chr + 8 + row] = 0x66
            bytes[chr + 16 + 8 + row] = 0xff.toByte()
        }
        return bytes
    }
}
