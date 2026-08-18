package labs.matrym.retroforge

/** Serializes RF-001 extraction provenance without adding a JSON dependency. */
object ManifestWriter {
    fun serialize(manifest: NesExtractionManifest): String =
        buildString {
            append('{')
            append("\"sourcePath\":").append(quoted(manifest.sourcePath))
            append(",\"sourceChecksum\":").append(quoted(manifest.sourceChecksum))
            append(",\"platform\":").append(quoted(manifest.platform))
            append(",\"assets\":[")
            manifest.assets.forEachIndexed { index, asset ->
                if (index > 0) {
                    append(',')
                }
                append('{')
                append("\"assetId\":").append(quoted(asset.assetId))
                append(",\"kind\":").append(quoted(asset.kind))
                append(",\"offset\":").append(asset.offset)
                append(",\"byteLength\":").append(asset.byteLength)
                append(",\"codecId\":").append(quoted(asset.codecId))
                append(",\"sourceChecksum\":").append(quoted(asset.sourceChecksum))
                append('}')
            }
            append("]}")
        }

    private fun quoted(value: String): String =
        buildString {
            append('"')
            value.forEach { character ->
                when (character) {
                    '"' -> append("\\\"")
                    '\\' -> append("\\\\")
                    '\b' -> append("\\b")
                    '\u000c' -> append("\\f")
                    '\n' -> append("\\n")
                    '\r' -> append("\\r")
                    '\t' -> append("\\t")
                    else ->
                        if (character.code < 0x20) {
                            append("\\u")
                            append(character.code.toString(16).padStart(4, '0'))
                        } else {
                            append(character)
                        }
                }
            }
            append('"')
        }
}
