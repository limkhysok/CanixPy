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
from src.features.home.models.models import Project
from src.features.home.viewmodels.home_viewmodel import HomeViewModel

TASK_ICON = "fa5s.file-alt"


class ProjectPage(QWidget):
    """Projects area: list of projects, plus create/open actions and a project's detail view."""

    def __init__(self, viewmodel: HomeViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.viewmodel = viewmodel
        self.project: Project | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._stack = QStackedWidget()
        layout.addWidget(self._stack)

        self._list_widget = self._build_list_page()
        self._stack.addWidget(self._list_widget)

        self._detail_widget = self._build_detail_page()
        self._stack.addWidget(self._detail_widget)

    # -- list page --------------------------------------------------------

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
        self.project_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.project_list)

        return page

    def _refresh_list(self) -> None:
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
            self._refresh_list()

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        project = item.data(Qt.ItemDataRole.UserRole)
        if project is not None:
            self.project = project
            self._refresh_detail()
            self._stack.setCurrentWidget(self._detail_widget)

    # -- detail page --------------------------------------------------------

    def _build_detail_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 32, 40, 32)
        layout.setSpacing(12)

        btn_back = QPushButton(icons.icon("fa5s.arrow-left"), "Back to Projects")
        btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_back.clicked.connect(self.show_list)
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

    def _refresh_detail(self) -> None:
        if self.project is None:
            return
        self.detail_title.setText(self.project.name)

        self.detail_task_list.clear()
        tasks_in_project = self.viewmodel.tasks_in_project(self.project.id)
        if not tasks_in_project:
            placeholder = QListWidgetItem("No tasks in this project yet.")
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            placeholder.setForeground(QBrush(QColor(theme.TEXT_SECONDARY)))
            self.detail_task_list.addItem(placeholder)
        else:
            for task in tasks_in_project:
                width, height = task.canvas_size
                text = f"{task.name}   ·   {width} x {height}"
                self.detail_task_list.addItem(QListWidgetItem(icons.icon(TASK_ICON, color=theme.ACCENT), text))

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
                item = QListWidgetItem(icons.icon(TASK_ICON, color=theme.ACCENT), f"{task.name}   ·   {width} x {height}")
                item.setData(Qt.ItemDataRole.UserRole, task)
                self.unassigned_list.addItem(item)

    def _on_move_task(self) -> None:
        item = self.unassigned_list.currentItem()
        if item is None or self.project is None:  # pyright: ignore[reportUnnecessaryComparison]
            return
        task = item.data(Qt.ItemDataRole.UserRole)
        if task is None:
            return
        self.viewmodel.move_task_to_project(task.id, self.project.id)
        self._refresh_detail()
        self._refresh_list()

    # -- shared --------------------------------------------------------

    def refresh(self) -> None:
        """Refresh whichever sub-page is currently visible; call when this page becomes active."""
        self._refresh_list()
        if self.project is not None:
            self._refresh_detail()

    def show_list(self) -> None:
        self._refresh_list()
        self._stack.setCurrentWidget(self._list_widget)
