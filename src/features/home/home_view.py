from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget


class HomeView(QWidget):
    """The Home Screen: templates and recent designs."""

    open_editor = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.addStretch()

        title = QLabel("<h1>CanixPy</h1>")
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(title)

        btn_new_design = QPushButton("+ New Design")
        btn_new_design.setFixedWidth(200)
        btn_new_design.clicked.connect(self.open_editor.emit)
        layout.addWidget(btn_new_design, alignment=Qt.AlignmentFlag.AlignHCenter)

        layout.addStretch()
