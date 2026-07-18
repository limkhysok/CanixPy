from __future__ import annotations

from PySide6.QtCore import QSize, Signal, Qt
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from src.core import icons, theme

SIDEBAR_STYLE = f"""
NavSidebar {{
    background-color: {theme.SURFACE};
    border-right: 1px solid {theme.BORDER};
}}
QListWidget {{
    background-color: transparent;
    border: none;
    outline: none;
    padding: 12px 8px;
    font-size: 14px;
}}
QListWidget::item {{
    padding: 10px 12px;
    border-radius: 8px;
    margin-bottom: 4px;
    color: {theme.TEXT_PRIMARY};
}}
QListWidget::item:hover {{
    background-color: {theme.BORDER};
}}
QListWidget::item:selected {{
    background-color: {theme.ACCENT};
    color: {theme.TEXT_ON_ACCENT};
}}
"""


class NavSidebar(QWidget):
    """Left navigation between the Home (recent work) and Projects (folders) pages."""

    page_selected = Signal(str)  # "home" | "projects"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(240)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(SIDEBAR_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.nav_list = QListWidget()
        self.nav_list.setIconSize(QSize(20, 20))
        self.nav_list.addItem(self._nav_item("fa5s.home", "Home"))
        self.nav_list.addItem(self._nav_item("fa5s.folder", "Projects"))
        self.nav_list.currentRowChanged.connect(self._on_row_changed)
        layout.addWidget(self.nav_list)

        self.nav_list.setCurrentRow(0)

    @staticmethod
    def _nav_item(icon_name: str, label: str) -> QListWidgetItem:
        icon = icons.icon(
            icon_name,
            color=theme.TEXT_PRIMARY,
            color_selected=theme.TEXT_ON_ACCENT,
        )
        return QListWidgetItem(icon, label)

    def _on_row_changed(self, row: int) -> None:
        self.page_selected.emit("projects" if row == 1 else "home")
