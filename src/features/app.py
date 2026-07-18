from PySide6.QtWidgets import QMainWindow, QStackedWidget, QWidget

from src.features.editor.editor_view import CoreDesignApp
from src.features.home.home_view import HomeView


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

    def show_editor(self) -> None:
        if self.editor_view is None:
            self.editor_view = CoreDesignApp()
            self.stack.addWidget(self.editor_view)
        self.stack.setCurrentWidget(self.editor_view)
