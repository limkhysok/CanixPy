from __future__ import annotations
from pathlib import Path
from typing import TYPE_CHECKING
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QListWidget, QListWidgetItem, QPushButton, QLabel, QFileDialog
from PySide6.QtCore import Qt, QSize, QPointF, QMimeData
from PySide6.QtGui import QDrag
from src.core import icons, theme
from src.features.editor.layout.layers_panel import LayersPanel

if TYPE_CHECKING:
    from src.features.editor.editor_view import CoreDesignApp

LEFT_SIDEBAR_STYLE = theme.load_qss(Path(__file__).with_name("left_sidebar.qss"))

SHAPE_ICONS = {
    "Rectangle": "fa5s.square",
    "Circle": "fa5s.circle",
    "Line": "fa5s.grip-lines",
    "Triangle": "fa5s.play",
    "Diamond": "fa5s.gem",
    "Star": "fa5s.star",
    "Arrow": "fa5s.long-arrow-alt-right",
    "Text Box": "fa5s.font",
}

SECTION_ICONS = {
    "Shapes": "fa5s.shapes",
    "Layers": "fa5s.layer-group",
    "Media Assets": "fa5s.photo-video",
}

def _section_header(text: str) -> QWidget:
    row = QWidget()
    row_layout = QHBoxLayout(row)
    row_layout.setContentsMargins(0, 0, 0, 0)
    row_layout.setSpacing(6)

    icon_name = SECTION_ICONS.get(text)
    if icon_name:
        icon_label = QLabel()
        icon_label.setPixmap(icons.icon(icon_name, color=theme.ACCENT).pixmap(12, 12))
        row_layout.addWidget(icon_label)

    text_label = QLabel(text.upper())
    text_label.setObjectName("sectionHeader")
    row_layout.addWidget(text_label)
    row_layout.addStretch()
    return row

class DraggableListWidget(QListWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        # Capped (not unlimited) height -- it's a static palette, not a
        # growing list, so it shouldn't compete with the Layers list below
        # for vertical space; it scrolls internally once it outgrows this.
        self.setMaximumHeight(200)
        for shape in SHAPE_ICONS:
            self.add_shape_item(shape)

    def add_shape_item(self, text: str) -> None:
        item = QListWidgetItem(icons.icon(SHAPE_ICONS[text]), text, self)
        item.setSizeHint(QSize(80, 40))
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

    def startDrag(self, supported_actions: Qt.DropAction) -> None:
        item = self.currentItem()
        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setText(item.text())
        drag.setMimeData(mime_data)
        drag.exec(Qt.DropAction.CopyAction)


# Wrap both the list widget and the upload button together into a clean Sidebar Widget
class LeftSidebar(QWidget):
    def __init__(self, main_app: "CoreDesignApp", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.main_app = main_app
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(LEFT_SIDEBAR_STYLE)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        layout.addWidget(_section_header("Shapes"))
        self.drag_list = DraggableListWidget()
        layout.addWidget(self.drag_list)

        layout.addSpacing(8)
        layout.addWidget(_section_header("Layers"))
        self.layers_panel = LayersPanel(main_app)
        layout.addWidget(self.layers_panel, 1)

        layout.addSpacing(8)
        layout.addWidget(_section_header("Media Assets"))

        btn_upload = QPushButton(icons.icon("fa5s.image"), "Upload Image")
        btn_upload.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_upload.clicked.connect(self.trigger_image_upload)
        layout.addWidget(btn_upload)

    def trigger_image_upload(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Select Local Image Asset", 
            "", 
            "Images (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        if file_path:
            # Spawn the image right in the middle of the current canvas frame
            center_point = QPointF(400, 300)
            self.main_app.scene.add_image_item(file_path, center_point)