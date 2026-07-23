from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QAction, QColor
from PySide6.QtWidgets import (
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QMenu,
    QPushButton,
    QToolButton,
    QWidget,
)

from src.core import icons, theme

TOP_NAVBAR_STYLE = theme.load_qss(Path(__file__).with_name("top_navbar.qss"))

ICON_BUTTON_SIZE = QSize(38, 38)


class TopNavbar(QWidget):
    """Header strip above the canvas: back navigation, undo/redo, and export.
    Per-page controls (name/rename/duplicate/delete/move, Add Page) float
    directly over the canvas instead -- see layout/page_overlay.py. Doesn't
    know about EditorView -- every button just emits a signal; EditorView
    (the composition root) wires each one to the actual action."""

    back_clicked = Signal()
    undo_clicked = Signal()
    redo_clicked = Signal()
    export_png_clicked = Signal()
    export_png_transparent_clicked = Signal()
    export_jpg_clicked = Signal()
    export_pdf_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(TOP_NAVBAR_STYLE)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(14)

        btn_back = QPushButton(icons.icon("fa5s.arrow-left", color=theme.TEXT_ON_ACCENT), "Back")
        btn_back.setObjectName("backButton")
        btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_back.clicked.connect(self.back_clicked.emit)
        layout.addWidget(btn_back)

        self.btn_undo = self._icon_button("fa5s.undo", "Undo (Ctrl+Z)")
        self.btn_redo = self._icon_button("fa5s.redo", "Redo (Ctrl+Y)")
        self.btn_undo.clicked.connect(self.undo_clicked.emit)
        self.btn_redo.clicked.connect(self.redo_clicked.emit)
        self.btn_undo.setEnabled(False)
        self.btn_redo.setEnabled(False)
        undo_redo_layout = QHBoxLayout()
        undo_redo_layout.setSpacing(6)
        undo_redo_layout.addWidget(self.btn_undo)
        undo_redo_layout.addWidget(self.btn_redo)
        layout.addLayout(undo_redo_layout)
        layout.addStretch()

        btn_export = QToolButton()
        btn_export.setObjectName("exportButton")
        btn_export.setText("Export")
        btn_export.setIcon(icons.icon("fa5s.file-export", color=theme.TEXT_ON_ACCENT))
        btn_export.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        btn_export.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_export.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)

        export_menu = QMenu(btn_export)
        export_actions = (
            ("PNG", self.export_png_clicked.emit),
            ("PNG (Transparent)", self.export_png_transparent_clicked.emit),
            ("JPG", self.export_jpg_clicked.emit),
            ("PDF", self.export_pdf_clicked.emit),
        )
        for label, handler in export_actions:
            action = QAction(label, export_menu)
            action.triggered.connect(handler)
            export_menu.addAction(action)
        btn_export.setMenu(export_menu)

        export_shadow = QGraphicsDropShadowEffect(btn_export)
        export_shadow.setBlurRadius(16)
        export_shadow.setOffset(0, 3)
        export_shadow.setColor(QColor(0, 0, 0, 70))
        btn_export.setGraphicsEffect(export_shadow)

        layout.addWidget(btn_export)

    def _icon_button(self, icon_name: str, tooltip: str) -> QPushButton:
        btn = QPushButton(icons.icon(icon_name, color=theme.TEXT_ON_ACCENT), "")
        btn.setObjectName("iconButton")
        btn.setToolTip(tooltip)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedSize(ICON_BUTTON_SIZE)
        btn.setIconSize(QSize(20, 20))
        return btn

    def set_history_enabled(self, can_undo: bool, can_redo: bool) -> None:
        self.btn_undo.setEnabled(can_undo)
        self.btn_redo.setEnabled(can_redo)
