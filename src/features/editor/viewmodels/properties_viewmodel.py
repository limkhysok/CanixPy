from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QColorDialog,
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsRectItem,
    QGraphicsTextItem,
)
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QGradient, QLinearGradient, QPen, QTextOption

from src.features.editor.canvas import items
from src.features.editor.canvas.items import make_shadow_effect
from src.features.editor.canvas.undo_manager import UndoStack

if TYPE_CHECKING:
    from src.features.editor.canvas.page import Page
    from src.features.editor.canvas.scene import DesignScene

DEFAULT_STROKE_WIDTH = 2


class PropertiesPanelViewModel:
    """Glue between the PropertiesPanel view and the graphics item(s) being edited."""

    def change_shape_color(self, item: QGraphicsRectItem | QGraphicsEllipseItem, undo_stack: UndoStack) -> None:
        old_brush = item.brush()
        color = QColorDialog.getColor()
        if color.isValid():
            new_brush = QBrush(color)
            item.setBrush(new_brush)
            undo_stack.push(lambda: item.setBrush(old_brush), lambda: item.setBrush(new_brush))

    def apply_gradient_fill(self, item: QGraphicsRectItem | QGraphicsEllipseItem, undo_stack: UndoStack) -> None:
        start = QColorDialog.getColor(QColor("#3498db"), None, "Pick Gradient Start Color")
        if not start.isValid():
            return
        end = QColorDialog.getColor(QColor("#8e44ad"), None, "Pick Gradient End Color")
        if not end.isValid():
            return
        old_brush = QBrush(item.brush())
        gradient = QLinearGradient(0, 0, 1, 1)
        # Object-bounding-box coordinates so the gradient stretches with the
        # shape instead of being pinned to the local coords it was created at.
        gradient.setCoordinateMode(QGradient.CoordinateMode.ObjectBoundingMode)
        gradient.setColorAt(0.0, start)
        gradient.setColorAt(1.0, end)
        new_brush = QBrush(gradient)
        item.setBrush(new_brush)
        undo_stack.push(lambda: item.setBrush(old_brush), lambda: item.setBrush(new_brush))

    def change_stroke_color(self, item: QGraphicsRectItem | QGraphicsEllipseItem, undo_stack: UndoStack) -> None:
        color = QColorDialog.getColor()
        if not color.isValid():
            return
        old_pen = QPen(item.pen())
        new_pen = QPen(item.pen())
        new_pen.setColor(color)
        if new_pen.width() == 0:
            new_pen.setWidth(DEFAULT_STROKE_WIDTH)
        item.setPen(new_pen)
        undo_stack.push(lambda: item.setPen(old_pen), lambda: item.setPen(new_pen))

    def set_stroke_width(self, item: QGraphicsRectItem | QGraphicsEllipseItem, width: int, undo_stack: UndoStack) -> None:
        old_pen = QPen(item.pen())
        new_pen = QPen(item.pen())
        new_pen.setWidth(width)
        item.setPen(new_pen)
        undo_stack.push(lambda: item.setPen(old_pen), lambda: item.setPen(new_pen))

    def set_opacity(self, item: QGraphicsItem, value: float, undo_stack: UndoStack) -> None:
        old_opacity = item.opacity()
        item.setOpacity(value)
        undo_stack.push(lambda: item.setOpacity(old_opacity), lambda: item.setOpacity(value))

    def set_opacity_multi(self, items: list[QGraphicsItem], value: float, undo_stack: UndoStack) -> None:
        old_opacities = {item: item.opacity() for item in items}

        def undo() -> None:
            for item, opacity in old_opacities.items():
                item.setOpacity(opacity)

        def redo() -> None:
            for item in items:
                item.setOpacity(value)

        redo()
        undo_stack.push(undo, redo)

    def toggle_shadow(self, item: QGraphicsItem, enabled: bool, undo_stack: UndoStack) -> None:
        had_shadow = item.graphicsEffect() is not None

        def apply(on: bool) -> None:
            item.setGraphicsEffect(make_shadow_effect() if on else None)

        apply(enabled)
        undo_stack.push(lambda: apply(had_shadow), lambda: apply(enabled))

    def toggle_shadow_multi(self, items: list[QGraphicsItem], enabled: bool, undo_stack: UndoStack) -> None:
        had_shadow = {item: item.graphicsEffect() is not None for item in items}

        def apply(on_map: dict[QGraphicsItem, bool] | bool) -> None:
            for item in items:
                on = on_map if isinstance(on_map, bool) else on_map[item]
                item.setGraphicsEffect(make_shadow_effect() if on else None)

        apply(enabled)
        undo_stack.push(lambda: apply(had_shadow), lambda: apply(enabled))

    def change_text_font(self, item: QGraphicsTextItem, font: QFont, undo_stack: UndoStack) -> None:
        old_font = item.font()
        new_font = QFont(old_font)
        new_font.setFamily(font.family())
        item.setFont(new_font)
        undo_stack.push(lambda: item.setFont(old_font), lambda: item.setFont(new_font))

    def change_text_size(self, item: QGraphicsTextItem, size: int, undo_stack: UndoStack) -> None:
        old_font = item.font()
        new_font = QFont(old_font)
        new_font.setPointSize(size)
        item.setFont(new_font)
        undo_stack.push(lambda: item.setFont(old_font), lambda: item.setFont(new_font))

    def change_text_color(self, item: QGraphicsTextItem, undo_stack: UndoStack) -> None:
        old_color = item.defaultTextColor()
        color = QColorDialog.getColor()
        if color.isValid():
            item.setDefaultTextColor(color)
            undo_stack.push(lambda: item.setDefaultTextColor(old_color), lambda: item.setDefaultTextColor(color))

    def toggle_text_bold(self, item: QGraphicsTextItem, bold: bool, undo_stack: UndoStack) -> None:
        old_font = item.font()
        new_font = QFont(old_font)
        new_font.setBold(bold)
        item.setFont(new_font)
        undo_stack.push(lambda: item.setFont(old_font), lambda: item.setFont(new_font))

    def toggle_text_italic(self, item: QGraphicsTextItem, italic: bool, undo_stack: UndoStack) -> None:
        old_font = item.font()
        new_font = QFont(old_font)
        new_font.setItalic(italic)
        item.setFont(new_font)
        undo_stack.push(lambda: item.setFont(old_font), lambda: item.setFont(new_font))

    def toggle_text_underline(self, item: QGraphicsTextItem, underline: bool, undo_stack: UndoStack) -> None:
        old_font = item.font()
        new_font = QFont(old_font)
        new_font.setUnderline(underline)
        item.setFont(new_font)
        undo_stack.push(lambda: item.setFont(old_font), lambda: item.setFont(new_font))

    def set_text_alignment(self, item: QGraphicsTextItem, alignment: Qt.AlignmentFlag, undo_stack: UndoStack) -> None:
        # Alignment only has visible effect once the text box has an explicit
        # wrap width -- default it to the current rendered width so alignment
        # works immediately without requiring the user to manually drag-resize
        # the text box first (see RotatableTextItem).
        if item.textWidth() < 0:
            item.setTextWidth(item.boundingRect().width())

        old_option = QTextOption(item.document().defaultTextOption())
        new_option = QTextOption(old_option)
        new_option.setAlignment(alignment)

        def apply(option: QTextOption) -> None:
            item.document().setDefaultTextOption(option)
            item.update()

        apply(new_option)
        undo_stack.push(lambda: apply(old_option), lambda: apply(new_option))

    def set_item_position(self, item: QGraphicsItem, x: float, y: float, undo_stack: UndoStack) -> None:
        old_pos = item.pos()
        new_pos = QPointF(x, y)
        if old_pos == new_pos:
            return
        item.setPos(new_pos)
        undo_stack.push(lambda: item.setPos(old_pos), lambda: item.setPos(new_pos))

    def set_item_size(
        self, item: QGraphicsItem, width: float, height: float, undo_stack: UndoStack
    ) -> tuple[float, float] | None:
        old = items.get_item_size(item)
        if old is None:
            return None
        new = items.resize_item(item, width, height)
        if new is None or new == old:
            return new
        undo_stack.push(lambda: items.resize_item(item, *old), lambda: items.resize_item(item, *new))
        return new

    def set_page_size(
        self, scene: "DesignScene", page: "Page", width: int, height: int, undo_stack: UndoStack
    ) -> None:
        old_w, old_h = page.width, page.height
        if (width, height) == (old_w, old_h):
            return
        scene.resize_page(page, width, height)
        undo_stack.push(
            lambda: scene.resize_page(page, old_w, old_h), lambda: scene.resize_page(page, width, height)
        )

    def change_page_background(self, page: "Page", undo_stack: UndoStack) -> None:
        old_color = QColor(page.background_color)
        color = QColorDialog.getColor(old_color)
        if color.isValid():
            page.set_background_color(color)
            undo_stack.push(
                lambda: page.set_background_color(old_color), lambda: page.set_background_color(QColor(color))
            )
