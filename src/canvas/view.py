from PyQt6.QtWidgets import QGraphicsView
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter

class ZoomableGraphicsView(QGraphicsView):
    def __init__(self, scene, main_app, parent=None):
        super().__init__(scene, parent)
        self.main_app = main_app
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setAcceptDrops(True)

    def wheelEvent(self, event):
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            zoom_factor = 1.25 if event.angleDelta().y() > 0 else 0.8
            self.scale(zoom_factor, zoom_factor)
        else:
            super().wheelEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            selected_items = self.scene().selectedItems()
            for item in selected_items:
                if item != getattr(self.scene(), 'page_frame', None):
                    self.scene().removeItem(item)
            self.main_app.update_properties_panel()
        else:
            super().keyPressEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        event.acceptProposedAction()

    def dropEvent(self, event):
        shape_type = event.mimeData().text()
        drop_pos = self.mapToScene(event.position().toPoint())
        self.scene().add_dropped_item(shape_type, drop_pos)
        event.acceptProposedAction()