from __future__ import annotations
from typing import TYPE_CHECKING
from PySide6.QtWidgets import (
    QGraphicsDropShadowEffect,
    QGraphicsItemGroup,
    QGraphicsScene,
    QGraphicsItem,
    QWidget,
)
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QBrush, QColor, QFont
from src.core import theme
from src.features.editor.canvas.items import (
    POLYGON_TEMPLATES,
    ResizableEllipseItem,
    ResizablePixmapItem,
    ResizablePolygonItem,
    ResizableRectItem,
    RotatableTextItem,
)
from src.features.editor.canvas.undo_manager import UndoStack

if TYPE_CHECKING:
    from src.features.editor.editor_view import CoreDesignApp

class DesignScene(QGraphicsScene):
    def __init__(
        self,
        main_app: "CoreDesignApp",
        width: int = 800,
        height: int = 600,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(0, 0, width, height, parent)
        self.main_app = main_app
        self.width_px = width
        self.height_px = height
        self.page_name: str | None = None  # None means "auto-numbered by position"
        self.undo_stack = UndoStack(on_change=self.main_app.update_history_buttons)
        self.setBackgroundBrush(QBrush(QColor(theme.CANVAS_SURROUND)))
        self.create_page_boundary()
        self.selectionChanged.connect(self.main_app.sync_editor_selection)

    def create_page_boundary(self) -> None:
        # We assign a very low fixed zValue so background frames don't intercept mouse clicks.
        # It's filled opaque white so it reads as a floating "page" against the gray canvas surround.
        self.page_frame = self.addRect(0, 0, self.width_px, self.height_px)
        self.page_frame.setPen(QColor(theme.BORDER))
        self.page_frame.setBrush(QBrush(QColor("#ffffff")))
        self.page_frame.setZValue(-1000)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 3)
        shadow.setColor(QColor(0, 0, 0, 45))
        self.page_frame.setGraphicsEffect(shadow)

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
            item = RotatableTextItem("Double Click to Edit")
            item.setFont(QFont("Arial", 16))
            item.setDefaultTextColor(QColor("#2c3e50"))
            item.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditable)
        else:
            return

        item.setPos(pos.x() - 50, pos.y() - 50)
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
        # Find the maximum Z value currently on canvas
        old_z = item.zValue()
        max_z = max(i.zValue() for i in all_items if i != self.page_frame)
        new_z = max_z + 1
        item.setZValue(new_z)
        self._push_z_undo(item, old_z, new_z)
        self.main_app.refresh_editor_panels()

    def send_to_back(self, item: QGraphicsItem) -> None:
        all_items = self.items()
        if not all_items:
            return
        # Find the minimum Z value currently on canvas, but stay in front of background
        old_z = item.zValue()
        min_z = min(i.zValue() for i in all_items if i != self.page_frame)
        new_z = min_z - 1
        item.setZValue(new_z)
        self._push_z_undo(item, old_z, new_z)
        self.main_app.refresh_editor_panels()

    def bring_items_to_front(self, items: list[QGraphicsItem]) -> None:
        items = [i for i in items if i != self.page_frame]
        others = [i for i in self.items() if i != self.page_frame and i not in items]
        if not items:
            return
        old_z = {item: item.zValue() for item in items}
        max_z = max((i.zValue() for i in others), default=0)
        # Preserve the moved items' order relative to each other.
        for offset, item in enumerate(sorted(items, key=lambda i: i.zValue())):
            item.setZValue(max_z + 1 + offset)
        self._push_group_z_undo(old_z, {item: item.zValue() for item in items})

    def send_items_to_back(self, items: list[QGraphicsItem]) -> None:
        items = [i for i in items if i != self.page_frame]
        others = [i for i in self.items() if i != self.page_frame and i not in items]
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
        aligns it to the page bounds; with several, aligns them to each
        other's combined bounding box (like Figma's align-selection)."""
        items = [i for i in self.selectedItems() if i != self.page_frame]
        if not items:
            return
        ref_rect = (
            QRectF(0, 0, self.width_px, self.height_px)
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
        items = [i for i in self.selectedItems() if i != self.page_frame]
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

        # Enable smooth transformation so images don't look pixelated when scaled or zoomed
        item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)

        # Center the image relative to where it was loaded/dropped
        bounds = item.boundingRect()
        item.setPos(pos.x() - bounds.width() / 2, pos.y() - bounds.height() / 2)

        # Make it selectable and moveable
        item.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
        )
        self._add_item_with_undo(item)

    def _add_item_with_undo(self, item: QGraphicsItem) -> None:
        self.add_items_with_undo([item])

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
        items = [i for i in items if i != self.page_frame]
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
        items = [i for i in items if i != self.page_frame]
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
