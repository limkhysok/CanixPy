from __future__ import annotations
from typing import TYPE_CHECKING, cast
from PySide6.QtWidgets import QFrame, QGraphicsItem, QGraphicsView, QGraphicsScene, QWidget
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QKeySequence, QMouseEvent, QPainter, QWheelEvent, QKeyEvent, QDragEnterEvent, QDragMoveEvent, QDropEvent
from src.core import theme
from src.features.editor.canvas.scene import DesignScene

if TYPE_CHECKING:
    from src.features.editor.editor_view import CoreDesignApp

NUDGE_STEP = 1
NUDGE_STEP_LARGE = 10
_NUDGE_KEYS = {
    Qt.Key.Key_Left: (-1, 0),
    Qt.Key.Key_Right: (1, 0),
    Qt.Key.Key_Up: (0, -1),
    Qt.Key.Key_Down: (0, 1),
}

class ZoomableGraphicsView(QGraphicsView):
    def __init__(self, scene: QGraphicsScene, main_app: "CoreDesignApp", parent: QWidget | None = None) -> None:
        super().__init__(scene, parent)
        self.main_app = main_app
        self._drag_start_positions: dict[QGraphicsItem, QPointF] = {}
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setAcceptDrops(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.Shape.NoFrame)
        # Paints the whole viewport (not just the scene rect) so the gray
        # surround still shows when the window is larger than the page.
        self.setBackgroundBrush(QBrush(QColor(theme.CANVAS_SURROUND)))

    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            zoom_factor = 1.25 if event.angleDelta().y() > 0 else 0.8
            self.scale(zoom_factor, zoom_factor)
        else:
            super().wheelEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        super().mousePressEvent(event)
        # Snapshot positions *after* the click has updated selection, so a
        # drag starting here can be diffed against these on release.
        self._drag_start_positions = {item: item.pos() for item in self.scene().selectedItems()}

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        super().mouseReleaseEvent(event)
        moved = {
            item: (old_pos, item.pos())
            for item, old_pos in self._drag_start_positions.items()
            if item.pos() != old_pos
        }
        self._drag_start_positions = {}
        if moved:
            cast(DesignScene, self.scene()).push_move_undo(moved)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        scene = cast(DesignScene, self.scene())
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            scene.delete_items(scene.selectedItems())
        elif event.matches(QKeySequence.StandardKey.Copy):
            self.main_app.copy_selection()
        elif event.matches(QKeySequence.StandardKey.Paste):
            self.main_app.paste_clipboard()
        elif event.key() == Qt.Key.Key_D and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.main_app.duplicate_selection()
        elif event.key() == Qt.Key.Key_G and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                scene.ungroup_items(scene.selectedItems())
            else:
                scene.group_items(scene.selectedItems())
        elif event.key() in _NUDGE_KEYS:
            self._nudge_selection(event.key(), event.modifiers())
        else:
            super().keyPressEvent(event)

    def _nudge_selection(self, key: Qt.Key, modifiers: Qt.KeyboardModifier) -> None:
        scene = cast(DesignScene, self.scene())
        items = [i for i in scene.selectedItems() if i != getattr(scene, "page_frame", None)]
        if not items:
            return
        step = NUDGE_STEP_LARGE if modifiers & Qt.KeyboardModifier.ShiftModifier else NUDGE_STEP
        dx, dy = _NUDGE_KEYS[key]
        old_positions = {item: item.pos() for item in items}
        for item in items:
            item.setPos(item.pos().x() + dx * step, item.pos().y() + dy * step)
        moved = {item: (old_positions[item], item.pos()) for item in items}
        scene.push_move_undo(moved)

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