from __future__ import annotations
from typing import TYPE_CHECKING, cast
from PySide6.QtWidgets import QFrame, QGraphicsItem, QGraphicsView, QGraphicsScene, QWidget
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QKeySequence, QMouseEvent, QPainter, QResizeEvent, QWheelEvent, QKeyEvent, QDragEnterEvent, QDragMoveEvent, QDropEvent
from src.core import theme
from src.features.editor.canvas.items import is_layer_locked
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

# Repeated Alt+clicks within this many viewport pixels of each other are
# treated as "the same spot" and advance the select-below cycle; anything
# further away starts a fresh cycle at the topmost item.
_ALT_CYCLE_TOLERANCE = 4

# Scene-unit padding around the page when fitting it to the viewport, so the
# page's own edge/border isn't flush against the viewport frame.
FIT_MARGIN = 40

class ZoomableGraphicsView(QGraphicsView):
    def __init__(self, scene: QGraphicsScene, main_app: "CoreDesignApp", parent: QWidget | None = None) -> None:
        super().__init__(scene, parent)
        self.main_app = main_app
        self._drag_start_positions: dict[QGraphicsItem, QPointF] = {}
        self._alt_cycle_pos: QPointF | None = None
        self._alt_cycle_index: int = 0
        # The viewport has no real size yet at construction time (layout
        # hasn't run), so the initial fit-to-page has to wait for the first
        # resize that actually gives it one.
        self._pending_fit = True
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

    def fit_to_page(self) -> None:
        """Scale/center the view so the whole page is visible -- called on
        first show and on every page switch, so opening a task with a canvas
        bigger than the viewport (e.g. a 1080x1920 Story) doesn't start
        zoomed in past the page edges, forcing a manual Ctrl+scroll out."""
        page_frame = getattr(self.scene(), "page_frame", None)
        if page_frame is None:
            return
        rect = page_frame.sceneBoundingRect().adjusted(-FIT_MARGIN, -FIT_MARGIN, FIT_MARGIN, FIT_MARGIN)
        self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)

    def request_fit_to_page(self) -> None:
        """Fit now if the viewport already has real geometry, otherwise defer
        to the first resizeEvent that gives it one (see `_pending_fit`)."""
        if self.viewport().width() > 0 and self.viewport().height() > 0:
            self.fit_to_page()
            self._pending_fit = False
        else:
            self._pending_fit = True

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self._pending_fit and self.viewport().width() > 0 and self.viewport().height() > 0:
            self.fit_to_page()
            self._pending_fit = False

    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            zoom_factor = 1.25 if event.angleDelta().y() > 0 else 0.8
            self.scale(zoom_factor, zoom_factor)
        else:
            super().wheelEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and event.modifiers() & Qt.KeyboardModifier.AltModifier:
            self._alt_click_select(event)
            return

        # Any plain click abandons whatever Alt-cycle was in progress, so a
        # later Alt+click at that same spot starts over at the topmost item
        # instead of resuming a stale cycle.
        self._alt_cycle_pos = None

        super().mousePressEvent(event)
        # Snapshot positions *after* the click has updated selection, so a
        # drag starting here can be diffed against these on release.
        self._drag_start_positions = {item: item.pos() for item in self.scene().selectedItems()}

    def _alt_click_select(self, event: QMouseEvent) -> None:
        """Alt+click cycles through whatever is stacked at this point, one
        item further down the z-order each repeated click -- the Figma/Canva
        way to reach something buried under other items without detouring
        through the Layers panel."""
        scene = cast(DesignScene, self.scene())
        page_frame = getattr(scene, "page_frame", None)
        scene_pos = self.mapToScene(event.position().toPoint())
        stack = [
            item for item in scene.items(scene_pos)
            if item is not page_frame and not is_layer_locked(item)
        ]
        stack.sort(key=lambda item: item.zValue(), reverse=True)

        view_pos = event.position()
        same_spot = (
            self._alt_cycle_pos is not None
            and (view_pos - self._alt_cycle_pos).manhattanLength() <= _ALT_CYCLE_TOLERANCE
        )
        self._alt_cycle_index = self._alt_cycle_index + 1 if same_spot else 0
        self._alt_cycle_pos = view_pos

        scene.clearSelection()
        if stack:
            stack[self._alt_cycle_index % len(stack)].setSelected(True)
        self._drag_start_positions = {item: item.pos() for item in scene.selectedItems()}

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