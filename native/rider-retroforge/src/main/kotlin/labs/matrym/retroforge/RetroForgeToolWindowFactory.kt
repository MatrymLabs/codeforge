package labs.matrym.retroforge

import com.intellij.openapi.project.Project
import com.intellij.openapi.wm.ToolWindow
import com.intellij.openapi.wm.ToolWindowFactory
import com.intellij.ui.components.JBScrollPane
import com.intellij.ui.components.JBTextArea
import com.intellij.ui.content.ContentFactory
import java.awt.Font

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
                font = Font(Font.MONOSPACED, Font.PLAIN, 14)
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
                indices = List(8) { row -> List(8) { column -> (row + column) % 4 } },
                sourceOffset = 0,
                codecId = "scaffold-preview",
            ),
        )
    }

    override fun sourceChecksum(): String = "scaffold-preview"
}
