from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.core import icons, theme
from src.features.home.home_viewmodel import HomeViewModel
from src.features.home.models import Project


class ProjectsPage(QWidget):
    """Lists project folders; drilling into one shows the tasks moved into it."""

    def __init__(self, viewmodel: HomeViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.viewmodel = viewmodel
        self.current_project: Project | None = None

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        self.stack = QStackedWidget()
        outer_layout.addWidget(self.stack)

        self.stack.addWidget(self._build_list_page())
        self.stack.addWidget(self._build_detail_page())

    def _build_list_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        layout.addWidget(QLabel("<h2>Projects</h2>"))

        btn_new_project = QPushButton(icons.icon("fa5s.folder-plus", color=theme.TEXT_ON_ACCENT), "New Project")
        btn_new_project.setProperty("accent", True)
        btn_new_project.clicked.connect(self._on_new_project)
        layout.addWidget(btn_new_project)

        self.project_list = QListWidget()
        self.project_list.itemDoubleClicked.connect(self._on_project_opened)
        layout.addWidget(self.project_list)

        return page

    def _build_detail_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        btn_back = QPushButton(icons.icon("fa5s.arrow-left"), "Back to Projects")
        btn_back.clicked.connect(self._show_list_page)
        layout.addWidget(btn_back)

        self.detail_title = QLabel()
        layout.addWidget(self.detail_title)

        layout.addWidget(QLabel("Tasks in this project:"))
        self.detail_task_list = QListWidget()
        layout.addWidget(self.detail_task_list)

        layout.addWidget(QLabel("Unassigned tasks (select one to move here):"))
        self.unassigned_list = QListWidget()
        layout.addWidget(self.unassigned_list)

        btn_move = QPushButton(icons.icon("fa5s.arrow-right"), "Move selected task here")
        btn_move.clicked.connect(self._on_move_task)
        layout.addWidget(btn_move)

        return page

    def refresh(self) -> None:
        self.project_list.clear()
        for project in self.viewmodel.projects:
            count = len(self.viewmodel.tasks_in_project(project.id))
            item = QListWidgetItem(icons.icon("fa5s.folder"), f"{project.name}  ({count})")
            item.setData(Qt.ItemDataRole.UserRole, project)
            self.project_list.addItem(item)

        if self.current_project is not None:
            self._refresh_detail_page()

    def _on_new_project(self) -> None:
        name, ok = QInputDialog.getText(self, "New Project", "Project name:")
        if ok and name.strip():
            self.viewmodel.create_project(name.strip())
            self.refresh()

    def _on_project_opened(self, item: QListWidgetItem) -> None:
        self.current_project = item.data(Qt.ItemDataRole.UserRole)
        self._refresh_detail_page()
        self.stack.setCurrentIndex(1)

    def _show_list_page(self) -> None:
        self.current_project = None
        self.stack.setCurrentIndex(0)

    def _refresh_detail_page(self) -> None:
        assert self.current_project is not None
        self.detail_title.setText(f"<h2>{self.current_project.name}</h2>")

        self.detail_task_list.clear()
        for task in self.viewmodel.tasks_in_project(self.current_project.id):
            width, height = task.canvas_size
            text = f"{task.name}  ({width} x {height})"
            self.detail_task_list.addItem(QListWidgetItem(icons.icon("fa5s.file-alt"), text))

        self.unassigned_list.clear()
        for task in self.viewmodel.unassigned_tasks():
            width, height = task.canvas_size
            item = QListWidgetItem(icons.icon("fa5s.file-alt"), f"{task.name}  ({width} x {height})")
            item.setData(Qt.ItemDataRole.UserRole, task)
            self.unassigned_list.addItem(item)

    def _on_move_task(self) -> None:
        item = self.unassigned_list.currentItem()
        if item is None or self.current_project is None:
            return
        task = item.data(Qt.ItemDataRole.UserRole)
        self.viewmodel.move_task_to_project(task.id, self.current_project.id)
        self.refresh()
