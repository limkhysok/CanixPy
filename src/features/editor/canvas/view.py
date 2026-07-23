from __future__ import annotations
import math
from pathlib import Path
from typing import TYPE_CHECKING, Callable, cast
from PySide6.QtWidgets import QFrame, QGraphicsItem, QGraphicsView, QGraphicsScene, QMenu, QMessageBox, QWidget
from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt
from PySide6.QtGui import (
    QAction,
    QBrush,
    QColor,
    QContextMenuEvent,
    QGuiApplication,
    QKeySequence,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QPixmap,
    QResizeEvent,
    QWheelEvent,
    QKeyEvent,
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
)
from src.core import icons, theme
from src.features.editor.canvas.items import ResizablePixmapItem, get_image_source, is_layer_locked, set_layer_locked
from src.features.editor.canvas.page import Page
from src.features.editor.canvas.scene import DesignScene

if TYPE_CHECKING:
    from src.features.editor.viewmodels.editor_viewmodel import EditorViewModel
    from src.features.editor.views.layout.page_overlay import PageOverlayManager

NUDGE_STEP = 1
NUDGE_STEP_LARGE = 10
ZOOM_STEP_IN = 1.25
ZOOM_STEP_OUT = 0.8
_NUDGE_KEYS: dict[int, tuple[int, int]] = {
    Qt.Key.Key_Left: (-1, 0),
    Qt.Key.Key_Right: (1, 0),
    Qt.Key.Key_Up: (0, -1),
    Qt.Key.Key_Down: (0, 1),
}

# Repeated Alt+clicks within this many viewport pixels of each other are
# treated as "the same spot" and advance the select-below cycle; anything
# further away starts a fresh cycle at the topmost item.
_ALT_CYCLE_TOLERANCE = 4

# Scene-unit padding around a page when fitting it to the viewport, so the
# page's own edge/border isn't flush against the viewport frame.
FIT_MARGIN = 40

# Grid overlay (see set_grid_visible): spacing is in scene units, not screen
# pixels, so it zooms with the content like Figma/Canva's -- but that means
# zooming far out would otherwise cram a huge number of screen-adjacent
# lines together, so the spacing widens by GRID_SPACING_STEP whenever it'd
# render closer together on screen than GRID_MIN_SCREEN_PX.
GRID_BASE_SPACING = 20.0
GRID_MIN_SCREEN_PX = 8.0
GRID_SPACING_STEP = 5

class ZoomableGraphicsView(QGraphicsView):
    def __init__(
        self,
        scene: QGraphicsScene,
        viewmodel: "EditorViewModel",
        on_refresh: Callable[[], None],
        on_properties_change: Callable[[], None],
        on_selection_sync: Callable[[], None],
        on_page_properties_shown: Callable[[Page], None],
        on_page_properties_cleared: Callable[[], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(scene, parent)
        self.viewmodel = viewmodel
        self._on_refresh = on_refresh
        self._on_properties_change = on_properties_change
        self._on_selection_sync = on_selection_sync
        self._on_page_properties_shown = on_page_properties_shown
        self._on_page_properties_cleared = on_page_properties_cleared
        self._drag_start_positions: dict[QGraphicsItem, QPointF] = {}
        self._alt_cycle_pos: QPointF | None = None
        self._alt_cycle_index: int = 0
        self._pressed_on_page: Page | None = None
        # Alt+drag-duplicate (see mousePressEvent/mouseMoveEvent): armed on
        # press when Alt+click lands on an already-selected item, then
        # actually triggered once the drag exceeds a small movement
        # threshold -- a plain Alt+click there still behaves like an
        # ordinary click/drag-start instead of always duplicating.
        self._alt_duplicate_armed = False
        self._alt_duplicate_start: QPointF | None = None
        self._grid_visible = False
        # Set by EditorView -- positions/rebuilds the per-page floating
        # labels every repaint. Not owned/constructed here so this view stays
        # decoupled from what the overlay UI actually is.
        self.page_overlay_manager: "PageOverlayManager | None" = None
        # The viewport has no real size yet at construction time (layout
        # hasn't run), so the initial fit-to-page has to wait for the first
        # resize that actually gives it one.
        self._pending_fit_page: Page | None = None
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

    def fit_to_page(self, page: Page) -> None:
        """Scale/center the view so the whole page is visible -- called on
        first show, so opening a task with a canvas bigger than the viewport
        (e.g. a 1080x1920 Story) doesn't start zoomed in past the page edges,
        forcing a manual Ctrl+scroll out."""
        # page.rect(), not page.frame.sceneBoundingRect() -- the frame's
        # boundingRect() is padded out for resize/rotate-handle hit testing
        # (see _HandleMixin), which would zoom out far past the actual page.
        rect = page.rect().adjusted(-FIT_MARGIN, -FIT_MARGIN, FIT_MARGIN, FIT_MARGIN)
        self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)

    def scroll_to_page(self, page: Page) -> None:
        """Centers the view on `page` without changing zoom -- used to jump
        to a page (e.g. right after adding/duplicating one) in a document
        where every page is already reachable by scrolling."""
        self.centerOn(page.rect().center())

    def request_fit_to_page(self, page: Page) -> None:
        """Fit now if the viewport already has real geometry, otherwise defer
        to the first resizeEvent that gives it one (see `_pending_fit_page`)."""
        if self.viewport().width() > 0 and self.viewport().height() > 0:
            self.fit_to_page(page)
            self._pending_fit_page = None
        else:
            self._pending_fit_page = page

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self._pending_fit_page is not None and self.viewport().width() > 0 and self.viewport().height() > 0:
            self.fit_to_page(self._pending_fit_page)
            self._pending_fit_page = None

    def set_grid_visible(self, visible: bool) -> None:
        self._grid_visible = visible
        self.viewport().update()

    def drawBackground(self, painter: QPainter, rect: QRectF | QRect) -> None:  # noqa: N802
        super().drawBackground(painter, rect)
        if not self._grid_visible:
            return
        rect = QRectF(rect)
        # Uniform scale assumed -- the view is never sheared/rotated, only
        # panned and zoomed (see _zoom), so m11() alone is the current
        # scene-to-screen scale factor.
        scale = self.transform().m11()
        spacing = GRID_BASE_SPACING
        while spacing * scale < GRID_MIN_SCREEN_PX:
            spacing *= GRID_SPACING_STEP

        pen = QPen(QColor(theme.BORDER))
        pen.setWidth(0)
        painter.setPen(pen)

        left = math.floor(rect.left() / spacing) * spacing
        top = math.floor(rect.top() / spacing) * spacing
        x = left
        while x < rect.right():
            painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
            x += spacing
        y = top
        while y < rect.bottom():
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
            y += spacing

    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self._zoom(ZOOM_STEP_IN if event.angleDelta().y() > 0 else ZOOM_STEP_OUT)
        else:
            super().wheelEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        super().paintEvent(event)
        # Resyncing after every repaint (rather than hooking every individual
        # cause -- zoom, pan, resize, page add/delete/move/resize, ...) keeps
        # the overlay labels and active-page tracking correct regardless of
        # what moved, since all of those already force a repaint anyway.
        if self.page_overlay_manager is not None:
            self.page_overlay_manager.sync(self)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        # Computed unconditionally, before the Alt-click branch (which
        # returns early) -- otherwise Alt+click on empty page space would
        # leave this stale from whatever the previous plain click hit.
        scene = cast(DesignScene, self.scene())
        # QGraphicsView.itemAt() is typed as always returning a
        # QGraphicsItem, but at runtime it's None when the click misses
        # every item (e.g. empty canvas) -- same PySide6 stub inaccuracy as
        # QGraphicsItem.scene() (see _typed_scene() in items.py).
        hit = cast("QGraphicsItem | None", self.itemAt(event.pos()))
        self._pressed_on_page = next((p for p in scene.pages if p.frame is hit), None)

        alt_held = bool(event.modifiers() & Qt.KeyboardModifier.AltModifier)
        if event.button() == Qt.MouseButton.LeftButton and alt_held:
            frames = scene.page_frames()
            if hit is not None and hit not in frames and hit.isSelected() and not is_layer_locked(hit):
                # Alt-dragging an already-selected item duplicates it rather
                # than cycling the selection below it (see
                # _alt_click_select) -- arm the duplicate and fall through to
                # ordinary press handling so Qt's own drag starts normally;
                # the duplicate itself only appears once that drag actually
                # moves (see mouseMoveEvent).
                self._alt_duplicate_armed = True
                self._alt_duplicate_start = event.position()
                self._alt_cycle_pos = None
                super().mousePressEvent(event)
                self._snapshot_drag_start_positions()
                return
            self._alt_click_select(event)
            return

        # Any plain click abandons whatever Alt-cycle was in progress, so a
        # later Alt+click at that same spot starts over at the topmost item
        # instead of resuming a stale cycle.
        self._alt_cycle_pos = None
        self._alt_duplicate_armed = False

        super().mousePressEvent(event)
        self._snapshot_drag_start_positions()

    def _snapshot_drag_start_positions(self) -> None:
        # Snapshot positions *after* the click has updated selection, so a
        # drag starting here can be diffed against these on release. Items
        # mid-handle-resize/-rotate are excluded: those push their own
        # undo entry (see _HandleMixin), and some resizes (e.g. an image's,
        # to keep the dragged-from corner fixed) legitimately move the item
        # too -- without this exclusion that also looked like a plain drag
        # here, pushing a second, conflicting move-undo on top of the
        # resize's own and corrupting the undo stack.
        self._drag_start_positions = {
            item: item.pos()
            for item in self.scene().selectedItems()
            if not (getattr(item, "_active_handle", None) or getattr(item, "_rotating", False))
        }

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._alt_duplicate_armed and self._alt_duplicate_start is not None:
            moved = (event.position() - self._alt_duplicate_start).manhattanLength()
            if moved > _ALT_CYCLE_TOLERANCE:
                self._alt_duplicate_armed = False
                self._perform_alt_duplicate()
        super().mouseMoveEvent(event)

    def _perform_alt_duplicate(self) -> None:
        """Leaves an exact copy of the current selection behind at its
        pre-drag position, then lets the drag already in progress (see
        mousePressEvent) carry on moving the *original* items -- reuses
        Qt's own in-progress drag instead of re-implementing item dragging,
        and is functionally identical to the usual Alt+drag-duplicate
        convention either way (one copy ends up moved, one stays put)."""
        scene = cast(DesignScene, self.scene())
        items = [i for i in scene.selectedItems() if not is_layer_locked(i)]
        if items:
            self.viewmodel.duplicate_items_in_place(items)

    def _alt_click_select(self, event: QMouseEvent) -> None:
        """Alt+click cycles through whatever is stacked at this point, one
        item further down the z-order each repeated click -- the Figma/Canva
        way to reach something buried under other items without detouring
        through the Layers panel."""
        scene = cast(DesignScene, self.scene())
        frames = scene.page_frames()
        scene_pos = self.mapToScene(event.position().toPoint())
        stack = [
            item for item in scene.items(scene_pos)
            if item not in frames and not is_layer_locked(item)
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

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        scene = cast(DesignScene, self.scene())
        frames = scene.page_frames()
        scene_pos = self.mapToScene(event.pos())
        images = [
            item for item in scene.items(scene_pos)
            if item not in frames and isinstance(item, ResizablePixmapItem)
        ]
        if not images:
            super().contextMenuEvent(event)
            return
        images.sort(key=lambda item: item.zValue(), reverse=True)
        image = images[0]

        # setSelected() is a no-op on a locked (unselectable) item, so the
        # menu actions below target `image` directly rather than "whatever's
        # selected" -- Duplicate/Delete/Info all work the same regardless.
        if not is_layer_locked(image):
            scene.clearSelection()
            image.setSelected(True)
            self._on_selection_sync()

        self._show_image_context_menu(image, event.globalPos())

    def _show_image_context_menu(self, image: ResizablePixmapItem, global_pos: QPoint) -> None:
        scene = cast(DesignScene, self.scene())
        menu = QMenu(self)

        duplicate_action = QAction(icons.icon("fa5s.clone", color=theme.TEXT_PRIMARY), "Duplicate", menu)
        duplicate_action.triggered.connect(lambda: self.viewmodel.duplicate_items([image]))
        menu.addAction(duplicate_action)

        locked = is_layer_locked(image)
        lock_action = QAction(
            icons.icon("fa5s.unlock" if locked else "fa5s.lock", color=theme.TEXT_PRIMARY),
            "Unlock" if locked else "Lock",
            menu,
        )
        lock_action.triggered.connect(lambda: self._toggle_image_lock(image))
        menu.addAction(lock_action)

        menu.addSeparator()

        delete_action = QAction(icons.icon("fa5s.trash-alt", color=theme.TEXT_PRIMARY), "Delete", menu)
        delete_action.triggered.connect(lambda: scene.delete_items([image]))
        menu.addAction(delete_action)

        menu.addSeparator()

        info_action = QAction(icons.icon("fa5s.info-circle", color=theme.TEXT_PRIMARY), "Info", menu)
        info_action.triggered.connect(lambda: self._show_image_info(image))
        menu.addAction(info_action)

        menu.exec(global_pos)

    def _toggle_image_lock(self, image: ResizablePixmapItem) -> None:
        set_layer_locked(image, not is_layer_locked(image))
        self._on_refresh()

    def _show_image_info(self, image: ResizablePixmapItem) -> None:
        native = image.pixmap().size()
        scale = image.scale()
        displayed_w = round(native.width() * scale)
        displayed_h = round(native.height() * scale)
        lines = [
            f"Original size: {native.width()} x {native.height()} px",
            f"Displayed size: {displayed_w} x {displayed_h} px ({scale * 100:.0f}%)",
        ]
        source = get_image_source(image)
        title = Path(source).name if source else "Image"
        if source:
            lines.append(f"Source: {source}")
        QMessageBox.information(self, title, "\n".join(lines))

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
            self._on_properties_change()

        scene = cast(DesignScene, self.scene())
        if not scene.selectedItems():
            if self._pressed_on_page is not None:
                self._on_page_properties_shown(self._pressed_on_page)
            else:
                self._on_page_properties_cleared()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        # Split into one method per shortcut cluster (each returns True if it
        # consumed the event) rather than one long if/elif chain -- purely a
        # readability/complexity split, every condition and action below is
        # unchanged from before.
        scene = cast(DesignScene, self.scene())
        handled = (
            self._handle_pan_key(event)
            or self._handle_clipboard_keys(event, scene)
            or self._handle_duplicate_group_keys(event, scene)
            or self._handle_nudge_keys(event)
            or self._handle_z_order_keys(event, scene)
            or self._handle_zoom_keys(event)
        )
        if not handled:
            super().keyPressEvent(event)

    def _handle_pan_key(self, event: QKeyEvent) -> bool:
        # Held Space temporarily swaps rubber-band selection for Qt's built-in
        # hand-drag panning (the Figma/Canva convention) -- isAutoRepeat()
        # guards against the OS repeating this event every few ms while the
        # key stays down, which would otherwise spam redundant mode-sets.
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            return True
        return False

    def _handle_clipboard_keys(self, event: QKeyEvent, scene: DesignScene) -> bool:
        if event.key() == Qt.Key.Key_Escape:
            scene.clearSelection()
        elif event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            scene.delete_items(scene.selectedItems())
        elif event.matches(QKeySequence.StandardKey.Cut):
            self.viewmodel.copy_selection()
            scene.delete_items(scene.selectedItems())
        elif event.matches(QKeySequence.StandardKey.Copy):
            self.viewmodel.copy_selection()
        elif event.matches(QKeySequence.StandardKey.Paste):
            self._paste(scene)
        elif event.matches(QKeySequence.StandardKey.SelectAll):
            for item in scene.items():
                if item.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsSelectable:
                    item.setSelected(True)
        else:
            return False
        return True

    def _handle_duplicate_group_keys(self, event: QKeyEvent, scene: DesignScene) -> bool:
        ctrl_held = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        if event.key() == Qt.Key.Key_D and ctrl_held:
            self.viewmodel.duplicate_selection()
        elif event.key() == Qt.Key.Key_G and ctrl_held and event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            scene.ungroup_items(scene.selectedItems())
        elif event.key() == Qt.Key.Key_G and ctrl_held:
            scene.group_items(scene.selectedItems())
        else:
            return False
        return True

    def _handle_nudge_keys(self, event: QKeyEvent) -> bool:
        if event.key() not in _NUDGE_KEYS:
            return False
        self._nudge_selection(event.key(), event.modifiers())
        return True

    def _handle_z_order_keys(self, event: QKeyEvent, scene: DesignScene) -> bool:
        ctrl_held = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        if event.key() == Qt.Key.Key_BracketRight and ctrl_held:
            scene.step_forward(scene.selectedItems())
        elif event.key() == Qt.Key.Key_BracketLeft and ctrl_held:
            scene.step_backward(scene.selectedItems())
        else:
            return False
        return True

    def _handle_zoom_keys(self, event: QKeyEvent) -> bool:
        if event.matches(QKeySequence.StandardKey.ZoomIn):
            self._zoom(ZOOM_STEP_IN)
        elif event.matches(QKeySequence.StandardKey.ZoomOut):
            self._zoom(ZOOM_STEP_OUT)
        elif event.key() == Qt.Key.Key_0 and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.fit_to_page(self.viewmodel.active_page)
        elif event.key() == Qt.Key.Key_1 and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self._reset_zoom()
        else:
            return False
        return True

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        else:
            super().keyReleaseEvent(event)

    def _paste(self, scene: DesignScene) -> None:
        """An image sitting on the OS clipboard (a copied screenshot, a
        browser image, ...) takes priority over the in-app clipboard --
        copy/cut inside the canvas never touches the OS clipboard (see
        EditorViewModel._clipboard), so finding an image there is a strong
        signal the user just copied it from outside the app and wants it on
        the canvas, not whatever was last cut/copied on this canvas."""
        clipboard_image = QGuiApplication.clipboard().image()
        if not clipboard_image.isNull():
            pos = self.mapToScene(self.viewport().rect().center())
            scene.add_image_from_clipboard(QPixmap.fromImage(clipboard_image), pos)
        else:
            self.viewmodel.paste_clipboard()

    def _zoom(self, factor: float) -> None:
        self.scale(factor, factor)

    def _reset_zoom(self) -> None:
        """Zoom to exactly 100% while keeping whatever's currently centered
        in view -- resetTransform() alone would also snap the pan back to the
        scene origin, jumping the view away from the page being edited."""
        center = self.mapToScene(self.viewport().rect().center())
        self.resetTransform()
        self.centerOn(center)

    def _nudge_selection(self, key: int, modifiers: Qt.KeyboardModifier) -> None:
        scene = cast(DesignScene, self.scene())
        frames = scene.page_frames()
        items = [i for i in scene.selectedItems() if i not in frames]
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
