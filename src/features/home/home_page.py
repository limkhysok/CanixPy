from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import QLabel, QListWidget, QListWidgetItem, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from src.core import icons, theme
from src.features.home.canvas_size_dialog import CanvasSizeDialog
from src.features.home.home_viewmodel import HomeViewModel

CONTENT_STYLE = f"""
QLabel#pageTitle {{
    font-size: 26px;
    font-weight: 700;
    color: {theme.TEXT_PRIMARY};
}}
QLabel#sectionHeader {{
    font-size: 16px;
    font-weight: 700;
    color: {theme.TEXT_PRIMARY};
}}
QLabel#sectionCount {{
    color: {theme.TEXT_SECONDARY};
    font-size: 13px;
}}
QListWidget {{
    padding: 6px;
}}
QListWidget::item {{
    padding: 12px 10px;
    margin-bottom: 2px;
}}
"""


class HomePage(QWidget):
    """Default landing page: start a new design, or see recently worked-on tasks."""

    open_editor = Signal(int, int)

    def __init__(self, viewmodel: HomeViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.viewmodel = viewmodel
        self.setStyleSheet(CONTENT_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 32, 40, 32)
        layout.setSpacing(12)

        title = QLabel("CanixPy")
        title.setObjectName("pageTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(title)

        btn_new_design = QPushButton(icons.icon("fa5s.plus", color=theme.TEXT_ON_ACCENT), "New Design")
        btn_new_design.setProperty("accent", True)
        btn_new_design.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_new_design.setFixedWidth(200)
        btn_new_design.clicked.connect(self._on_new_design)
        layout.addWidget(btn_new_design, alignment=Qt.AlignmentFlag.AlignHCenter)

        layout.addSpacing(16)

        header_row = QVBoxLayout()
        header_row.setSpacing(2)
        self.section_header = QLabel("Recent")
        self.section_header.setObjectName("sectionHeader")
        header_row.addWidget(self.section_header)
        self.section_count = QLabel()
        self.section_count.setObjectName("sectionCount")
        header_row.addWidget(self.section_count)
        layout.addLayout(header_row)

        self.recent_list = QListWidget()
        self.recent_list.setIconSize(self.recent_list.iconSize() * 1.2)
        self.recent_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.recent_list)

        self.refresh()

    def refresh(self) -> None:
        self.recent_list.clear()
        tasks = self.viewmodel.recent_tasks()

        count = len(tasks)
        self.section_count.setText(f"{count} design{'s' if count != 1 else ''}")

        if not tasks:
            placeholder = QListWidgetItem(
                icons.icon("fa5s.inbox", color=theme.TEXT_SECONDARY),
                "No designs yet — click “New Design” to get started.",
            )
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            placeholder.setForeground(QBrush(QColor(theme.TEXT_SECONDARY)))
            self.recent_list.addItem(placeholder)
            return

        for task in tasks:
            width, height = task.canvas_size
            text = f"{task.name}   ·   {width} x {height}"
            self.recent_list.addItem(QListWidgetItem(icons.icon("fa5s.file-alt", color=theme.ACCENT), text))

    def _on_new_design(self) -> None:
        dialog = CanvasSizeDialog(self.viewmodel, self)
        if dialog.exec() == CanvasSizeDialog.DialogCode.Accepted:
            width, height = dialog.selected_size()
            name = f"Untitled Design {len(self.viewmodel.tasks) + 1}"
            self.viewmodel.add_task(name, (width, height))
            self.refresh()
            self.open_editor.emit(width, height)
