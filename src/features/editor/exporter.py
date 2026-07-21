from PySide6.QtWidgets import QGraphicsScene
from PySide6.QtGui import QBrush, QImage, QPageSize, QPainter, QPdfWriter, QPixmap
from PySide6.QtCore import QMarginsF, QRectF, QSizeF, Qt

# PDF points are defined as 1/72 inch; pinning the writer's resolution to 72
# DPI makes "1 point" and "1 device pixel" the same number, so the page can
# be sized directly in the canvas's own width/height without a conversion.
_PDF_POINTS_PER_INCH = 72


def _hide_page_background(scene: QGraphicsScene) -> tuple[bool, QBrush]:
    """Temporarily strip the white page fill/shadow and the gray canvas
    surround so a render captures only the actual content, for transparent
    exports. Returns what to restore afterward."""
    page_frame = getattr(scene, "page_frame", None)
    was_visible = page_frame.isVisible() if page_frame is not None else True
    previous_brush = scene.backgroundBrush()
    if page_frame is not None:
        page_frame.setVisible(False)
    scene.setBackgroundBrush(QBrush(Qt.GlobalColor.transparent))
    return was_visible, previous_brush


def _restore_page_background(scene: QGraphicsScene, was_visible: bool, previous_brush: QBrush) -> None:
    page_frame = getattr(scene, "page_frame", None)
    if page_frame is not None:
        page_frame.setVisible(was_visible)
    scene.setBackgroundBrush(previous_brush)


def export_scene_to_png(
    scene: QGraphicsScene, file_path: str, width: int = 800, height: int = 600, transparent: bool = False
) -> None:
    # Hide selection boundaries temporarily so handles aren't baked into the image
    scene.clearSelection()

    restore_state = _hide_page_background(scene) if transparent else None
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
        scene.render(painter, QRectF(0, 0, width, height), QRectF(0, 0, width, height))
        painter.end()
    finally:
        if restore_state is not None:
            _restore_page_background(scene, *restore_state)

    image.save(file_path, "PNG")


def export_scene_to_jpg(scene: QGraphicsScene, file_path: str, width: int = 800, height: int = 600) -> None:
    scene.clearSelection()

    # JPEG has no alpha channel, so this always renders on an opaque white page.
    image = QPixmap(width, height)
    image.fill(Qt.GlobalColor.white)

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    scene.render(painter, QRectF(0, 0, width, height), QRectF(0, 0, width, height))
    painter.end()

    image.save(file_path, "JPG", quality=92)


def export_scene_to_pdf(scene: QGraphicsScene, file_path: str, width: int = 800, height: int = 600) -> None:
    scene.clearSelection()

    writer = QPdfWriter(file_path)
    writer.setResolution(_PDF_POINTS_PER_INCH)
    writer.setPageSize(QPageSize(QSizeF(width, height), QPageSize.Unit.Point))
    writer.setPageMargins(QMarginsF(0, 0, 0, 0))

    painter = QPainter(writer)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    scene.render(painter, QRectF(0, 0, width, height), QRectF(0, 0, width, height))
    painter.end()
