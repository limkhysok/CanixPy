from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.core import icons, theme
from src.features.home.home_viewmodel import HomeViewModel
from src.features.home.models import Project

CONTENT_STYLE = f"""
QLabel#pageTitle {{
    font-size: 26px;
    font-weight: 700;
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
    margin-bottom: 2px;
}}
"""


class ProjectsPage(QWidget):
    """Lists project folders; drilling into one shows the tasks moved into it."""

    def __init__(self, viewmodel: HomeViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.viewmodel = viewmodel
        self.current_project: Project | None = None
        self.setStyleSheet(CONTENT_STYLE)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        self.stack = QStackedWidget()
        outer_layout.addWidget(self.stack)

        self.stack.addWidget(self._build_list_page())
        self.stack.addWidget(self._build_detail_page())

    def _build_list_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
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
        self.project_list.itemDoubleClicked.connect(self._on_project_opened)
        layout.addWidget(self.project_list)

        return page

    def _build_detail_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 32, 40, 32)
        layout.setSpacing(12)

        btn_back = QPushButton(icons.icon("fa5s.arrow-left"), "Back to Projects")
        btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_back.clicked.connect(self._show_list_page)
        layout.addWidget(btn_back)

        self.detail_title = QLabel()
        self.detail_title.setObjectName("pageTitle")
        layout.addWidget(self.detail_title)

        layout.addSpacing(8)
        layout.addWidget(QLabel("Tasks in this project:"))
        self.detail_task_list = QListWidget()
        self.detail_task_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.detail_task_list)

        layout.addWidget(QLabel("Unassigned tasks (select one to move here):"))
        self.unassigned_list = QListWidget()
        self.unassigned_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.unassigned_list)

        btn_move = QPushButton(icons.icon("fa5s.arrow-right"), "Move selected task here")
        btn_move.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_move.clicked.connect(self._on_move_task)
        layout.addWidget(btn_move)

        return page

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
        self.detail_title.setText(self.current_project.name)

        self.detail_task_list.clear()
        tasks_in_project = self.viewmodel.tasks_in_project(self.current_project.id)
        if not tasks_in_project:
            placeholder = QListWidgetItem("No tasks in this project yet.")
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            placeholder.setForeground(QBrush(QColor(theme.TEXT_SECONDARY)))
            self.detail_task_list.addItem(placeholder)
        else:
            for task in tasks_in_project:
                width, height = task.canvas_size
                text = f"{task.name}   ·   {width} x {height}"
                self.detail_task_list.addItem(QListWidgetItem(icons.icon("fa5s.file-alt", color=theme.ACCENT), text))

        self.unassigned_list.clear()
        unassigned = self.viewmodel.unassigned_tasks()
        if not unassigned:
            placeholder = QListWidgetItem("Nothing to move — every task is already in a project.")
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            placeholder.setForeground(QBrush(QColor(theme.TEXT_SECONDARY)))
            self.unassigned_list.addItem(placeholder)
        else:
            for task in unassigned:
                width, height = task.canvas_size
                item = QListWidgetItem(icons.icon("fa5s.file-alt", color=theme.ACCENT), f"{task.name}   ·   {width} x {height}")
                item.setData(Qt.ItemDataRole.UserRole, task)
                self.unassigned_list.addItem(item)

    def _on_move_task(self) -> None:
        item = self.unassigned_list.currentItem()
        if item is None or self.current_project is None:
            return
        task = item.data(Qt.ItemDataRole.UserRole)
        if task is None:
            return
        self.viewmodel.move_task_to_project(task.id, self.current_project.id)
        self.refresh()
