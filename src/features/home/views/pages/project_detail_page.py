from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import QLabel, QListWidget, QListWidgetItem, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from src.core import icons, theme
from src.features.home.models.models import Project
from src.features.home.viewmodels.home_viewmodel import HomeViewModel

TASK_ICON = "fa5s.file-alt"


class ProjectDetailPage(QWidget):
    """Detail view for a single project: its tasks, plus moving unassigned tasks in."""

    back_requested = Signal()
    tasks_changed = Signal()

    def __init__(self, viewmodel: HomeViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.viewmodel = viewmodel
        self.project: Project | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 32, 40, 32)
        layout.setSpacing(12)

        btn_back = QPushButton(icons.icon("fa5s.arrow-left"), "Back to Projects")
        btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_back.clicked.connect(self.back_requested.emit)
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

    def show_project(self, project: Project) -> None:
        self.project = project
        self.refresh()

    def refresh(self) -> None:
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
        if item is None or self.project is None:
            return
        task = item.data(Qt.ItemDataRole.UserRole)
        if task is None:
            return
        self.viewmodel.move_task_to_project(task.id, self.project.id)
        self.refresh()
        self.tasks_changed.emit()
