from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QMainWindow, QStackedWidget, QWidget

from src.features.editor.editor_view import CoreDesignApp
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

    def show_editor(self, width: int = 800, height: int = 600, image_path: str = "") -> None:
        if self.editor_view is not None:
            self.stack.removeWidget(self.editor_view)
            self.editor_view.deleteLater()

        self.editor_view = CoreDesignApp((width, height))
        if image_path:
            center = QPointF(width / 2, height / 2)
            self.editor_view.scene.add_image_item(image_path, center)

        self.stack.addWidget(self.editor_view)
        self.stack.setCurrentWidget(self.editor_view)
