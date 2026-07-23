from __future__ import annotations
from typing import TYPE_CHECKING
from PySide6.QtWidgets import (
    QGraphicsDropShadowEffect,
    QGraphicsItemGroup,
    QGraphicsLineItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsItem,
    QWidget,
)
from PySide6.QtCore import Qt, QLineF, QPointF, QRectF
from PySide6.QtGui import QBrush, QColor, QFont, QPen
from src.core import theme
from src.features.editor.canvas.items import (
    POLYGON_TEMPLATES,
    ResizableEllipseItem,
    ResizablePixmapItem,
    ResizablePolygonItem,
    ResizableRectItem,
    RotatableTextItem,
    set_image_source,
)
from src.features.editor.canvas.page import PAGE_GAP, Page, page_for_item
from src.features.editor.canvas.undo_manager import UndoStack

if TYPE_CHECKING:
    from src.features.editor.editor_view import CoreDesignApp

# Scene-unit padding kept independent of view.py's FIT_MARGIN (a related but
# distinct concept -- zoom-fit padding, not scene-rect padding) to avoid a
# circular import (view.py already imports DesignScene from this module).
SCENE_RECT_MARGIN = 40
# Extra bottom padding so the last page can be scrolled fully into view /
# centered rather than pinned flush against the scrollable limit.
SCROLL_END_MARGIN = 400

class DesignScene(QGraphicsScene):
    def __init__(self, main_app: "CoreDesignApp", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.main_app = main_app
        self.pages: list[Page] = []
        self.undo_stack = UndoStack(on_change=self.main_app.update_history_buttons)
        self.setBackgroundBrush(QBrush(QColor(theme.CANVAS_SURROUND)))
        self._snap_guide_items: list[QGraphicsLineItem] = []
        # QGraphicsScene.addItem() doesn't keep a PySide item's underlying
        # C++ object alive on its own -- a well-known PySide/PyQt
        # QGraphicsItem gotcha -- so items added *without* going through
        # add_items_with_undo() (whose undo/redo closures incidentally keep
        # a permanent reference) would otherwise silently vanish the moment
        # the caller's last Python reference goes out of scope. Only
        # add_items() (bulk, non-undoable additions -- see project load)
        # needs this explicitly; regular add/delete/duplicate already keep
        # items alive via their undo entries.
        self._item_refs: list[QGraphicsItem] = []
        self._update_scene_rect()
        self.selectionChanged.connect(self.main_app.sync_editor_selection)

    # --- page lifecycle ----------------------------------------------------
    def _create_frame(self, width: int, height: int, background_color: str) -> QGraphicsRectItem:
        # Very low fixed zValue so background frames don't intercept mouse
        # clicks; filled opaque so each page reads as a floating "sheet"
        # against the gray canvas surround.
        frame = self.addRect(0, 0, width, height)
        frame.setPen(QColor(theme.BORDER))
        frame.setBrush(QBrush(QColor(background_color)))
        frame.setZValue(-1000)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 3)
        shadow.setColor(QColor(0, 0, 0, 45))
        frame.setGraphicsEffect(shadow)
        return frame

    def add_page(
        self, width: int, height: int, background_color: str = "#ffffff", name: str | None = None
    ) -> Page:
        """Appends a new page below the current last one."""
        y = 0.0
        if self.pages:
            last = self.pages[-1]
            y = last.y_offset + last.height + PAGE_GAP
        frame = self._create_frame(width, height, background_color)
        frame.setPos(0, y)
        page = Page(frame, name)
        self.pages.append(page)
        self._update_scene_rect()
        return page

    def insert_page_after(
        self, source: Page, width: int, height: int, background_color: str = "#ffffff", name: str | None = None
    ) -> Page:
        """Inserts a new page directly below `source`, pushing every
        subsequent page down to make room."""
        # Snapshotted *before* the new frame is created/positioned -- the
        # new page's region starts out coinciding with wherever the old next
        # page currently sits (that's the whole point, it's about to push it
        # down), so page_for_item() evaluated after this point could
        # misattribute the old next page's items to the brand new, still-
        # empty page. See reflow_from()'s docstring for the general rule.
        partition = self._partition_items()
        index = self.pages.index(source)
        y = source.y_offset + source.height + PAGE_GAP
        frame = self._create_frame(width, height, background_color)
        frame.setPos(0, y)
        page = Page(frame, name)
        self.pages.insert(index + 1, page)
        self.reflow_from(index + 2, partition)
        return page

    def delete_page(self, page: Page) -> None:
        if len(self.pages) <= 1:
            return  # always keep at least one page
        partition = self._partition_items()
        index = self.pages.index(page)
        for item in partition.get(page, []):
            self.removeItem(item)
        self.removeItem(page.frame)
        self.pages.remove(page)
        partition.pop(page, None)
        self.reflow_from(index, partition)

    def resize_page(self, page: Page, width: float, height: float) -> None:
        # Snapshotted *before* resizing -- once page.set_size() runs, a page
        # that just grew can transiently overlap the next page's not-yet-
        # moved region, and page_for_item() would misattribute that page's
        # items to the resized one. See reflow_from()'s docstring.
        partition = self._partition_items()
        page.set_size(width, height)
        self.reflow_from(self.pages.index(page) + 1, partition)

    def move_page(self, page: Page, delta: int) -> None:
        index = self.pages.index(page)
        new_index = index + delta
        if not (0 <= new_index < len(self.pages)):
            return
        partition = self._partition_items()
        self.pages[index], self.pages[new_index] = self.pages[new_index], self.pages[index]
        self.reflow_from(min(index, new_index), partition)

    def page_frames(self) -> set[QGraphicsItem]:
        return {p.frame for p in self.pages}

    def _partition_items(self) -> dict[Page, list[QGraphicsItem]]:
        """Item->page assignment using the *current* page boundaries. Only
        meaningful when those boundaries are all still non-overlapping (i.e.
        before any page's geometry has been mutated this operation) -- see
        reflow_from()."""
        frames = self.page_frames()
        partition: dict[Page, list[QGraphicsItem]] = {p: [] for p in self.pages}
        for item in self.items():
            if item in frames or item.parentItem() is not None:
                continue
            partition[page_for_item(self.pages, item)].append(item)
        return partition

    def reflow_from(self, index: int, partition: dict[Page, list[QGraphicsItem]] | None = None) -> None:
        """Recomputes every page's y_offset from `index` onward (stacked
        top-to-bottom with PAGE_GAP), moving each page's own items along
        with it.

        `partition` should be captured via _partition_items() *before* the
        triggering page's geometry (resize/insert/delete/reorder) was
        mutated -- a page that just grew, or a newly inserted page, can
        transiently overlap a not-yet-moved neighbor's old region, and
        page_for_item()'s nearest-page tie-break would then misattribute
        that neighbor's items to the wrong page if evaluated after the fact.
        Defaults to computing it fresh (correct only when nothing has
        changed yet) as a convenience for any future direct caller -- every
        page-mutating method above passes an explicit pre-mutation snapshot.
        """
        if partition is None:
            partition = self._partition_items()
        moves: list[tuple[Page, float]] = []
        y = 0.0 if index == 0 else self.pages[index - 1].y_offset + self.pages[index - 1].height + PAGE_GAP
        for page in self.pages[index:]:
            delta = y - page.y_offset
            if delta:
                moves.append((page, delta))
            y += page.height + PAGE_GAP
        for page, delta in moves:
            page.set_y_offset(page.y_offset + delta)
            for item in partition.get(page, []):
                item.setPos(item.pos().x(), item.pos().y() + delta)
        self._update_scene_rect()

    def _update_scene_rect(self) -> None:
        if not self.pages:
            self.setSceneRect(0, 0, *self.main_app.canvas_size)
            return
        max_w = max(p.width for p in self.pages)
        bottom = self.pages[-1].y_offset + self.pages[-1].height
        self.setSceneRect(
            -SCENE_RECT_MARGIN,
            -SCENE_RECT_MARGIN,
            max_w + 2 * SCENE_RECT_MARGIN,
            bottom + SCENE_RECT_MARGIN + SCROLL_END_MARGIN,
        )

    # --- magnetic snap guides (see items.py _HandleMixin.itemChange) -----
    def snap_targets(self, moving: QGraphicsItem) -> list[QRectF]:
        """Every page's bounds plus every other top-level item's real
        (unpadded) visual rect in scene coordinates -- everything a drag can
        snap to, including pages the item isn't currently "in" (e.g.
        dragging toward the page below)."""
        selected = set(self.selectedItems())
        frames = self.page_frames()
        targets = [p.frame.sceneBoundingRect() for p in self.pages]
        for other in self.items():
            if other in frames or other is moving or other in selected or other.parentItem() is not None:
                continue
            local_rect = getattr(other, "local_rect", None)
            rect = other.mapRectToScene(local_rect()) if callable(local_rect) else other.sceneBoundingRect()
            targets.append(rect)
        return targets

    def show_snap_guides(self, lines: list[QLineF]) -> None:
        self.clear_snap_guides()
        pen = QPen(QColor(theme.ACCENT))
        pen.setWidth(0)
        pen.setStyle(Qt.PenStyle.DashLine)
        for line in lines:
            guide = self.addLine(line, pen)
            guide.setZValue(2000)  # above every real item and its handles
            self._snap_guide_items.append(guide)

    def clear_snap_guides(self) -> None:
        for guide in self._snap_guide_items:
            self.removeItem(guide)
        self._snap_guide_items = []

    def add_dropped_item(self, shape_type: str, pos: QPointF) -> None:
        if shape_type == "Rectangle":
            item = ResizableRectItem(0, 0, 150, 100)
            item.setBrush(QBrush(QColor("#3498db")))
        elif shape_type == "Circle":
            item = ResizableEllipseItem(0, 0, 100, 100)
            item.setBrush(QBrush(QColor("#e74c3c")))
        elif shape_type == "Line":
            item = ResizableRectItem(0, 0, 150, 4)
            item.setBrush(QBrush(QColor("#2c3e50")))
            item.shape_kind = "Line"  # tags it for the layers panel; it's still a plain thin rect underneath
        elif shape_type in POLYGON_TEMPLATES:
            item = ResizablePolygonItem(shape_type, 100, 100)
            item.setBrush(QBrush(QColor("#f39c12")))
        elif shape_type == "Text Box":
            self.add_text_item("Double Click to Edit", pos)
            return
        else:
            return

        item.setPos(pos.x() - 50, pos.y() - 50)
        item.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
        )
        self._add_item_with_undo(item)

    def add_text_item(
        self,
        text: str,
        pos: QPointF,
        font: QFont | None = None,
    ) -> None:
        item = RotatableTextItem(text)
        item.setFont(font or QFont("Arial", 16))
        item.setDefaultTextColor(QColor("#2c3e50"))
        # Starts non-editable so a single click selects/drags it like any
        # other item; RotatableTextItem switches into edit mode on double-click.
        item.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)

        # local_rect(), not boundingRect() -- boundingRect() is padded out to
        # reserve room for the resize/rotate handles (see items.py), which
        # would otherwise pull the actually-visible text well off the
        # intended drop point.
        bounds = item.local_rect()
        item.setPos(pos.x() - bounds.width() / 2, pos.y() - bounds.height() / 2)
        item.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
        )
        self._add_item_with_undo(item)

    # --- NEW LAYER MANAGEMENT FEATURES ---
    def bring_to_front(self, item: QGraphicsItem) -> None:
        all_items = self.items()
        if not all_items:
            return
        frames = self.page_frames()
        old_z = item.zValue()
        max_z = max((i.zValue() for i in all_items if i not in frames), default=0)
        new_z = max_z + 1
        item.setZValue(new_z)
        self._push_z_undo(item, old_z, new_z)
        self.main_app.refresh_editor_panels()

    def send_to_back(self, item: QGraphicsItem) -> None:
        all_items = self.items()
        if not all_items:
            return
        frames = self.page_frames()
        old_z = item.zValue()
        min_z = min((i.zValue() for i in all_items if i not in frames), default=0)
        new_z = min_z - 1
        item.setZValue(new_z)
        self._push_z_undo(item, old_z, new_z)
        self.main_app.refresh_editor_panels()

    def bring_items_to_front(self, items: list[QGraphicsItem]) -> None:
        frames = self.page_frames()
        items = [i for i in items if i not in frames]
        others = [i for i in self.items() if i not in frames and i not in items]
        if not items:
            return
        old_z = {item: item.zValue() for item in items}
        max_z = max((i.zValue() for i in others), default=0)
        # Preserve the moved items' order relative to each other.
        for offset, item in enumerate(sorted(items, key=lambda i: i.zValue())):
            item.setZValue(max_z + 1 + offset)
        self._push_group_z_undo(old_z, {item: item.zValue() for item in items})

    def send_items_to_back(self, items: list[QGraphicsItem]) -> None:
        frames = self.page_frames()
        items = [i for i in items if i not in frames]
        others = [i for i in self.items() if i not in frames and i not in items]
        if not items:
            return
        old_z = {item: item.zValue() for item in items}
        min_z = min((i.zValue() for i in others), default=0)
        sorted_items = sorted(items, key=lambda i: i.zValue())
        for offset, item in enumerate(sorted_items):
            item.setZValue(min_z - len(sorted_items) + offset)
        self._push_group_z_undo(old_z, {item: item.zValue() for item in items})

    def _push_group_z_undo(
        self, old_z: dict[QGraphicsItem, float], new_z: dict[QGraphicsItem, float]
    ) -> None:
        def undo() -> None:
            for item, z in old_z.items():
                item.setZValue(z)
            self.main_app.refresh_editor_panels()

        def redo() -> None:
            for item, z in new_z.items():
                item.setZValue(z)
            self.main_app.refresh_editor_panels()

        self.undo_stack.push(undo, redo)
        self.main_app.refresh_editor_panels()

    def _selection_bounds(self, items: list[QGraphicsItem]) -> QRectF:
        bounds = items[0].sceneBoundingRect()
        for item in items[1:]:
            bounds = bounds.united(item.sceneBoundingRect())
        return bounds

    def align_items(self, edge: str) -> None:
        """Align selected items to an edge/center. With one item selected,
        aligns it to its own page's bounds; with several, aligns them to each
        other's combined bounding box (like Figma's align-selection) --
        including when they span more than one page, sidestepping any need
        for a "which page" decision in that case."""
        frames = self.page_frames()
        items = [i for i in self.selectedItems() if i not in frames]
        if not items:
            return
        ref_rect = (
            page_for_item(self.pages, items[0]).rect()
            if len(items) == 1
            else self._selection_bounds(items)
        )

        old_positions = {item: item.pos() for item in items}
        for item in items:
            item_rect = item.sceneBoundingRect()
            dx = dy = 0.0
            if edge == "left":
                dx = ref_rect.left() - item_rect.left()
            elif edge == "h_center":
                dx = ref_rect.center().x() - item_rect.center().x()
            elif edge == "right":
                dx = ref_rect.right() - item_rect.right()
            elif edge == "top":
                dy = ref_rect.top() - item_rect.top()
            elif edge == "v_center":
                dy = ref_rect.center().y() - item_rect.center().y()
            elif edge == "bottom":
                dy = ref_rect.bottom() - item_rect.bottom()
            item.setPos(item.pos().x() + dx, item.pos().y() + dy)

        self._push_reposition_undo(items, old_positions)

    def distribute_items(self, axis: str) -> None:
        """Spread 3+ selected items with equal gaps between their bounding
        boxes along the given axis, anchoring the first/last items in place."""
        frames = self.page_frames()
        items = [i for i in self.selectedItems() if i not in frames]
        if len(items) < 3:
            return

        old_positions = {item: item.pos() for item in items}
        if axis == "horizontal":
            ordered = sorted(items, key=lambda i: i.sceneBoundingRect().left())
            span = ordered[-1].sceneBoundingRect().right() - ordered[0].sceneBoundingRect().left()
            total_width = sum(i.sceneBoundingRect().width() for i in ordered)
            gap = (span - total_width) / (len(ordered) - 1)
            cursor = ordered[0].sceneBoundingRect().left()
            for item in ordered:
                rect = item.sceneBoundingRect()
                item.setPos(item.pos().x() + (cursor - rect.left()), item.pos().y())
                cursor += rect.width() + gap
        else:
            ordered = sorted(items, key=lambda i: i.sceneBoundingRect().top())
            span = ordered[-1].sceneBoundingRect().bottom() - ordered[0].sceneBoundingRect().top()
            total_height = sum(i.sceneBoundingRect().height() for i in ordered)
            gap = (span - total_height) / (len(ordered) - 1)
            cursor = ordered[0].sceneBoundingRect().top()
            for item in ordered:
                rect = item.sceneBoundingRect()
                item.setPos(item.pos().x(), item.pos().y() + (cursor - rect.top()))
                cursor += rect.height() + gap

        self._push_reposition_undo(items, old_positions)

    def _push_reposition_undo(
        self, items: list[QGraphicsItem], old_positions: dict[QGraphicsItem, QPointF]
    ) -> None:
        moved = {
            item: (old_positions[item], item.pos())
            for item in items
            if old_positions[item] != item.pos()
        }
        if moved:
            self.push_move_undo(moved)

    def _push_z_undo(self, item: QGraphicsItem, old_z: float, new_z: float) -> None:
        def undo() -> None:
            item.setZValue(old_z)
            self.main_app.refresh_editor_panels()

        def redo() -> None:
            item.setZValue(new_z)
            self.main_app.refresh_editor_panels()

        self.undo_stack.push(undo, redo)

    def add_image_item(self, file_path: str, pos: QPointF) -> None:
        from PySide6.QtCore import Qt

        from src.core.image_loader import load_pixmap

        pixmap = load_pixmap(file_path)
        if pixmap is None:
            return  # Unreadable or unsupported file

        # Create a native image graphics item
        item = ResizablePixmapItem(pixmap)
        set_image_source(item, file_path)

        # Enable smooth transformation so images don't look pixelated when scaled or zoomed
        item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)

        # Center the image relative to where it was loaded/dropped. local_rect(),
        # not boundingRect() -- boundingRect() is padded out to reserve room for
        # the resize/rotate handles (see items.py), which would otherwise pull
        # the actually-visible image well off the intended drop point.
        bounds = item.local_rect()
        item.setPos(pos.x() - bounds.width() / 2, pos.y() - bounds.height() / 2)

        # Make it selectable and moveable
        item.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
        )
        self._add_item_with_undo(item)

    def _add_item_with_undo(self, item: QGraphicsItem) -> None:
        self.add_items_with_undo([item])

    def add_items(self, items: list[QGraphicsItem]) -> None:
        """Bulk add with no undo entry -- used for project load, where
        "undo" landing back on a blank page right after opening a file
        would be surprising. See the _item_refs comment in __init__ for why
        this needs to keep its own reference rather than relying on an
        undo closure to do it incidentally."""
        for item in items:
            self.addItem(item)
        self._item_refs.extend(items)

    def add_items_with_undo(self, items: list[QGraphicsItem]) -> None:
        for item in items:
            self.addItem(item)

        def undo() -> None:
            for item in items:
                self.removeItem(item)
            self.main_app.refresh_editor_panels()

        def redo() -> None:
            for item in items:
                self.addItem(item)
            self.main_app.refresh_editor_panels()

        self.undo_stack.push(undo, redo)
        self.main_app.refresh_editor_panels()

    def delete_items(self, items: list[QGraphicsItem]) -> None:
        frames = self.page_frames()
        items = [i for i in items if i not in frames]
        if not items:
            return

        for item in items:
            self.removeItem(item)

        def undo() -> None:
            for item in items:
                self.addItem(item)
            self.main_app.refresh_editor_panels()

        def redo() -> None:
            for item in items:
                self.removeItem(item)
            self.main_app.refresh_editor_panels()

        self.undo_stack.push(undo, redo)
        self.main_app.refresh_editor_panels()

    def group_items(self, items: list[QGraphicsItem]) -> None:
        frames = self.page_frames()
        items = [i for i in items if i not in frames]
        if len(items) < 2:
            return

        # `box` lets undo/redo share a mutable reference to the *current*
        # QGraphicsItemGroup -- createItemGroup/destroyItemGroup each produce
        # a fresh C++ object, so redo can't just reuse the one undo captured.
        box: dict[str, QGraphicsItemGroup | None] = {"group": None}

        def do() -> None:
            group = self.createItemGroup(items)
            group.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
            box["group"] = group
            self.clearSelection()
            group.setSelected(True)
            self.main_app.refresh_editor_panels()

        def undo() -> None:
            group = box["group"]
            if group is not None:
                self.destroyItemGroup(group)
                box["group"] = None
            self.clearSelection()
            for item in items:
                item.setSelected(True)
            self.main_app.refresh_editor_panels()

        do()
        self.undo_stack.push(undo, do)

    def ungroup_items(self, items: list[QGraphicsItem]) -> None:
        for item in items:
            if isinstance(item, QGraphicsItemGroup):
                self._ungroup_one(item)

    def _ungroup_one(self, group: QGraphicsItemGroup) -> None:
        children = list(group.childItems())
        box: dict[str, QGraphicsItemGroup | None] = {"group": group}

        def do() -> None:
            current = box["group"]
            if current is not None:
                self.destroyItemGroup(current)
                box["group"] = None
            self.clearSelection()
            for item in children:
                item.setSelected(True)
            self.main_app.refresh_editor_panels()

        def undo() -> None:
            new_group = self.createItemGroup(children)
            new_group.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
            box["group"] = new_group
            self.clearSelection()
            new_group.setSelected(True)
            self.main_app.refresh_editor_panels()

        do()
        self.undo_stack.push(undo, do)

    def push_move_undo(self, moved: dict[QGraphicsItem, tuple[QPointF, QPointF]]) -> None:
        def undo() -> None:
            for item, (old_pos, _new_pos) in moved.items():
                item.setPos(old_pos)

        def redo() -> None:
            for item, (_old_pos, new_pos) in moved.items():
                item.setPos(new_pos)

        self.undo_stack.push(undo, redo)
