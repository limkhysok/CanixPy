from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget

from src.core import icons, theme
from src.features.home.canvas_size_dialog import CanvasSizeDialog
from src.features.home.home_viewmodel import HomeViewModel


class HomePage(QWidget):
    """Default landing page: start a new design, or see recently worked-on tasks."""

    open_editor = Signal(int, int)

    def __init__(self, viewmodel: HomeViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.viewmodel = viewmodel

        layout = QVBoxLayout(self)

        title = QLabel("<h1>CanixPy</h1>")
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(title)

        btn_new_design = QPushButton(icons.icon("fa5s.plus", color=theme.TEXT_ON_ACCENT), "New Design")
        btn_new_design.setProperty("accent", True)
        btn_new_design.setFixedWidth(200)
        btn_new_design.clicked.connect(self._on_new_design)
        layout.addWidget(btn_new_design, alignment=Qt.AlignmentFlag.AlignHCenter)

        layout.addSpacing(20)
        layout.addWidget(QLabel("<b>Recent</b>"))

        self.recent_list = QListWidget()
        layout.addWidget(self.recent_list)

        self.refresh()

    def refresh(self) -> None:
        self.recent_list.clear()
        for task in self.viewmodel.recent_tasks():
            width, height = task.canvas_size
            text = f"{task.name}  ({width} x {height})"
            self.recent_list.addItem(QListWidgetItem(icons.icon("fa5s.file-alt"), text))

    def _on_new_design(self) -> None:
        dialog = CanvasSizeDialog(self.viewmodel, self)
        if dialog.exec() == CanvasSizeDialog.DialogCode.Accepted:
            width, height = dialog.selected_size()
            name = f"Untitled Design {len(self.viewmodel.tasks) + 1}"
            self.viewmodel.add_task(name, (width, height))
            self.refresh()
            self.open_editor.emit(width, height)
