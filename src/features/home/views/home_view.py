from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QStackedWidget, QWidget

from src.features.home.home_page import HomePage
from src.features.home.home_viewmodel import HomeViewModel
from src.features.home.layout.left_sidebar import LeftSidebar
from src.features.home.projects_page import ProjectsPage


class HomeView(QWidget):
    """The Home Screen: a left nav (Home / Projects) plus the active page."""

    open_editor = Signal(int, int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.viewmodel = HomeViewModel()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.left_sidebar = LeftSidebar()
        self.left_sidebar.page_selected.connect(self._on_page_selected)
        layout.addWidget(self.left_sidebar)

        self.pages = QStackedWidget()
        layout.addWidget(self.pages, 1)

        self.home_page = HomePage(self.viewmodel)
        self.home_page.open_editor.connect(self.open_editor.emit)
        self.pages.addWidget(self.home_page)

        self.projects_page = ProjectsPage(self.viewmodel)
        self.pages.addWidget(self.projects_page)

        self.pages.setCurrentWidget(self.home_page)

    def _on_page_selected(self, page_name: str) -> None:
        if page_name == "projects":
            self.projects_page.refresh()
            self.pages.setCurrentWidget(self.projects_page)
        else:
            self.home_page.refresh()
            self.pages.setCurrentWidget(self.home_page)
