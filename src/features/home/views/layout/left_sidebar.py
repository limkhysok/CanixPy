from __future__ import annotations

from PySide6.QtCore import QSize, Signal, Qt
from PySide6.QtWidgets import QButtonGroup, QPushButton, QVBoxLayout, QWidget

from src.core import icons, theme
from src.features.home.layout.navbar import Navbar

LEFT_SIDEBAR_STYLE = f"""
LeftSidebar {{
    background-color: {theme.SURFACE};
    border-right: 1px solid {theme.BORDER};
}}
QPushButton#navButton {{
    background-color: transparent;
    border: none;
    border-radius: 8px;
    padding: 9px 12px;
    text-align: left;
    color: {theme.TEXT_PRIMARY};
    font-size: 13px;
    font-weight: 500;
}}
QPushButton#navButton:hover {{
    background-color: {theme.BORDER};
}}
QPushButton#navButton:checked {{
    background-color: {theme.ACCENT_LIGHT};
    color: {theme.ACCENT};
    font-weight: 600;
}}
"""

NAV_ITEMS = [
    ("fa5s.home", "Home"),
    ("fa5s.folder", "Projects"),
]

ICON_SIZE = QSize(17, 17)


class LeftSidebar(QWidget):
    """Left navigation between the Home (recent work) and Projects (folders) pages."""

    page_selected = Signal(str)  # "home" | "projects"

    EXPANDED_WIDTH = 208
    COLLAPSED_WIDTH = 64

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(LEFT_SIDEBAR_STYLE)
        self._collapsed = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.navbar = Navbar()
        self.navbar.toggle_clicked.connect(self.toggle_collapsed)
        layout.addWidget(self.navbar)

        nav_layout = QVBoxLayout()
        nav_layout.setContentsMargins(8, 8, 8, 8)
        nav_layout.setSpacing(2)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons: list[QPushButton] = []

        for row, (icon_name, label) in enumerate(NAV_ITEMS):
            button = self._build_nav_button(icon_name, label)
            self.nav_group.addButton(button, row)
            self.nav_buttons.append(button)
            nav_layout.addWidget(button)

        nav_layout.addStretch()
        layout.addLayout(nav_layout)

        self.nav_group.idClicked.connect(self._on_nav_clicked)
        self.nav_buttons[0].setChecked(True)

        self.setFixedWidth(self.EXPANDED_WIDTH)

    def _build_nav_button(self, icon_name: str, label: str) -> QPushButton:
        button = QPushButton(label)
        button.setObjectName("navButton")
        button.setCheckable(True)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setIconSize(ICON_SIZE)
        button.setIcon(icons.icon(icon_name, color=theme.TEXT_PRIMARY))
        button.setProperty("icon_name", icon_name)
        def on_toggled(checked: bool) -> None:
            self._restyle_icon(button, checked)

        button.toggled.connect(on_toggled)
        return button

    @staticmethod
    def _restyle_icon(button: QPushButton, checked: bool) -> None:
        icon_name: str = button.property("icon_name")
        color = theme.ACCENT if checked else theme.TEXT_PRIMARY
        button.setIcon(icons.icon(icon_name, color=color))

    def toggle_collapsed(self) -> None:
        self._collapsed = not self._collapsed
        self.setFixedWidth(self.COLLAPSED_WIDTH if self._collapsed else self.EXPANDED_WIDTH)

        for row, (_, label) in enumerate(NAV_ITEMS):
            button = self.nav_buttons[row]
            button.setText("" if self._collapsed else label)
            button.setToolTip(label if self._collapsed else "")

        self.navbar.set_collapsed(self._collapsed)

    def _on_nav_clicked(self, row: int) -> None:
        self.page_selected.emit("projects" if row == 1 else "home")
