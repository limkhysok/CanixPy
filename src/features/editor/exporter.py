from PySide6.QtWidgets import QGraphicsScene
from PySide6.QtGui import QPixmap, QPainter
from PySide6.QtCore import Qt, QRectF


def export_scene_to_png(scene: QGraphicsScene, file_path: str, width: int = 800, height: int = 600) -> None:
    # Hide selection boundaries temporarily so handles aren't baked into the image
    scene.clearSelection()

    # Setup an offline pixel image buffer matching the page size
    image = QPixmap(width, height)
    image.fill(Qt.GlobalColor.white)

    # Paint the vector canvas onto the image buffer
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

    # Render the specific bounding region, skipping outer margins
    scene.render(painter, QRectF(0, 0, width, height), QRectF(0, 0, width, height))
    painter.end()

    image.save(file_path, "PNG")
