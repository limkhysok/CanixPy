from PySide6.QtWidgets import QWidget


class HomeView(QWidget):
    """The Home Screen: templates and recent designs."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
