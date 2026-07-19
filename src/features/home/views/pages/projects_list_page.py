from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.core import icons, theme
from src.features.home.models.models import Project
from src.features.home.viewmodels.home_viewmodel import HomeViewModel


class ProjectsListPage(QWidget):
    """The Projects page: list of projects, plus create/open actions."""

    project_opened = Signal(Project)

    def __init__(self, viewmodel: HomeViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.viewmodel = viewmodel

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 32, 40, 32)
        layout.setSpacing(12)

        title = QLabel("Projects")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        self.project_count = QLabel()
        self.project_count.setObjectName("sectionCount")
        layout.addWidget(self.project_count)

        layout.addSpacing(8)

        btn_new_project = QPushButton(icons.icon("fa5s.folder-plus", color=theme.TEXT_ON_ACCENT), "New Project")
        btn_new_project.setProperty("accent", True)
        btn_new_project.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_new_project.clicked.connect(self._on_new_project)
        layout.addWidget(btn_new_project)

        hint = QLabel("Double-click a project to open it.")
        hint.setObjectName("hintText")
        layout.addWidget(hint)

        self.project_list = QListWidget()
        self.project_list.setCursor(Qt.CursorShape.PointingHandCursor)
        self.project_list.setIconSize(self.project_list.iconSize() * 1.2)
        self.project_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.project_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.project_list)

        self.refresh()

    def refresh(self) -> None:
        self.project_list.clear()
        projects = self.viewmodel.projects

        count = len(projects)
        self.project_count.setText(f"{count} project{'s' if count != 1 else ''}")

        if not projects:
            placeholder = QListWidgetItem(
                icons.icon("fa5s.folder-open", color=theme.TEXT_SECONDARY),
                "No projects yet — click “New Project” to create one.",
            )
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            placeholder.setForeground(QBrush(QColor(theme.TEXT_SECONDARY)))
            self.project_list.addItem(placeholder)
        else:
            for project in projects:
                task_count = len(self.viewmodel.tasks_in_project(project.id))
                label = f"{project.name}   ·   {task_count} task{'s' if task_count != 1 else ''}"
                item = QListWidgetItem(icons.icon("fa5s.folder", color=theme.ACCENT), label)
                item.setData(Qt.ItemDataRole.UserRole, project)
                self.project_list.addItem(item)

    def _on_new_project(self) -> None:
        name, ok = QInputDialog.getText(self, "New Project", "Project name:")
        if ok and name.strip():
            self.viewmodel.create_project(name.strip())
            self.refresh()

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        project = item.data(Qt.ItemDataRole.UserRole)
        if project is not None:
            self.project_opened.emit(project)
