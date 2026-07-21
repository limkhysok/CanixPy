from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel, QMenu, QPushButton, QToolButton, QWidget

from src.core import icons, theme

if TYPE_CHECKING:
    from src.features.editor.editor_view import CoreDesignApp

TOP_NAVBAR_STYLE = theme.load_qss(Path(__file__).with_name("top_navbar.qss"))

ICON_BUTTON_SIZE = QSize(32, 32)


class TopNavbar(QWidget):
    """Header strip above the canvas: back navigation, page switching, zoom, and export."""

    back_clicked = Signal()

    def __init__(self, main_app: "CoreDesignApp", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.main_app = main_app
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(TOP_NAVBAR_STYLE)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        btn_back = QPushButton(icons.icon("fa5s.arrow-left", color=theme.TEXT_PRIMARY), "Back")
        btn_back.setObjectName("backButton")
        btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_back.clicked.connect(self.back_clicked.emit)
        layout.addWidget(btn_back)

        layout.addWidget(self._divider())

        btn_save = self._icon_button("fa5s.save", "Save Project (Ctrl+S)")
        btn_open = self._icon_button("fa5s.folder-open", "Open Project (Ctrl+O)")
        btn_save.clicked.connect(main_app.save_project)
        btn_open.clicked.connect(main_app.open_project)
        layout.addWidget(btn_save)
        layout.addWidget(btn_open)

        layout.addWidget(self._divider())

        self.btn_undo = self._icon_button("fa5s.undo", "Undo (Ctrl+Z)")
        self.btn_redo = self._icon_button("fa5s.redo", "Redo (Ctrl+Y)")
        self.btn_undo.clicked.connect(main_app.undo)
        self.btn_redo.clicked.connect(main_app.redo)
        self.btn_undo.setEnabled(False)
        self.btn_redo.setEnabled(False)
        layout.addWidget(self.btn_undo)
        layout.addWidget(self.btn_redo)

        layout.addWidget(self._divider())

        self.page_selector = QComboBox()
        self.page_selector.setEditable(True)
        self.page_selector.setMinimumWidth(130)
        self.page_selector.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.page_selector.setCursor(Qt.CursorShape.PointingHandCursor)
        self.page_selector.currentIndexChanged.connect(main_app.on_page_combo_changed)
        self.page_selector.lineEdit().setToolTip("Type to rename this page")
        self.page_selector.lineEdit().editingFinished.connect(
            lambda: main_app.rename_current_page(self.page_selector.currentText())
        )

        # Split button: clicking the main face adds a page; the arrow opens
        # the less-common page operations, keeping the toolbar from needing
        # one button per action.
        btn_page_menu = QToolButton()
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

        pages_label = QLabel("Pages:")
        pages_label.setObjectName("navLabel")
        layout.addWidget(pages_label)
        layout.addWidget(self.page_selector)
        layout.addWidget(btn_page_menu)

        layout.addWidget(self._divider())

        btn_zoom_out = self._icon_button("fa5s.search-minus", "Zoom Out")
        btn_zoom_in = self._icon_button("fa5s.search-plus", "Zoom In")
        btn_zoom_reset = self._icon_button("fa5s.compress-arrows-alt", "Reset Zoom")
        btn_zoom_out.clicked.connect(main_app.zoom_out)
        btn_zoom_in.clicked.connect(main_app.zoom_in)
        btn_zoom_reset.clicked.connect(main_app.zoom_reset)
        layout.addWidget(btn_zoom_out)
        layout.addWidget(btn_zoom_in)
        layout.addWidget(btn_zoom_reset)

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

        layout.addWidget(btn_export)

    def _icon_button(self, icon_name: str, tooltip: str) -> QPushButton:
        btn = QPushButton(icons.icon(icon_name), "")
        btn.setObjectName("iconButton")
        btn.setToolTip(tooltip)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedSize(ICON_BUTTON_SIZE)
        return btn

    def _divider(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.VLine)
        line.setFrameShadow(QFrame.Shadow.Plain)
        line.setStyleSheet(f"color: {theme.BORDER};")
        return line

    def set_history_enabled(self, can_undo: bool, can_redo: bool) -> None:
        self.btn_undo.setEnabled(can_undo)
        self.btn_redo.setEnabled(can_redo)
