from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QGraphicsScene
from PySide6.QtGui import QBrush, QImage, QPageSize, QPainter, QPdfWriter, QPixmap
from PySide6.QtCore import QMarginsF, QRectF, QSize, QSizeF, Qt
from PySide6.QtSvg import QSvgGenerator

if TYPE_CHECKING:
    from src.features.editor.canvas.page import Page

# PDF points are defined as 1/72 inch; pinning the writer's resolution to 72
# DPI makes "1 point" and "1 device pixel" the same number, so the page can
# be sized directly in the canvas's own width/height without a conversion.
_PDF_POINTS_PER_INCH = 72


def _page_source_rect(page: "Page") -> QRectF:
    """The exported page's region within the shared multi-page scene --
    pages are freely positioned, not all anchored at the scene origin, so
    this can't just be QRectF(0, 0, width, height)."""
    return QRectF(page.x_offset, page.y_offset, page.width, page.height)


def _hide_page_background(scene: QGraphicsScene, page: "Page") -> tuple[bool, QBrush]:
    """Temporarily strip this page's white fill/shadow and the gray canvas
    surround so a render captures only the actual content, for transparent
    exports. Only this page's frame needs hiding -- it's the only one inside
    the render's source rect. Returns what to restore afterward."""
    was_visible = page.frame.isVisible()
    previous_brush = scene.backgroundBrush()
    page.frame.setVisible(False)
    scene.setBackgroundBrush(QBrush(Qt.GlobalColor.transparent))
    return was_visible, previous_brush


def _restore_page_background(scene: QGraphicsScene, page: "Page", was_visible: bool, previous_brush: QBrush) -> None:
    page.frame.setVisible(was_visible)
    scene.setBackgroundBrush(previous_brush)


def export_scene_to_png(
    scene: QGraphicsScene, file_path: str, page: "Page", transparent: bool = False
) -> None:
    width, height = int(page.width), int(page.height)
    # Hide selection boundaries temporarily so handles aren't baked into the image
    scene.clearSelection()

    restore_state = _hide_page_background(scene, page) if transparent else None
    try:
        if transparent:
            image = QImage(width, height, QImage.Format.Format_ARGB32)
            image.fill(Qt.GlobalColor.transparent)
        else:
            image = QPixmap(width, height)
            image.fill(Qt.GlobalColor.white)

        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        scene.render(painter, QRectF(0, 0, width, height), _page_source_rect(page))
        painter.end()
    finally:
        if restore_state is not None:
            _restore_page_background(scene, page, *restore_state)

    image.save(file_path, "PNG")


def export_scene_to_jpg(scene: QGraphicsScene, file_path: str, page: "Page") -> None:
    width, height = int(page.width), int(page.height)
    scene.clearSelection()

    # JPEG has no alpha channel, so this always renders on an opaque white page.
    image = QPixmap(width, height)
    image.fill(Qt.GlobalColor.white)

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    scene.render(painter, QRectF(0, 0, width, height), _page_source_rect(page))
    painter.end()

    image.save(file_path, "JPG", quality=92)


def export_scene_to_svg(scene: QGraphicsScene, file_path: str, page: "Page") -> None:
    width, height = int(page.width), int(page.height)
    scene.clearSelection()

    generator = QSvgGenerator()
    generator.setFileName(file_path)
    generator.setSize(QSize(width, height))
    generator.setViewBox(QRectF(0, 0, width, height))
    generator.setTitle(Path(file_path).stem)

    painter = QPainter(generator)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    scene.render(painter, QRectF(0, 0, width, height), _page_source_rect(page))
    painter.end()


def export_scene_to_pdf(scene: QGraphicsScene, file_path: str, page: "Page") -> None:
    width, height = int(page.width), int(page.height)
    scene.clearSelection()

    writer = QPdfWriter(file_path)
    writer.setResolution(_PDF_POINTS_PER_INCH)
    writer.setPageSize(QPageSize(QSizeF(width, height), QPageSize.Unit.Point))
    writer.setPageMargins(QMarginsF(0, 0, 0, 0))

    painter = QPainter(writer)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    scene.render(painter, QRectF(0, 0, width, height), _page_source_rect(page))
    painter.end()


# Format key -> (file extension, export function) -- shared by export_all_pages
# so the "export every page" flow reuses the exact same per-page renderers as
# the single-page Export menu instead of a separate implementation. Defined
# after every export_scene_to_* function above so this dict can reference
# them directly.
_EXPORTERS = {
    "png": ("png", export_scene_to_png),
    "png_transparent": ("png", lambda scene, path, page: export_scene_to_png(scene, path, page, transparent=True)),
    "jpg": ("jpg", export_scene_to_jpg),
    "pdf": ("pdf", export_scene_to_pdf),
    "svg": ("svg", export_scene_to_svg),
}


def export_all_pages(
    scene: QGraphicsScene, pages: list["Page"], directory: str, fmt: str, base_name: str = "design_page"
) -> list[str]:
    """Exports every page to its own file in `directory`, named
    "{base_name}_{n}.{ext}" in page order. Returns the written paths."""
    extension, export_one = _EXPORTERS[fmt]
    paths: list[str] = []
    for index, page in enumerate(pages, start=1):
        file_path = str(Path(directory) / f"{base_name}_{index}.{extension}")
        export_one(scene, file_path, page)
        paths.append(file_path)
    return paths
