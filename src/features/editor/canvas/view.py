from __future__ import annotations
from typing import TYPE_CHECKING, cast
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QWidget
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QWheelEvent, QKeyEvent, QDragEnterEvent, QDragMoveEvent, QDropEvent
from src.features.editor.canvas.scene import DesignScene

if TYPE_CHECKING:
    from src.features.editor.editor_view import CoreDesignApp

class ZoomableGraphicsView(QGraphicsView):
    def __init__(self, scene: QGraphicsScene, main_app: "CoreDesignApp", parent: QWidget | None = None) -> None:
        super().__init__(scene, parent)
        self.main_app = main_app
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setAcceptDrops(True)

    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            zoom_factor = 1.25 if event.angleDelta().y() > 0 else 0.8
            self.scale(zoom_factor, zoom_factor)
        else:
            super().wheelEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            selected_items = self.scene().selectedItems()
            for item in selected_items:
                if item != getattr(self.scene(), 'page_frame', None):
                    self.scene().removeItem(item)
            self.main_app.update_properties_panel()
        else:
            super().keyPressEvent(event)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        shape_type = event.mimeData().text()
        drop_pos = self.mapToScene(event.position().toPoint())
        cast(DesignScene, self.scene()).add_dropped_item(shape_type, drop_pos)
        event.acceptProposedAction()