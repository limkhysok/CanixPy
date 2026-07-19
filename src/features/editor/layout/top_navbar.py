from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QWidget

from src.core import icons, theme

if TYPE_CHECKING:
    from src.features.editor.editor_view import CoreDesignApp

TOP_NAVBAR_STYLE = f"""
TopNavbar {{
    border-bottom: 1px solid {theme.BORDER};
}}
"""


class TopNavbar(QWidget):
    """Header strip above the canvas: back navigation, page switching, zoom, and export."""

    back_clicked = Signal()

    def __init__(self, main_app: "CoreDesignApp", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.main_app = main_app
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(TOP_NAVBAR_STYLE)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        btn_back = QPushButton(icons.icon("fa5s.arrow-left"), "Back")
        btn_back.clicked.connect(self.back_clicked.emit)
        layout.addWidget(btn_back)
        layout.addSpacing(30)

        self.page_selector = QComboBox()
        self.page_selector.currentIndexChanged.connect(main_app.on_page_combo_changed)
        btn_add_page = QPushButton(icons.icon("fa5s.plus"), "Add Page")
        btn_add_page.clicked.connect(main_app.add_new_page)

        btn_zoom_in = QPushButton(icons.icon("fa5s.search-plus"), "Zoom In")
        btn_zoom_out = QPushButton(icons.icon("fa5s.search-minus"), "Zoom Out")
        btn_zoom_reset = QPushButton(icons.icon("fa5s.undo"), "Reset")
        btn_zoom_in.clicked.connect(main_app.zoom_in)
        btn_zoom_out.clicked.connect(main_app.zoom_out)
        btn_zoom_reset.clicked.connect(main_app.zoom_reset)

        btn_export = QPushButton(icons.icon("fa5s.file-export", color=theme.TEXT_ON_ACCENT), "Export PNG")
        btn_export.setProperty("accent", True)
        btn_export.clicked.connect(main_app.export_page_to_png)

        layout.addWidget(QLabel("Pages:"))
        layout.addWidget(self.page_selector)
        layout.addWidget(btn_add_page)
        layout.addSpacing(30)
        layout.addWidget(btn_zoom_in)
        layout.addWidget(btn_zoom_out)
        layout.addWidget(btn_zoom_reset)
        layout.addSpacing(30)
        layout.addWidget(btn_export)
        layout.addStretch()
