from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QStackedWidget, QVBoxLayout, QWidget

from src.core import theme
from src.features.home.models.models import Project
from src.features.home.viewmodels.home_viewmodel import HomeViewModel
from src.features.home.views.layout.left_sidebar import LeftSidebar
from src.features.home.views.layout.navbar import Navbar
from src.features.home.views.pages.home_page import HomePage
from src.features.home.views.pages.project_detail_page import ProjectDetailPage
from src.features.home.views.pages.projects_list_page import ProjectsListPage

# Shared chrome for every page hosted in `self.pages` -- page-specific styling
# (e.g. the recent-task cards) lives on the page widget itself instead.
CONTENT_STYLE = f"""
QLabel#pageTitle {{
    font-size: 36px;
    font-weight: 500;
    color: {theme.TEXT_PRIMARY};
}}
QLabel#sectionHeader {{
    font-size: 20px;
    font-weight: 500;
    color: {theme.TEXT_PRIMARY};
}}
QLabel#sectionCount {{
    color: {theme.TEXT_SECONDARY};
    font-size: 13px;
}}
QLabel#hintText {{
    color: {theme.TEXT_SECONDARY};
    font-size: 12px;
}}
QListWidget {{
    padding: 6px;
}}
QListWidget::item {{
    padding: 12px 10px;
    border-bottom: 1px solid {theme.BORDER};
    font-size: 15px;
}}
"""


class HomeView(QWidget):
    """The Home Screen shell: left nav (Home / Projects / ...) plus the active page."""

    open_editor = Signal(int, int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.viewmodel = HomeViewModel()
        self.setStyleSheet(CONTENT_STYLE)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.left_sidebar = LeftSidebar()
        self.left_sidebar.page_selected.connect(self._on_page_selected)
        layout.addWidget(self.left_sidebar)

        content_column = QWidget()
        content_layout = QVBoxLayout(content_column)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self.navbar = Navbar()
        self.navbar.toggle_clicked.connect(self.left_sidebar.set_collapsed)
        content_layout.addWidget(self.navbar)

        self.pages = QStackedWidget()
        content_layout.addWidget(self.pages, 1)

        layout.addWidget(content_column, 1)

        self.home_page = HomePage(self.viewmodel)
        self.home_page.open_editor.connect(self.open_editor)
        self.pages.addWidget(self.home_page)

        self.projects_root = QStackedWidget()

        self.projects_list_page = ProjectsListPage(self.viewmodel)
        self.projects_list_page.project_opened.connect(self._on_project_opened)
        self.projects_root.addWidget(self.projects_list_page)

        self.project_detail_page = ProjectDetailPage(self.viewmodel)
        self.project_detail_page.back_requested.connect(self._show_projects_list_page)
        self.project_detail_page.tasks_changed.connect(self.projects_list_page.refresh)
        self.projects_root.addWidget(self.project_detail_page)

        self.pages.addWidget(self.projects_root)

        self.pages.setCurrentWidget(self.home_page)

    def _on_page_selected(self, page_name: str) -> None:
        if page_name == "projects":
            self.projects_list_page.refresh()
            if self.project_detail_page.project is not None:
                self.project_detail_page.refresh()
            self.pages.setCurrentWidget(self.projects_root)
        else:
            self.home_page.refresh()
            self.pages.setCurrentWidget(self.home_page)

    def _on_project_opened(self, project: Project) -> None:
        self.project_detail_page.show_project(project)
        self.projects_root.setCurrentWidget(self.project_detail_page)

    def _show_projects_list_page(self) -> None:
        self.projects_list_page.refresh()
        self.projects_root.setCurrentWidget(self.projects_list_page)
