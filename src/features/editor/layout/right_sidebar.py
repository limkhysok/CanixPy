from __future__ import annotations
from typing import TYPE_CHECKING
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QFontComboBox, QSpinBox
from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsEllipseItem, QGraphicsTextItem, QGraphicsItem
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from src.core import icons, theme
from src.features.editor.properties_viewmodel import PropertiesPanelViewModel

if TYPE_CHECKING:
    from src.features.editor.editor_view import CoreDesignApp

RIGHT_SIDEBAR_STYLE = f"""
PropertiesPanel {{
    border-left: 1px solid {theme.BORDER};
}}
"""

class PropertiesPanel(QWidget):
    def __init__(self, main_app: "CoreDesignApp", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.main_app = main_app
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(RIGHT_SIDEBAR_STYLE)
        self.viewmodel = PropertiesPanelViewModel()

        # Outer layout spans the whole widget (so the border-left runs the full
        # column height); dynamic inspector content lives in the nested
        # main_layout, which clear_layout()/inspect_item() rebuild in place.
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(QLabel("<b>Properties Panel</b>"))

        self.main_layout = QVBoxLayout()
        outer_layout.addLayout(self.main_layout)
        outer_layout.addStretch()

        self.show_empty_state()

    def show_empty_state(self) -> None:
        self.clear_layout()
        self.main_layout.addWidget(QLabel("Select an item to edit its assets."))

    def clear_layout(self) -> None:
        for i in reversed(range(self.main_layout.count())):
            widget = self.main_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

    def inspect_item(self, item: QGraphicsItem | None) -> None:
        self.clear_layout()
        if not item or item == getattr(self.main_app.scene, 'page_frame', None):
            self.show_empty_state()
            return

        # 1. Custom settings depending on type
        if isinstance(item, (QGraphicsRectItem, QGraphicsEllipseItem)):
            btn_color = QPushButton(icons.icon("fa5s.palette"), "Change Color")
            btn_color.clicked.connect(lambda: self.viewmodel.change_shape_color(item))
            self.main_layout.addWidget(QLabel("Shape Styling:"))
            self.main_layout.addWidget(btn_color)

        elif isinstance(item, QGraphicsTextItem):
            self.main_layout.addWidget(QLabel("Font Family:"))
            font_box = QFontComboBox()
            font_box.setCurrentFont(item.font())

            def on_font_changed(font: QFont) -> None:
                self.viewmodel.change_text_font(item, font)
            font_box.currentFontChanged.connect(on_font_changed)
            self.main_layout.addWidget(font_box)

            self.main_layout.addWidget(QLabel("Font Size:"))
            size_box = QSpinBox()
            size_box.setRange(8, 120)
            size_box.setValue(item.font().pointSize())

            def on_size_changed(size: int) -> None:
                self.viewmodel.change_text_size(item, size)
            size_box.valueChanged.connect(on_size_changed)
            self.main_layout.addWidget(size_box)

            btn_color = QPushButton(icons.icon("fa5s.palette"), "Text Color")
            btn_color.clicked.connect(lambda: self.viewmodel.change_text_color(item))
            self.main_layout.addWidget(btn_color)

        # 2. GLOBAL ARRANGE TOOL LAYOUT (Available for all items)
        self.main_layout.addSpacing(15)
        self.main_layout.addWidget(QLabel("<b>Arrangement</b>"))

        btn_front = QPushButton(icons.icon("fa5s.arrow-up"), "Bring to Front")
        btn_front.clicked.connect(lambda: self.main_app.scene.bring_to_front(item))
        self.main_layout.addWidget(btn_front)

        btn_back = QPushButton(icons.icon("fa5s.arrow-down"), "Send to Back")
        btn_back.clicked.connect(lambda: self.main_app.scene.send_to_back(item))
        self.main_layout.addWidget(btn_back)