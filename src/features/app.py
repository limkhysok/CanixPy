from __future__ import annotations

from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QMainWindow, QStackedWidget, QWidget

from src.features.editor import persistence
from src.features.editor.editor_view import CoreDesignApp
from src.features.home.models.models import Task
from src.features.home.views.home_view import HomeView


class App(QMainWindow):
    """Top-level window that switches between the Home and Editor screens."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("CanixPy")
        self.setGeometry(100, 100, 1300, 800)

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.editor_view: CoreDesignApp | None = None

        self.home_view = HomeView()
        self.home_view.open_editor.connect(self.show_editor)
        self.stack.addWidget(self.home_view)

    def show_editor(self, task: Task) -> None:
        if self.editor_view is not None:
            self.stack.removeWidget(self.editor_view)
            self.editor_view.deleteLater()

        self.editor_view = CoreDesignApp(task.canvas_size)
        self.editor_view.back_to_home.connect(lambda: self._on_editor_closed(task))

        if task.content is not None:
            # Reopening a task the user already edited -- restore exactly
            # what they left, instead of re-adding the raw imported image.
            self.editor_view.apply_project_data(task.content)
        elif task.file_path:
            width, height = task.canvas_size
            center = QPointF(width / 2, height / 2)
            self.editor_view.scene.add_image_item(task.file_path, center)

        self.stack.addWidget(self.editor_view)
        self.stack.setCurrentWidget(self.editor_view)

    def _on_editor_closed(self, task: Task) -> None:
        if self.editor_view is not None:
            content = persistence.serialize_project(self.editor_view)
            self.home_view.viewmodel.save_task_content(task.id, content)
            self.home_view.home_page.refresh()
        self.show_home()

    def show_home(self) -> None:
        self.stack.setCurrentWidget(self.home_view)
