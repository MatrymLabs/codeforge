package labs.matrym.retroforge

import java.security.MessageDigest

/** The decoded metadata carried by an iNES 1.0 header. */
data class NesHeader(
    val prgRomBytes: Int,
    val chrRomBytes: Int,
    val mapper: Int,
    val trainerPresent: Boolean,
    val mirroring: String,
)

data class NesExtractedAsset(
    val assetId: String,
    val kind: String,
    val offset: Int,
    val byteLength: Int,
    val codecId: String,
    val sourceChecksum: String,
)

/** Provenance for the bytes and every tile derived from them. */
data class NesExtractionManifest(
    val sourcePath: String,
    val sourceChecksum: String,
    val platform: String,
    val assets: List<NesExtractedAsset>,
)

/** A read-only NES iNES ROM projection for RF-001. */
class NesRom private constructor(
    val sourcePath: String,
    val header: NesHeader,
    private val checksum: String,
    private val decodedTiles: List<DecodedTile>,
    val manifest: NesExtractionManifest,
) : TileSource {
    override fun tiles(bank: Int): List<DecodedTile> {
        require(bank >= 0) { "bank must be non-negative" }
        val first = bank * TILES_PER_BANK
        require(first < decodedTiles.size) { "CHR bank $bank is out of range" }
        return decodedTiles.subList(first, minOf(first + TILES_PER_BANK, decodedTiles.size))
    }

    override fun sourceChecksum(): String = checksum

    companion object {
        private const val HEADER_BYTES = 16
        private const val TRAINER_BYTES = 512
        private const val PRG_UNIT_BYTES = 16 * 1024
        private const val CHR_UNIT_BYTES = 8 * 1024
        private const val TILE_BYTES = 16
        private const val TILES_PER_BANK = CHR_UNIT_BYTES / TILE_BYTES

        fun load(
            bytes: ByteArray,
            sourcePath: String = "<memory>",
        ): NesRom {
            require(bytes.size >= HEADER_BYTES) { "iNES ROM is shorter than its 16-byte header" }
            require(
                bytes[0] == 'N'.code.toByte() &&
                    bytes[1] == 'E'.code.toByte() &&
                    bytes[2] == 'S'.code.toByte() &&
                    bytes[3] == 0x1a.toByte(),
            ) {
                "missing iNES magic"
            }

            val flags6 = u8(bytes[6])
            val flags7 = u8(bytes[7])
            val prgRomBytes = u8(bytes[4]) * PRG_UNIT_BYTES
            val chrRomBytes = u8(bytes[5]) * CHR_UNIT_BYTES
            require(chrRomBytes > 0) { "CHR RAM-only cartridges are not supported by RF-001" }

            val trainerPresent = flags6 and 0x04 != 0
            val chrOffset = HEADER_BYTES + (if (trainerPresent) TRAINER_BYTES else 0) + prgRomBytes
            require(chrOffset + chrRomBytes <= bytes.size) {
                "iNES header points past the end of the ROM"
            }

            val header =
                NesHeader(
                    prgRomBytes = prgRomBytes,
                    chrRomBytes = chrRomBytes,
                    mapper = (flags7 and 0xf0) or (flags6 ushr 4),
                    trainerPresent = trainerPresent,
                    mirroring = if (flags6 and 1 != 0) "vertical" else "horizontal",
                )
            val checksum = sha256(bytes)
            val tiles =
                (0 until chrRomBytes / TILE_BYTES).map { index ->
                    decodeTile(bytes, chrOffset + index * TILE_BYTES)
                }
            val assets =
                tiles.mapIndexed { index, tile ->
                    NesExtractedAsset(
                        assetId = "chr-tile-$index",
                        kind = "tile",
                        offset = tile.sourceOffset,
                        byteLength = TILE_BYTES,
                        codecId = tile.codecId,
                        sourceChecksum = checksum,
                    )
                }
            return NesRom(
                sourcePath = sourcePath,
                header = header,
                checksum = checksum,
                decodedTiles = tiles,
                manifest = NesExtractionManifest(sourcePath, checksum, "nes", assets),
            )
        }

        private fun decodeTile(
            bytes: ByteArray,
            offset: Int,
        ): DecodedTile {
            val rows =
                (0 until 8).map { y ->
                    val low = u8(bytes[offset + y])
                    val high = u8(bytes[offset + 8 + y])
                    (0 until 8).map { x ->
                        val bit = 7 - x
                        (((high ushr bit) and 1) shl 1) or ((low ushr bit) and 1)
                    }
                }
            return DecodedTile(rows, sourceOffset = offset, codecId = "nes.2bpp")
        }

        private fun u8(value: Byte): Int = value.toInt() and 0xff

        private fun sha256(bytes: ByteArray): String =
            MessageDigest
                .getInstance("SHA-256")
                .digest(bytes)
                .joinToString("") { "%02x".format(it) }
    }
}
