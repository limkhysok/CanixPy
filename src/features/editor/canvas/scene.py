from __future__ import annotations
from typing import TYPE_CHECKING
from PySide6.QtWidgets import QGraphicsScene, QGraphicsRectItem, QGraphicsEllipseItem, QGraphicsTextItem, QGraphicsItem, QWidget
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QBrush, QColor, QFont

if TYPE_CHECKING:
    from src.features.editor.editor_view import CoreDesignApp

class DesignScene(QGraphicsScene):
    def __init__(self, main_app: "CoreDesignApp", parent: QWidget | None = None) -> None:
        super().__init__(0, 0, 800, 600, parent)
        self.main_app = main_app
        self.setBackgroundBrush(QBrush(QColor("#ffffff")))
        self.create_page_boundary()
        self.selectionChanged.connect(self.main_app.update_properties_panel)

    def create_page_boundary(self) -> None:
        # We assign a very low fixed zValue so background frames don't intercept mouse clicks
        self.page_frame = self.addRect(0, 0, 800, 600)
        self.page_frame.setPen(QColor("#cccccc"))
        self.page_frame.setZValue(-1000)

    def add_dropped_item(self, shape_type: str, pos: QPointF) -> None:
        if shape_type == "Rectangle":
            item = QGraphicsRectItem(0, 0, 150, 100)
            item.setBrush(QBrush(QColor("#3498db")))
        elif shape_type == "Circle":
            item = QGraphicsEllipseItem(0, 0, 100, 100)
            item.setBrush(QBrush(QColor("#e74c3c")))
        elif shape_type == "Text Box":
            item = QGraphicsTextItem("Double Click to Edit")
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
        self.addItem(item)

    # --- NEW LAYER MANAGEMENT FEATURES ---
    def bring_to_front(self, item: QGraphicsItem) -> None:
        all_items = self.items()
        if not all_items:
            return
        # Find the maximum Z value currently on canvas
        max_z = max(i.zValue() for i in all_items if i != self.page_frame)
        item.setZValue(max_z + 1)

    def send_to_back(self, item: QGraphicsItem) -> None:
        all_items = self.items()
        if not all_items:
            return
        # Find the minimum Z value currently on canvas, but stay in front of background
        min_z = min(i.zValue() for i in all_items if i != self.page_frame)
        item.setZValue(min_z - 1)
    def add_image_item(self, file_path: str, pos: QPointF) -> None:
        from PySide6.QtWidgets import QGraphicsPixmapItem
        from PySide6.QtGui import QPixmap
        from PySide6.QtCore import Qt

        pixmap = QPixmap(file_path)
        if pixmap.isNull():
            return  # Invalid image file

        # Create a native image graphics item
        item = QGraphicsPixmapItem(pixmap)
        
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
        self.addItem(item)