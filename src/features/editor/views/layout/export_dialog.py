from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialogButtonBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from src.core import icons, theme
from src.core.frameless_dialog import DialogTitleBar, FramelessCardDialog
from src.features.editor.canvas.page import Page
from src.features.editor.exporter import BASELINE_DPI

EXPORT_DIALOG_STYLE = theme.load_qss(Path(__file__).with_name("export_dialog.qss"))

FORMAT_ICON_SIZE = 14
HEADER_ICON_SIZE = 26
CLOSE_BUTTON_SIZE = 28

# (export key matching exporter._EXPORTERS, display label, fontawesome icon)
_FORMAT_OPTIONS: list[tuple[str, str, str]] = [
    ("png", "PNG", "fa5s.file-image"),
    ("jpg", "JPG", "fa5s.image"),
    ("pdf", "PDF", "fa5s.file-pdf"),
    ("svg", "SVG", "fa5s.file-code"),
]

# (label, DPI) -- DPI is embedded as file metadata and also drives the pixel
# scale raster exports render at: scale = dpi / exporter.BASELINE_DPI, chosen
# so each tier is an exact 1x/2x/3x multiple. DPI itself is print vocabulary
# that doesn't mean much for a canvas with no defined physical size, so it's
# kept out of the *label* (shown as a plain scale multiplier instead, the way
# Figma/Canva phrase this) even though it's still embedded in the file for
# any print software that does read it. Standard/1x is the default: it
# matches the canvas's own pixel size exactly (what export already produced
# before this dialog existed), keeping files small and predictable for the
# screen/social-post use this app is mostly aimed at -- the higher tiers are
# opt-in upgrades for anyone who specifically needs a crisper file.
_QUALITY_OPTIONS: list[tuple[str, int]] = [
    ("Standard (1x)", 72),
    ("High Quality (2x)", 144),
    ("High-Res (3x)", 216),
]


class ExportDialog(FramelessCardDialog):
    """Export flow: pick a file format, a quality/DPI, and which page(s) to
    export, then Export. Replaces the old Export button's dropdown, which
    listed every file format twice -- once for the active page, once again
    under a separate "Export All Pages" submenu -- with a single dialog where
    picking the page(s) is just one more choice instead of a duplicated menu
    tree. Pages are checkboxes (plus a "select all" master), not exclusive
    radios, so exporting an arbitrary subset -- e.g. just pages 1 and 3 --
    doesn't require two separate export runs. A live "Output" line at the
    bottom reflects the current format/quality/page combination so the
    resulting file size/dimensions are never a surprise after the fact.

    Frameless/blurred-backdrop chrome shared with CanvasSizeDialog via
    FramelessCardDialog -- see src/core/frameless_dialog.py."""

    def __init__(self, pages: list[Page], active_page_index: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Export")
        self.setMinimumWidth(400)
        self.setStyleSheet(EXPORT_DIALOG_STYLE)

        self._pages = pages

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 20, 28, 20)
        layout.setSpacing(16)

        # --- Header: icon + title/subtitle + close button, no native title bar ---
        title_bar = DialogTitleBar()
        header = QHBoxLayout(title_bar)
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(14)
        header_icon = QLabel()
        header_icon.setPixmap(
            icons.icon("fa5s.file-export", color=theme.ACCENT).pixmap(HEADER_ICON_SIZE, HEADER_ICON_SIZE)
        )
        header.addWidget(header_icon)
        header_text = QVBoxLayout()
        header_text.setSpacing(2)
        title = QLabel("Export Design")
        title.setObjectName("dialogTitle")
        header_text.addWidget(title)
        subtitle = QLabel("Choose a format, quality, and which pages to include")
        subtitle.setObjectName("dialogSubtitle")
        header_text.addWidget(subtitle)
        header.addLayout(header_text, 1)

        close_button = QPushButton(icons.icon("fa5s.times", color=theme.TEXT_SECONDARY), "")
        close_button.setObjectName("closeButton")
        close_button.setFixedSize(CLOSE_BUTTON_SIZE, CLOSE_BUTTON_SIZE)
        close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        close_button.setToolTip("Close")
        close_button.clicked.connect(self.reject)
        header.addWidget(close_button, alignment=Qt.AlignmentFlag.AlignTop)

        layout.addWidget(title_bar)

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

        self._select_all_check = QCheckBox("All Pages")
        self._select_all_check.toggled.connect(self._on_select_all_toggled)
        pages_layout.addWidget(self._select_all_check)

        pages_divider = QFrame()
        pages_divider.setFrameShape(QFrame.Shape.HLine)
        pages_layout.addWidget(pages_divider)

        self._page_checks: list[QCheckBox] = []
        for index, page in enumerate(pages):
            name = page.name or f"Page {index + 1}"
            check = QCheckBox(f"{name} (current)" if index == active_page_index else name)
            check.setChecked(index == active_page_index)
            check.toggled.connect(self._on_page_check_toggled)
            self._page_checks.append(check)
            pages_layout.addWidget(check)

        layout.addWidget(pages_group)

        self._output_label = QLabel()
        self._output_label.setObjectName("outputPreview")
        self._output_label.setWordWrap(True)
        layout.addWidget(self._output_label)

        divider = QFrame()
        divider.setObjectName("footerDivider")
        divider.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(divider)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self._export_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        assert self._export_button is not None
        self._export_button.setText("Export")
        self._export_button.setProperty("accent", True)
        self._export_button.setCursor(Qt.CursorShape.PointingHandCursor)
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

    def _on_select_all_toggled(self, checked: bool) -> None:
        """Master checkbox: bulk-sets every page checkbox. Signals are
        blocked during the bulk set so _on_page_check_toggled doesn't fire
        len(pages) times and fight back over this checkbox's own state."""
        for check in self._page_checks:
            check.blockSignals(True)
            check.setChecked(checked)
            check.blockSignals(False)
        self._sync_export_enabled()
        self._update_output_preview()

    def _on_page_check_toggled(self) -> None:
        all_checked = all(check.isChecked() for check in self._page_checks)
        self._select_all_check.blockSignals(True)
        self._select_all_check.setChecked(all_checked)
        self._select_all_check.blockSignals(False)
        self._sync_export_enabled()
        self._update_output_preview()

    def _sync_export_enabled(self) -> None:
        # Exporting nothing isn't a valid action -- disable rather than
        # silently no-op if every page checkbox gets unchecked.
        self._export_button.setEnabled(any(check.isChecked() for check in self._page_checks))

    def _update_output_preview(self) -> None:
        is_vector = self._selected_format_key() in ("pdf", "svg")
        dpi = self.dpi()
        selected = self.selected_pages()

        scale_label = f"{round(dpi / BASELINE_DPI)}x"

        if not selected:
            self._output_label.setText("Select at least one page to export")
        elif len(selected) == 1:
            page = selected[0]
            if is_vector:
                self._output_label.setText(f"Output: {round(page.width)} × {round(page.height)} px (vector)")
            else:
                scale = dpi / BASELINE_DPI
                width, height = round(page.width * scale), round(page.height * scale)
                self._output_label.setText(f"Output: {width} × {height} px ({scale_label})")
        else:
            count = len(selected)
            if is_vector:
                self._output_label.setText(f"Output: {count} pages, each at its native vector size")
            else:
                self._output_label.setText(f"Output: {count} pages, each at {scale_label}")

    def export_key(self) -> str:
        """One of exporter._EXPORTERS's keys."""
        key = self._selected_format_key()
        if key == "png" and self._transparent_check.isChecked():
            return "png_transparent"
        return key

    def dpi(self) -> int:
        return _QUALITY_OPTIONS[self._quality_combo.currentIndex()][1]

    def selected_pages(self) -> list[Page]:
        """Checked pages, in document order. Never includes a page whose
        checkbox is unchecked, so this can be empty (see _sync_export_enabled,
        which disables Export for that case)."""
        return [page for page, check in zip(self._pages, self._page_checks) if check.isChecked()]
