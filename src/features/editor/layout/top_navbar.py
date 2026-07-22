from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QAction, QColor
from PySide6.QtWidgets import (
    QComboBox,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QMenu,
    QPushButton,
    QToolButton,
    QWidget,
)

from src.core import icons, theme

if TYPE_CHECKING:
    from src.features.editor.editor_view import CoreDesignApp

TOP_NAVBAR_STYLE = theme.load_qss(Path(__file__).with_name("top_navbar.qss"))

ICON_BUTTON_SIZE = QSize(38, 38)


class TopNavbar(QWidget):
    """Header strip above the canvas: back navigation, page switching, zoom, and export."""

    back_clicked = Signal()

    def __init__(self, main_app: "CoreDesignApp", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.main_app = main_app
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
        self.btn_undo.clicked.connect(main_app.undo)
        self.btn_redo.clicked.connect(main_app.redo)
        self.btn_undo.setEnabled(False)
        self.btn_redo.setEnabled(False)
        undo_redo_layout = QHBoxLayout()
        undo_redo_layout.setSpacing(6)
        undo_redo_layout.addWidget(self.btn_undo)
        undo_redo_layout.addWidget(self.btn_redo)
        layout.addLayout(undo_redo_layout)

        # Kept off the visible toolbar for now, but page-switching logic
        # (rebuild/rename/duplicate/delete/move) still targets this combo,
        # so it stays alive as a hidden child instead of being deleted.
        self.page_selector = QComboBox(self)
        self.page_selector.setEditable(True)
        self.page_selector.setMinimumWidth(130)
        self.page_selector.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.page_selector.setCursor(Qt.CursorShape.PointingHandCursor)
        self.page_selector.currentIndexChanged.connect(main_app.on_page_combo_changed)
        page_selector_line_edit = self.page_selector.lineEdit()
        assert page_selector_line_edit is not None  # guaranteed by setEditable(True) above
        page_selector_line_edit.setToolTip("Type to rename this page")
        page_selector_line_edit.editingFinished.connect(
            lambda: main_app.rename_current_page(self.page_selector.currentText())
        )
        self.page_selector.setVisible(False)

        btn_page_menu = QToolButton(self)
        btn_page_menu.setObjectName("pageMenuButton")
        btn_page_menu.setText("Add Page")
        btn_page_menu.setIcon(icons.icon("fa5s.plus"))
        btn_page_menu.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        btn_page_menu.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_page_menu.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        btn_page_menu.clicked.connect(main_app.add_new_page)

        page_menu = QMenu(btn_page_menu)
        duplicate_action = QAction(icons.icon("fa5s.clone"), "Duplicate Page", page_menu)
        duplicate_action.triggered.connect(main_app.duplicate_current_page)
        delete_action = QAction(icons.icon("fa5s.trash-alt"), "Delete Page", page_menu)
        delete_action.triggered.connect(main_app.delete_current_page)
        move_left_action = QAction(icons.icon("fa5s.arrow-left"), "Move Left", page_menu)
        move_left_action.triggered.connect(lambda: main_app.move_current_page(-1))
        move_right_action = QAction(icons.icon("fa5s.arrow-right"), "Move Right", page_menu)
        move_right_action.triggered.connect(lambda: main_app.move_current_page(1))
        page_menu.addAction(duplicate_action)
        page_menu.addAction(delete_action)
        page_menu.addSeparator()
        page_menu.addAction(move_left_action)
        page_menu.addAction(move_right_action)
        btn_page_menu.setMenu(page_menu)
        btn_page_menu.setVisible(False)

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
            ("PNG", main_app.export_page_to_png),
            ("PNG (Transparent)", main_app.export_page_to_png_transparent),
            ("JPG", main_app.export_page_to_jpg),
            ("PDF", main_app.export_page_to_pdf),
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
