"""Custom graphics items: stock Qt shapes/text/image items, extended with
on-canvas resize handles (corners + edges) and a rotate handle when selected.

Each subclass just wires `_HandleMixin` on top of the matching stock
QGraphics*Item class, so every existing `isinstance(item, QGraphicsRectItem)`
check elsewhere in the codebase keeps working unchanged -- these are real
subclasses, not wrappers.
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING, Callable, cast

from PySide6.QtCore import QPointF, QRectF, QSizeF, Qt
from PySide6.QtGui import QColor, QCursor, QFocusEvent, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import (
    QGraphicsDropShadowEffect,
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsPixmapItem,
    QGraphicsPolygonItem,
    QGraphicsRectItem,
    QGraphicsSceneHoverEvent,
    QGraphicsSceneMouseEvent,
    QGraphicsTextItem,
    QStyle,
    QStyleOptionGraphicsItem,
    QWidget,
)

from src.core import theme
from src.features.editor.canvas.snapping import SNAP_THRESHOLD_PX, compute_snap

if TYPE_CHECKING:
    from src.features.editor.canvas.scene import DesignScene

# Handle/rotate sizes below are target *screen* pixels, not local/scene units --
# see _HandleMixin._device_scale(). A constant in local units would shrink to a
# couple of real screen pixels for anything zoomed out or scaled down (e.g. an
# imported photo, which lands at full native pixel size and forces the view to
# zoom way out), making handles nearly impossible to grab with the mouse.
HANDLE_VISUAL_PX = 8.0
HANDLE_HIT_PX = 18.0  # bigger than the visible square -- forgiving without looking bulky
ROTATE_OFFSET_PX = 24.0
ROTATE_HIT_PX = 18.0
MIN_SIZE = 12.0

# Fixed (not zoom-dependent) upper bound on how large the on-screen-constant
# sizes above are allowed to grow in local units when heavily zoomed out.
# boundingRect() needs a value Qt can index/cache without per-zoom
# invalidation, so it reserves this fixed worst-case margin; shape() (see
# below) is what actually governs precise click/hit behavior, so a generous
# bound here doesn't make empty canvas space near a small item clickable.
_MAX_LOCAL_HANDLE_HIT = 80.0
_MAX_LOCAL_ROTATE_REACH = 220.0

SHADOW_BLUR = 16
SHADOW_OFFSET = (0, 4)
SHADOW_COLOR = QColor(0, 0, 0, 110)


def make_shadow_effect() -> QGraphicsDropShadowEffect:
    """Shared shadow recipe so every item's drop-shadow toggle looks the same."""
    effect = QGraphicsDropShadowEffect()
    effect.setBlurRadius(SHADOW_BLUR)
    effect.setOffset(*SHADOW_OFFSET)
    effect.setColor(SHADOW_COLOR)
    return effect

# Corner handles resize both axes; edge handles resize one axis.
_ALL_HANDLES = ("tl", "tm", "tr", "ml", "mr", "bl", "bm", "br")
_CORNER_HANDLES = ("tl", "tr", "bl", "br")

_CURSOR_FOR_HANDLE = {
    "tl": Qt.CursorShape.SizeFDiagCursor, "br": Qt.CursorShape.SizeFDiagCursor,
    "tr": Qt.CursorShape.SizeBDiagCursor, "bl": Qt.CursorShape.SizeBDiagCursor,
    "tm": Qt.CursorShape.SizeVerCursor, "bm": Qt.CursorShape.SizeVerCursor,
    "ml": Qt.CursorShape.SizeHorCursor, "mr": Qt.CursorShape.SizeHorCursor,
    "rotate": Qt.CursorShape.CrossCursor,
}


def _resized_rect(start: QRectF, handle: str, delta: QPointF) -> QRectF:
    rect = QRectF(start)
    if "l" in handle:
        rect.setLeft(min(start.left() + delta.x(), start.right() - MIN_SIZE))
    if "r" in handle:
        rect.setRight(max(start.right() + delta.x(), start.left() + MIN_SIZE))
    if "t" in handle:
        rect.setTop(min(start.top() + delta.y(), start.bottom() - MIN_SIZE))
    if "b" in handle:
        rect.setBottom(max(start.bottom() + delta.y(), start.top() + MIN_SIZE))
    return rect.normalized()


# Real base is `object` (see the class docstring for why) -- this indirection
# just gives the type checker a QGraphicsItem to resolve `self.<method>` calls
# against, since TYPE_CHECKING is True for it but False at runtime.
if TYPE_CHECKING:
    _HandleMixinBase = QGraphicsItem
else:
    _HandleMixinBase = object


class _HandleMixin(_HandleMixinBase):
    """Adds resize + rotate handles to a QGraphicsItem when selected.

    Subclasses implement `local_rect()` (item-local geometry used to place
    handles) and `_apply_resize(rect)` (mutate the item to match that rect).
    Set `RESIZE_HANDLES = ()` to offer rotate-only interaction (used by text).

    `_HandleMixinBase` is QGraphicsItem only for the type checker (see its
    definition above) -- actually deriving from it at runtime makes shiboken
    build two separate QGraphicsItem C++ bases for e.g. `ResizableRectItem
    (_HandleMixin, QGraphicsRectItem)` and segfaults. At runtime this is
    exactly the plain, base-less mixin it always was.
    """

    RESIZE_HANDLES: tuple[str, ...] = _ALL_HANDLES

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        self.setAcceptHoverEvents(True)
        self._active_handle: str | None = None
        self._resize_start_rect: QRectF | None = None
        self._resize_start_pos: QPointF | None = None
        self._resize_start_scene_pos: QPointF | None = None
        self._resize_changed = False
        self._rotating = False
        self._rotate_start_angle = 0.0
        self._rotate_start_rotation = 0.0
        self._plain_dragging = False

    def _typed_scene(self) -> "DesignScene | None":
        # QGraphicsItem.scene() is typed as always returning a QGraphicsScene,
        # but at runtime it's None until the item is actually added to one --
        # this narrows to the app's real DesignScene subclass everywhere
        # resize/rotate/drag code below needs its DesignScene-only members
        # (undo_stack, snap_targets, ...).
        return cast("DesignScene | None", self.scene())

    # -- geometry (implemented per subclass) -----------------------------
    def local_rect(self) -> QRectF:
        raise NotImplementedError

    def _apply_resize(self, rect: QRectF) -> None:
        raise NotImplementedError

    def _resize_reference_rect(self) -> QRectF:
        """Rect a resize drag starts from/ends at, in whatever coordinate
        space _apply_resize()/_resize_delta() use for this subclass. Default:
        local_rect(), matching shape items -- setRect() mutates their local
        geometry, not their transform, so local coordinates stay stable for
        the whole drag and are also self-contained (safe to replay later for
        undo/redo without any other saved state)."""
        return QRectF(self.local_rect())

    def _resize_delta(self, event: QGraphicsSceneMouseEvent) -> QPointF:
        """Mouse movement since the drag started, in the same coordinate
        space as _resize_reference_rect(). Default: Qt's item-local mapping.
        Override together with _resize_reference_rect() for any subclass
        whose _apply_resize() changes the item's own transform (e.g.
        ResizablePixmapItem's setScale()) -- local coordinates would
        otherwise be measured against a transform that's drifting on every
        move, corrupting the delta mid-drag."""
        assert self._resize_start_pos is not None
        return event.pos() - self._resize_start_pos

    def _resize_target_rect(self, rect: QRectF) -> QRectF:
        """Post-process the raw handle-driven rect before it's applied.
        Default: identity. Override for any subclass whose resize has fewer
        true degrees of freedom than the raw two-axis drag rect implies --
        see ResizablePixmapItem, where passing the raw rect straight through
        let the anchor corner drift whenever the mouse drag didn't happen to
        exactly match the locked aspect ratio."""
        return rect

    def boundingRect(self) -> QRectF:  # noqa: N802 (Qt override)
        # Fixed worst-case margin -- see _MAX_LOCAL_HANDLE_HIT/_MAX_LOCAL_ROTATE_REACH.
        pad = _MAX_LOCAL_HANDLE_HIT + _MAX_LOCAL_ROTATE_REACH
        return self.local_rect().adjusted(-pad, -pad, pad, pad)

    def shape(self) -> QPainterPath:  # noqa: N802 (Qt override)
        # Qt's default shape() is just boundingRect() as a rectangle -- with a
        # fixed generous pad in boundingRect() that would make empty canvas
        # space near any item clickable. Return the real silhouette instead,
        # plus a precise hit-region around each handle when selected.
        path = QPainterPath()
        # Winding (not the QPainterPath default of odd-even), so overlapping
        # handle squares -- which do overlap each other and the base rect
        # once zoomed out enough -- union together instead of the overlap
        # cancelling out into a "hole" under odd-even parity.
        path.setFillRule(Qt.FillRule.WindingFill)
        path.addRect(self.local_rect())
        if self.isSelected():
            hit = self._handle_hit_size()
            for pos in self._handle_positions().values():
                path.addRect(QRectF(pos.x() - hit / 2, pos.y() - hit / 2, hit, hit))
            rp = self._rotate_handle_pos()
            rot_hit = self._rotate_hit_size()
            path.addEllipse(rp, rot_hit / 2, rot_hit / 2)
        return path

    # -- device-scale-independent sizing -----------------------------------
    def _device_scale(self) -> float:
        """Uniform local-to-screen scale factor (item transform x view zoom).
        Handle sizes are derived from this so they stay a constant, easily
        clickable size on screen no matter how zoomed out the view is or how
        small the item itself has been scaled -- see the HANDLE_*_PX comment
        above `_HandleMixin` for why that matters."""
        scene = self._typed_scene()
        if scene is None:
            return 1.0
        views = scene.views()
        if not views:
            return 1.0
        device_transform = self.deviceTransform(views[0].viewportTransform())
        p0 = device_transform.map(QPointF(0.0, 0.0))
        p1 = device_transform.map(QPointF(1.0, 0.0))
        length = math.hypot(p1.x() - p0.x(), p1.y() - p0.y())
        return length if length > 1e-6 else 1.0

    def _handle_visual_size(self) -> float:
        return min(HANDLE_VISUAL_PX / self._device_scale(), _MAX_LOCAL_HANDLE_HIT)

    def _handle_hit_size(self) -> float:
        return min(HANDLE_HIT_PX / self._device_scale(), _MAX_LOCAL_HANDLE_HIT)

    def _rotate_offset(self) -> float:
        return min(ROTATE_OFFSET_PX / self._device_scale(), _MAX_LOCAL_ROTATE_REACH)

    def _rotate_hit_size(self) -> float:
        return min(ROTATE_HIT_PX / self._device_scale(), _MAX_LOCAL_ROTATE_REACH)

    def _handle_positions(self) -> dict[str, QPointF]:
        r = self.local_rect()
        all_positions = {
            "tl": r.topLeft(), "tm": QPointF(r.center().x(), r.top()), "tr": r.topRight(),
            "ml": QPointF(r.left(), r.center().y()), "mr": QPointF(r.right(), r.center().y()),
            "bl": r.bottomLeft(), "bm": QPointF(r.center().x(), r.bottom()), "br": r.bottomRight(),
        }
        return {name: pos for name, pos in all_positions.items() if name in self.RESIZE_HANDLES}

    def _rotate_handle_pos(self) -> QPointF:
        r = self.local_rect()
        return QPointF(r.center().x(), r.top() - self._rotate_offset())

    def _handle_at(self, local_pos: QPointF) -> str | None:
        half = self._handle_hit_size() / 2
        for name, pos in self._handle_positions().items():
            if abs(local_pos.x() - pos.x()) <= half and abs(local_pos.y() - pos.y()) <= half:
                return name
        rp = self._rotate_handle_pos()
        if (local_pos - rp).manhattanLength() <= self._rotate_hit_size():
            return "rotate"
        return None

    # -- painting ---------------------------------------------------------
    def _unselected_option(self, option: QStyleOptionGraphicsItem) -> QStyleOptionGraphicsItem:
        """Strip State_Selected before delegating to the stock item's
        paint(). Every stock QGraphics*Item class draws its own black/white
        dashed selection rectangle whenever this flag is set; this app draws
        its own accent-colored handles instead (see _paint_handles), so
        without stripping the flag both would be drawn on top of each
        other."""
        stripped = QStyleOptionGraphicsItem(option)
        stripped.state &= ~QStyle.StateFlag.State_Selected  # type: ignore[attr-defined]
        return stripped

    def _paint_handles(self, painter: QPainter) -> None:
        if not self.isSelected():
            return
        pen = QPen(QColor(theme.ACCENT))
        pen.setWidth(0)
        painter.setPen(pen)
        painter.setBrush(QColor("#ffffff"))

        r = self.local_rect()
        rp = self._rotate_handle_pos()
        painter.drawLine(QPointF(r.center().x(), r.top()), rp)
        handle_size = self._handle_visual_size()
        painter.drawEllipse(rp, handle_size / 2, handle_size / 2)

        for pos in self._handle_positions().values():
            painter.drawRect(QRectF(pos.x() - handle_size / 2, pos.y() - handle_size / 2, handle_size, handle_size))

    # -- hover / cursor -----------------------------------------------------
    def hoverMoveEvent(self, event: QGraphicsSceneHoverEvent) -> None:  # noqa: N802
        handle = self._handle_at(event.pos()) if self.isSelected() else None
        self.setCursor(QCursor(_CURSOR_FOR_HANDLE[handle]) if handle else QCursor())
        super().hoverMoveEvent(event)

    # -- mouse: resize / rotate, falling back to normal move/select -----
    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802
        if self.isSelected():
            handle = self._handle_at(event.pos())
            if handle == "rotate":
                self._rotating = True
                center = self.mapToScene(self.local_rect().center())
                p = event.scenePos()
                self._rotate_start_angle = math.degrees(math.atan2(p.y() - center.y(), p.x() - center.x()))
                self._rotate_start_rotation = self.rotation()
                event.accept()
                return
            if handle:
                self._active_handle = handle
                self._resize_start_rect = self._resize_reference_rect()
                self._resize_start_pos = event.pos()
                self._resize_start_scene_pos = event.scenePos()
                self._resize_changed = False
                event.accept()
                return
        # Falling through to Qt's own default press/move/release handling --
        # that's what actually translates the item on drag (see itemChange
        # below), so mark the window during which a position change is a
        # real user drag rather than a programmatic setPos() (undo/redo,
        # initial placement, align/distribute, nudging, ...) that snapping
        # should leave alone.
        self._plain_dragging = True
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802
        if self._rotating:
            center = self.mapToScene(self.local_rect().center())
            p = event.scenePos()
            angle = math.degrees(math.atan2(p.y() - center.y(), p.x() - center.x()))
            self.setTransformOriginPoint(self.local_rect().center())
            self.setRotation(self._rotate_start_rotation + (angle - self._rotate_start_angle))
            event.accept()
            return
        if self._active_handle and self._resize_start_rect is not None:
            delta = self._resize_delta(event)
            new_rect = _resized_rect(self._resize_start_rect, self._active_handle, delta)
            new_rect = self._resize_target_rect(new_rect)
            self._apply_resize(new_rect)
            self._resize_changed = True
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802
        if self._rotating:
            self._rotating = False
            new_rotation = self.rotation()
            old_rotation = self._rotate_start_rotation
            if abs(new_rotation - old_rotation) > 0.01:
                self._push_undo(
                    lambda: self.setRotation(old_rotation),
                    lambda: self.setRotation(new_rotation),
                )
            self._refresh_properties_panel()
            event.accept()
            return
        if self._active_handle:
            self._active_handle = None
            if self._resize_changed and self._resize_start_rect is not None:
                old_rect = QRectF(self._resize_start_rect)
                new_rect = self._resize_reference_rect()
                self._push_undo(
                    lambda: self._apply_resize(old_rect),
                    lambda: self._apply_resize(new_rect),
                )
            self._refresh_properties_panel()
            event.accept()
            return
        super().mouseReleaseEvent(event)
        self._plain_dragging = False
        scene = self._typed_scene()
        if scene is not None:
            scene.clear_snap_guides()

    # -- magnetic snap while dragging (not resizing/rotating) -------------
    def itemChange(  # noqa: N802
        self, change: QGraphicsItem.GraphicsItemChange, value: object
    ) -> object:
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self._plain_dragging:
            scene = self._typed_scene()
            # Multi-item drags move every selected item independently through
            # this same hook with no shared leader to coordinate a common
            # correction, so snapping only engages for a single selected item
            # -- otherwise the group would skew apart as each item snaps to a
            # different, slightly different offset.
            if scene is not None and len(scene.selectedItems()) == 1:
                new_pos = cast(QPointF, value)
                delta = new_pos - self.pos()
                # self.pos() is still the pre-change position here -- Qt calls
                # itemChange() before applying it -- so this is the item's
                # real current on-screen rect, safe to translate by the
                # proposed delta below (rotation/scale aren't changing).
                proposed_rect = self.mapRectToScene(self.local_rect()).translated(delta)
                threshold = SNAP_THRESHOLD_PX / self._device_scale()
                dx, dy, guides = compute_snap(proposed_rect, scene.snap_targets(self), threshold)
                scene.show_snap_guides(guides)
                return new_pos + QPointF(dx, dy)
        return super().itemChange(change, value)

    def _push_undo(self, undo_fn: Callable[[], None], redo_fn: Callable[[], None]) -> None:
        scene = self._typed_scene()
        if scene is not None:
            scene.undo_stack.push(undo_fn, redo_fn)

    def _refresh_properties_panel(self) -> None:
        # Position & Size fields in the Properties panel (see right_sidebar.py)
        # don't update live during a drag -- refresh them once the resize/
        # rotate gesture actually finishes instead.
        scene = self._typed_scene()
        if scene is not None:
            scene.main_app.update_properties_panel()

    # -- typed size entry (Properties panel W/H fields) --------------------
    def set_size(self, width: float, height: float) -> None:
        # Reuses each subclass's own _resize_reference_rect()/
        # _resize_target_rect()/_apply_resize() overrides -- already handle
        # local-vs-scene coordinates, aspect lock (pixmap), and the width-only
        # pin (text) for handle-drag resizing, so a typed W/H entry (anchored
        # at the current top-left, since there's no drag handle/corner to
        # anchor from) gets all of that for free instead of re-deriving it.
        width = max(width, MIN_SIZE)
        height = max(height, MIN_SIZE)
        base = self._resize_reference_rect()
        requested = QRectF(base.topLeft(), QSizeF(width, height))
        self._apply_resize(self._resize_target_rect(requested))


class ResizableRectItem(_HandleMixin, QGraphicsRectItem):
    # Corner-only, matching every other item's 4-handle look -- freeform
    # (width/height still independent), just without the extra edge handles.
    RESIZE_HANDLES = _CORNER_HANDLES

    def local_rect(self) -> QRectF:
        return self.rect()

    def _apply_resize(self, rect: QRectF) -> None:
        self.setRect(rect)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None) -> None:
        super().paint(painter, self._unselected_option(option), widget)
        self._paint_handles(painter)


class ResizableEllipseItem(_HandleMixin, QGraphicsEllipseItem):
    RESIZE_HANDLES = _CORNER_HANDLES

    def local_rect(self) -> QRectF:
        return self.rect()

    def _apply_resize(self, rect: QRectF) -> None:
        self.setRect(rect)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None) -> None:
        super().paint(painter, self._unselected_option(option), widget)
        self._paint_handles(painter)


class ResizablePixmapItem(_HandleMixin, QGraphicsPixmapItem):
    """Images resize uniformly (aspect-locked) from the corners only.

    Unlike the shape items above, _apply_resize() here changes the item's own
    transform (setScale()) rather than a local geometry rect -- local_rect()
    is always just the native pixmap size and can't itself be resized. That
    breaks the mixin's default local-coordinate resize contract two ways: (1)
    event.pos() drifts mid-drag because it's computed against a transform
    that _apply_resize() is changing on every move, and (2) setScale() alone
    always anchors growth at the local origin (top-left) no matter which
    handle was actually dragged, so resizing from any corner but
    bottom-right visibly grew the image in the wrong direction. Overriding
    the resize hooks to work in scene coordinates instead fixes both: scene
    coordinates aren't affected by this item's own live transform, and a
    scene rect's topLeft doubles as the exact position the anchor corner
    needs to end up at.
    """

    RESIZE_HANDLES = _CORNER_HANDLES

    def local_rect(self) -> QRectF:
        return QRectF(self.pixmap().rect())

    def _resize_reference_rect(self) -> QRectF:
        return self.mapRectToScene(self.local_rect())

    def _resize_delta(self, event: QGraphicsSceneMouseEvent) -> QPointF:
        assert self._resize_start_scene_pos is not None
        return event.scenePos() - self._resize_start_scene_pos

    def _resize_target_rect(self, rect: QRectF) -> QRectF:
        # Aspect-locked resize has exactly one true degree of freedom, always
        # driven by width (see _apply_resize) -- the height and whichever of
        # top/bottom isn't the dragged edge must be re-derived from that
        # locked aspect ratio rather than trusting the raw (possibly
        # off-ratio) drag rect, or the anchor edge silently drifts.
        native = self.local_rect()
        if native.width() <= 0 or native.height() <= 0:
            return rect
        handle = self._active_handle or ""
        width = rect.width()
        height = width * (native.height() / native.width())
        top = rect.bottom() - height if "t" in handle else rect.top()
        return QRectF(rect.left(), top, width, height)

    def _apply_resize(self, rect: QRectF) -> None:
        # `rect` is a scene rect (see _resize_reference_rect/_resize_delta
        # above), so it's self-contained -- topLeft is exactly where the
        # anchor corner needs to be, independent of any transient drag
        # state, which keeps this safe to replay later for undo/redo.
        native = self.local_rect()
        if native.width() <= 0:
            return
        scale = max(rect.width() / native.width(), 0.05)
        self.setScale(scale)
        self.setPos(rect.topLeft())

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None) -> None:
        # QGraphicsPixmapItem.paint's stub (unlike QGraphicsItem's) omits the
        # Optional here even though Qt allows a null widget -- cast rather
        # than narrow our own signature away from the real base contract.
        super().paint(painter, self._unselected_option(option), cast(QWidget, widget))
        self._paint_handles(painter)


def _star_points(spikes: int = 5, inner_ratio: float = 0.4) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for i in range(spikes * 2):
        angle = -math.pi / 2 + i * math.pi / spikes
        radius = 0.5 if i % 2 == 0 else 0.5 * inner_ratio
        points.append((0.5 + radius * math.cos(angle), 0.5 + radius * math.sin(angle)))
    return points


# Keys match the shape-palette display text exactly (see left_sidebar.py),
# since that text is what travels through the drag-and-drop payload as the
# shape_type string -- same convention "Rectangle"/"Circle"/"Text Box" use.
POLYGON_TEMPLATES: dict[str, list[tuple[float, float]]] = {
    "Triangle": [(0.5, 0.0), (1.0, 1.0), (0.0, 1.0)],
    "Diamond": [(0.5, 0.0), (1.0, 0.5), (0.5, 1.0), (0.0, 0.5)],
    "Star": _star_points(),
    "Arrow": [(0.0, 0.35), (0.6, 0.35), (0.6, 0.15), (1.0, 0.5), (0.6, 0.85), (0.6, 0.65), (0.0, 0.65)],
}


class ResizablePolygonItem(_HandleMixin, QGraphicsPolygonItem):
    """A shape built from a POLYGON_TEMPLATES entry (normalized 0..1 points),
    rescaled to whatever bounding rect the user drags it to -- lets Triangle/
    Diamond/Star/Arrow all share one resize implementation instead of one
    class each. `shape_kind` is kept (not just the raw points) so the layers
    panel and persistence can identify which template an instance uses."""

    # Corner-only, matching every other item's 4-handle look -- freeform
    # (width/height still independent), just without the extra edge handles.
    RESIZE_HANDLES = _CORNER_HANDLES

    def __init__(self, shape_kind: str, width: float, height: float, parent: QGraphicsItem | None = None) -> None:
        super().__init__(parent)
        self.shape_kind = shape_kind
        self._local_bounds = QRectF(0, 0, width, height)
        self._sync_polygon()

    def local_rect(self) -> QRectF:
        return self._local_bounds

    def _apply_resize(self, rect: QRectF) -> None:
        self._local_bounds = QRectF(rect)
        self._sync_polygon()

    def _sync_polygon(self) -> None:
        rect = self._local_bounds
        template = POLYGON_TEMPLATES[self.shape_kind]
        points = [QPointF(rect.left() + fx * rect.width(), rect.top() + fy * rect.height()) for fx, fy in template]
        self.setPolygon(QPolygonF(points))

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None) -> None:
        super().paint(painter, self._unselected_option(option), widget)
        self._paint_handles(painter)


def get_layer_name(item: QGraphicsItem) -> str | None:
    return getattr(item, "layer_name", None)


def set_layer_name(item: QGraphicsItem, name: str | None) -> None:
    item.layer_name = name  # type: ignore[attr-defined]


def get_image_source(item: QGraphicsItem) -> str | None:
    """Original file path an image was imported from, if any -- not set for
    images created by duplicate/paste/project-load, which only carry the
    flattened pixmap. Used to show a filename in the image's Info panel."""
    return getattr(item, "image_source", None)


def set_image_source(item: QGraphicsItem, path: str | None) -> None:
    item.image_source = path  # type: ignore[attr-defined]


def is_layer_locked(item: QGraphicsItem) -> bool:
    return bool(getattr(item, "layer_locked", False))


def set_layer_locked(item: QGraphicsItem, locked: bool) -> None:
    item.layer_locked = locked  # type: ignore[attr-defined]
    item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, not locked)
    item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, not locked)
    if locked:
        item.setSelected(False)


def get_shape_kind(item: QGraphicsItem) -> str | None:
    return getattr(item, "shape_kind", None)


def set_shape_kind(item: QGraphicsItem, shape_kind: str) -> None:
    item.shape_kind = shape_kind  # type: ignore[attr-defined]


class RotatableTextItem(_HandleMixin, QGraphicsTextItem):
    """Text supports rotation plus horizontal resizing: dragging a corner
    handle sets an explicit wrap width and the text reflows inside it.
    Corner handles are offered (matching every other item's 4-handle look)
    but only their horizontal component does anything -- height has no
    independent value to set (QGraphicsTextItem lays out purely from
    textWidth; height always follows whatever the wrapped content needs), so
    vertical drag is ignored rather than fighting the reflowed height every
    frame or dragging the box vertically (see _resize_target_rect). Font
    size keeps its own control in the Properties panel; this only changes
    wrap width, not scale.
    """

    RESIZE_HANDLES: tuple[str, ...] = _CORNER_HANDLES

    def local_rect(self) -> QRectF:
        # Must call the unbound QGraphicsTextItem implementation directly --
        # `self.boundingRect()` would resolve to the mixin's own override
        # (which calls `local_rect()`), recursing infinitely.
        return QGraphicsTextItem.boundingRect(self)

    def _resize_reference_rect(self) -> QRectF:
        # Scene coordinates, not local -- _apply_resize() below calls
        # setPos() on every move, so (like ResizablePixmapItem) local
        # coordinates would drift mid-drag against a transform that's
        # changing under them. See _resize_delta().
        return self.mapRectToScene(self.local_rect())

    def _resize_delta(self, event: QGraphicsSceneMouseEvent) -> QPointF:
        assert self._resize_start_scene_pos is not None
        return event.scenePos() - self._resize_start_scene_pos

    def _resize_target_rect(self, rect: QRectF) -> QRectF:
        # Pin top/bottom back to their drag-start values -- only rect.left()/
        # right() (i.e. width) is ever real for text (see class docstring).
        # Without this, "tl"/"tr"/"bl"/"br" would also drag rect.top() or
        # bottom() per the raw two-axis handle math in _resized_rect(),
        # moving the box vertically for no visible reason since _apply_resize
        # never uses height.
        start = self._resize_start_rect
        if start is None:
            return rect
        return QRectF(rect.left(), start.top(), rect.width(), start.height())

    def _apply_resize(self, rect: QRectF) -> None:
        # rect.top() is always pinned to the drag-start value (see
        # _resize_target_rect), so topLeft() is exactly the scene position
        # the anchor edge (whichever one wasn't dragged) needs to stay at,
        # self-contained and safe to replay later for undo/redo.
        self.setTextWidth(max(rect.width(), MIN_SIZE))
        self.setPos(rect.topLeft())

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802
        # Items are created with NoTextInteraction so a single click
        # selects/drags them like any other item; double-click (matching the
        # "Double Click to Edit" placeholder) is what switches into editing.
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        super().mouseDoubleClickEvent(event)

    def focusOutEvent(self, event: QFocusEvent) -> None:  # noqa: N802
        # Drop back out of edit mode on blur, otherwise every later single
        # click places a text cursor instead of selecting/moving the item.
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        cursor = self.textCursor()
        cursor.clearSelection()
        self.setTextCursor(cursor)
        super().focusOutEvent(event)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None) -> None:
        # See ResizablePixmapItem.paint -- QGraphicsTextItem's stub has the
        # same Optional-less `widget` mismatch against the real base contract.
        super().paint(painter, self._unselected_option(option), cast(QWidget, widget))
        self._paint_handles(painter)


# -- size accessors for the Properties panel's Position & Size fields ------
# Free functions (not methods on the private _HandleMixin) so callers outside
# this module -- e.g. right_sidebar.py -- don't need to import/depend on it,
# matching the get_layer_name()/is_layer_locked() convention above.
def get_item_size(item: QGraphicsItem) -> tuple[float, float] | None:
    """(width, height) in scene units, or None for an item with no
    independent size (e.g. a QGraphicsItemGroup). Pixmap items report their
    *displayed* size (local_rect() scaled by item.scale()), not the native
    pixmap size, since that's what the user actually sees/expects to edit."""
    if not isinstance(item, _HandleMixin):
        return None
    rect = item.local_rect()
    if isinstance(item, ResizablePixmapItem):
        return rect.width() * item.scale(), rect.height() * item.scale()
    return rect.width(), rect.height()


def can_edit_height(item: QGraphicsItem) -> bool:
    # Text height always follows the wrapped content -- see RotatableTextItem.
    return not isinstance(item, RotatableTextItem)


def is_aspect_locked(item: QGraphicsItem) -> bool:
    return isinstance(item, ResizablePixmapItem)


def resize_item(item: QGraphicsItem, width: float, height: float) -> tuple[float, float] | None:
    """Applies a typed width/height (see _HandleMixin.set_size) and returns
    the item's real resulting size -- which may differ from what was asked
    for (aspect lock on images, height ignored entirely for text) -- or None
    if the item has no independent size to set."""
    if not isinstance(item, _HandleMixin):
        return None
    item.set_size(width, height)
    return get_item_size(item)
