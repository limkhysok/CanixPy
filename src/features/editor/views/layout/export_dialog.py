from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGroupBox,
    QLabel,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from src.core import icons, theme
from src.features.editor.canvas.page import Page
from src.features.editor.exporter import BASELINE_DPI

EXPORT_DIALOG_STYLE = theme.load_qss(Path(__file__).with_name("export_dialog.qss"))

FORMAT_ICON_SIZE = 14

# (export key matching exporter._EXPORTERS, display label, fontawesome icon)
_FORMAT_OPTIONS: list[tuple[str, str, str]] = [
    ("png", "PNG", "fa5s.file-image"),
    ("jpg", "JPG", "fa5s.image"),
    ("pdf", "PDF", "fa5s.file-pdf"),
    ("svg", "SVG", "fa5s.file-code"),
]

# (label, DPI) -- DPI is embedded as file metadata and also drives the pixel
# scale raster exports render at (see exporter.BASELINE_DPI). Standard/72 DPI
# is the default: it matches the canvas's own pixel size exactly (what export
# already produced before this dialog existed), keeping files small and
# predictable for the screen/social-post use this app is mostly aimed at.
# High/Print are opt-in upgrades for anyone who specifically needs a crisper
# or print-ready file.
_QUALITY_OPTIONS: list[tuple[str, int]] = [
    ("Standard — 72 DPI (Web & Social)", 72),
    ("High — 150 DPI", 150),
    ("Print — 300 DPI", 300),
]

# Sentinel returned by selected_page() meaning "every page", never a real Page.
ALL_PAGES = object()


class ExportDialog(QDialog):
    """Export flow: pick a file format, a quality/DPI, and which page(s) to
    export, then Export. Replaces the old Export button's dropdown, which
    listed every file format twice -- once for the active page, once again
    under a separate "Export All Pages" submenu -- with a single dialog where
    picking the page(s) is just one more choice instead of a duplicated menu
    tree. A live "Output" line at the bottom reflects the current
    format/quality/page combination so the resulting file size/dimensions are
    never a surprise after the fact."""

    def __init__(self, pages: list[Page], active_page_index: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Export")
        self.setMinimumWidth(360)
        self.setStyleSheet(EXPORT_DIALOG_STYLE)

        self._pages = pages

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(16)

        # --- Group 1: file format ---
        format_group = QGroupBox("File Format")
        format_layout = QVBoxLayout(format_group)
        self._format_buttons = QButtonGroup(self)
        for key, label, icon_name in _FORMAT_OPTIONS:
            radio = QRadioButton(label)
            radio.setIcon(icons.icon(icon_name, color=theme.TEXT_SECONDARY))
            radio.setIconSize(QSize(FORMAT_ICON_SIZE, FORMAT_ICON_SIZE))
            radio.setProperty("formatKey", key)
            radio.setChecked(key == "png")
            radio.toggled.connect(self._on_format_changed)
            self._format_buttons.addButton(radio)
            format_layout.addWidget(radio)

        self._transparent_check = QCheckBox("Transparent background")
        format_layout.addWidget(self._transparent_check)
        layout.addWidget(format_group)

        # --- Group 2: quality / resolution + DPI ---
        self._quality_group = QGroupBox("Quality")
        quality_layout = QVBoxLayout(self._quality_group)
        self._quality_combo = QComboBox()
        for label, _dpi in _QUALITY_OPTIONS:
            self._quality_combo.addItem(label)
        self._quality_combo.currentIndexChanged.connect(self._update_output_preview)
        quality_layout.addWidget(self._quality_combo)
        layout.addWidget(self._quality_group)

        # --- Group 3: which page(s) to export ---
        pages_group = QGroupBox("Pages")
        pages_layout = QVBoxLayout(pages_group)
        self._page_buttons = QButtonGroup(self)

        all_pages_radio = QRadioButton("All Pages")
        all_pages_radio.setProperty("pageIndex", -1)
        all_pages_radio.toggled.connect(self._update_output_preview)
        self._page_buttons.addButton(all_pages_radio)
        pages_layout.addWidget(all_pages_radio)

        for index, page in enumerate(pages):
            name = page.name or f"Page {index + 1}"
            radio = QRadioButton(f"{name} (current)" if index == active_page_index else name)
            radio.setProperty("pageIndex", index)
            radio.setChecked(index == active_page_index)
            radio.toggled.connect(self._update_output_preview)
            self._page_buttons.addButton(radio)
            pages_layout.addWidget(radio)

        layout.addWidget(pages_group)

        self._output_label = QLabel()
        self._output_label.setObjectName("outputPreview")
        self._output_label.setWordWrap(True)
        layout.addWidget(self._output_label)

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(divider)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        assert ok_button is not None
        ok_button.setText("Export")
        ok_button.setProperty("accent", True)
        ok_button.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        assert cancel_button is not None
        cancel_button.setCursor(Qt.CursorShape.PointingHandCursor)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._on_format_changed()

    def _on_format_changed(self) -> None:
        key = self._selected_format_key()
        self._transparent_check.setEnabled(key == "png")
        if key != "png":
            self._transparent_check.setChecked(False)
        # PDF/SVG are vector -- there's no per-pixel resolution to vary.
        self._quality_group.setEnabled(key not in ("pdf", "svg"))
        self._update_output_preview()

    def _selected_format_key(self) -> str:
        button = self._format_buttons.checkedButton()
        assert button is not None
        return button.property("formatKey")

    def _update_output_preview(self) -> None:
        is_vector = self._selected_format_key() in ("pdf", "svg")
        dpi = self.dpi()
        target = self.selected_page()

        if target is ALL_PAGES:
            count = len(self._pages)
            noun = "page" if count == 1 else "pages"
            if is_vector:
                self._output_label.setText(f"Output: {count} {noun}, each at its native vector size")
            else:
                self._output_label.setText(f"Output: {count} {noun}, each scaled to {dpi} DPI")
        else:
            page = target
            assert isinstance(page, Page)
            if is_vector:
                self._output_label.setText(f"Output: {round(page.width)} × {round(page.height)} px (vector)")
            else:
                scale = dpi / BASELINE_DPI
                width, height = round(page.width * scale), round(page.height * scale)
                self._output_label.setText(f"Output: {width} × {height} px at {dpi} DPI")

    def export_key(self) -> str:
        """One of exporter._EXPORTERS's keys."""
        key = self._selected_format_key()
        if key == "png" and self._transparent_check.isChecked():
            return "png_transparent"
        return key

    def dpi(self) -> int:
        return _QUALITY_OPTIONS[self._quality_combo.currentIndex()][1]

    def selected_page(self) -> Page | object:
        """The one Page to export, or the ALL_PAGES sentinel."""
        button = self._page_buttons.checkedButton()
        assert button is not None
        index = button.property("pageIndex")
        if index == -1:
            return ALL_PAGES
        return self._pages[index]
