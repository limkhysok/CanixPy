from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsEllipseItem, QGraphicsTextItem, QColorDialog
from PySide6.QtGui import QBrush, QFont


class PropertiesPanelViewModel:
    """Glue between the PropertiesPanel view and the graphics item being edited."""

    def change_shape_color(self, item: QGraphicsRectItem | QGraphicsEllipseItem) -> None:
        color = QColorDialog.getColor()
        if color.isValid():
            item.setBrush(QBrush(color))

    def change_text_font(self, item: QGraphicsTextItem, font: QFont) -> None:
        current_font = item.font()
        current_font.setFamily(font.family())
        item.setFont(current_font)

    def change_text_size(self, item: QGraphicsTextItem, size: int) -> None:
        current_font = item.font()
        current_font.setPointSize(size)
        item.setFont(current_font)

    def change_text_color(self, item: QGraphicsTextItem) -> None:
        color = QColorDialog.getColor()
        if color.isValid():
            item.setDefaultTextColor(color)
