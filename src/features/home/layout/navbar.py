from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from src.core import icons, theme

NAVBAR_STYLE = f"""
Navbar {{
    border-bottom: 1px solid {theme.BORDER};
}}
QPushButton#toggleButton {{
    background-color: transparent;
    border: none;
    border-radius: 6px;
    padding: 8px;
}}
QPushButton#toggleButton:hover {{
    background-color: {theme.BORDER};
}}
"""


class Navbar(QWidget):
    """Header strip at the top of the left sidebar holding the collapse/expand toggle."""

    toggle_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(NAVBAR_STYLE)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        self.toggle_button = QPushButton()
        self.toggle_button.setObjectName("toggleButton")
        self.toggle_button.setIcon(icons.icon("fa5s.angle-left", color=theme.TEXT_PRIMARY))
        self.toggle_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_button.setToolTip("Collapse sidebar")
        self.toggle_button.clicked.connect(self.toggle_clicked.emit)
        layout.addWidget(self.toggle_button)
        layout.setAlignment(self.toggle_button, Qt.AlignmentFlag.AlignLeft)

    def set_collapsed(self, collapsed: bool) -> None:
        icon_name = "fa5s.angle-right" if collapsed else "fa5s.angle-left"
        self.toggle_button.setIcon(icons.icon(icon_name, color=theme.TEXT_PRIMARY))
        self.toggle_button.setToolTip("Expand sidebar" if collapsed else "Collapse sidebar")

        alignment = Qt.AlignmentFlag.AlignHCenter if collapsed else Qt.AlignmentFlag.AlignLeft
        self.layout().setAlignment(self.toggle_button, alignment)
