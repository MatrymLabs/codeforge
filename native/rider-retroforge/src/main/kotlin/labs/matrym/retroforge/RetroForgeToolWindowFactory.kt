package labs.matrym.retroforge

import com.intellij.openapi.project.Project
import com.intellij.openapi.wm.ToolWindow
import com.intellij.openapi.wm.ToolWindowFactory
import com.intellij.ui.components.JBScrollPane
import com.intellij.ui.components.JBTextArea
import com.intellij.ui.content.ContentFactory
import java.awt.Font

/** An NES tile is 8x8 pixels. Not a display choice: it is the cartridge format. */
private const val TILE_SIDE = 8

/** 2bpp means two bits per pixel, so exactly four palette indices exist. */
private const val PALETTE_SIZE = 4

/** Point size for the preview. Monospaced and large enough that a tile reads as a shape. */
private const val PREVIEW_FONT_POINTS = 14

/** The first editor surface: a read-only preview of the existing projection contract. */
class RetroForgeToolWindowFactory : ToolWindowFactory {
    override fun createToolWindowContent(
        project: Project,
        toolWindow: ToolWindow,
    ) {
        val preview =
            JBTextArea().apply {
                text = AsciiTileProjection().render(PreviewTileSource, limit = 1)
                isEditable = false
                lineWrap = false
                font = Font(Font.MONOSPACED, Font.PLAIN, PREVIEW_FONT_POINTS)
            }
        val content = ContentFactory.getInstance().createContent(JBScrollPane(preview), null, false)
        toolWindow.contentManager.addContent(content)
    }
}

/** A decoded, synthetic tile keeps this scaffold independent of ROM loading and click handling. */
private object PreviewTileSource : TileSource {
    override fun tiles(bank: Int): List<DecodedTile> {
        require(bank == 0) { "the scaffold preview has one tile bank" }
        return listOf(
            DecodedTile(
                indices = List(TILE_SIDE) { row -> List(TILE_SIDE) { col -> (row + col) % PALETTE_SIZE } },
                sourceOffset = 0,
                codecId = "scaffold-preview",
            ),
        )
    }

    override fun sourceChecksum(): String = "scaffold-preview"
}
