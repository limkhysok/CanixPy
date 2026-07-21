from __future__ import annotations

from functools import partial
from math import gcd
from typing import Callable

from PySide6.QtCore import QEvent, QObject, QPoint, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
    QPixmap,
    QShowEvent,
)
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGraphicsBlurEffect,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from src.core import icons, theme
from src.features.home.viewmodels.home_viewmodel import CanvasPreset, HomeViewModel

CATEGORY_ICONS: dict[str, str] = {
    "Popular": "fa5s.fire",
    "Facebook": "fa5b.facebook-f",
    "Instagram": "fa5b.instagram",
    "LinkedIn": "fa5b.linkedin-in",
    "Pinterest": "fa5b.pinterest-p",
    "TikTok": "fa5b.tiktok",
    "Twitter": "fa5b.twitter",
    "YouTube": "fa5b.youtube",
}

DIALOG_CORNER_RADIUS = 16

DIALOG_STYLE = f"""
QLabel {{
    background-color: transparent;
}}
QLabel#dialogTitle {{
    font-size: 22px;
    font-weight: 600;
    color: {theme.TEXT_PRIMARY};
}}
QLabel#dialogSubtitle {{
    font-size: 13px;
    color: {theme.TEXT_SECONDARY};
}}
QLabel#sectionLabel {{
    font-size: 12px;
    font-weight: 600;
    color: {theme.TEXT_SECONDARY};
}}
QLabel#hintLabel {{
    font-size: 11px;
    color: {theme.TEXT_SECONDARY};
}}
QScrollArea#categoryScroll, QScrollArea#presetScroll {{
    background-color: transparent;
    border: none;
}}
QScrollArea#categoryScroll QWidget#qt_scrollarea_viewport, QScrollArea#presetScroll QWidget#qt_scrollarea_viewport {{
    background-color: transparent;
}}
QPushButton#categoryChip {{
    background-color: {theme.BACKGROUND};
    border: 1px solid {theme.BORDER};
    border-radius: 15px;
    padding: 6px 14px;
    font-size: 12px;
    font-weight: 500;
    color: {theme.TEXT_PRIMARY};
}}
QPushButton#categoryChip:hover {{
    background-color: {theme.ACCENT_LIGHT};
    border-color: {theme.ACCENT};
}}
QPushButton#categoryChip:checked {{
    background-color: {theme.ACCENT};
    border-color: {theme.ACCENT};
    color: {theme.TEXT_ON_ACCENT};
}}
QWidget#presetCard {{
    background-color: {theme.BACKGROUND};
    border: 1px solid {theme.BORDER};
    border-radius: 10px;
}}
QWidget#presetCard:hover {{
    background-color: {theme.ACCENT_LIGHT};
    border-color: {theme.ACCENT};
}}
QWidget#presetCard:focus {{
    border: 1px solid {theme.ACCENT};
    outline: none;
}}
QWidget#presetCard[selected="true"] {{
    background-color: {theme.ACCENT_LIGHT};
    border: 2px solid {theme.ACCENT};
    outline: none;
}}
QWidget#presetIconBox {{
    background-color: {theme.ACCENT_LIGHT};
    border-radius: 12px;
}}
QWidget#presetCard[selected="true"] QWidget#presetIconBox {{
    background-color: {theme.ACCENT};
}}
QLabel#presetSwatch {{
    background-color: {theme.ACCENT};
    border-radius: 3px;
}}
QWidget#presetCard[selected="true"] QLabel#presetSwatch {{
    background-color: {theme.TEXT_ON_ACCENT};
}}
QLabel#presetName {{
    font-size: 14px;
    font-weight: 600;
    color: {theme.TEXT_PRIMARY};
}}
QLabel#presetDims {{
    font-size: 12px;
    color: {theme.TEXT_SECONDARY};
}}
QWidget#customSizeSection {{
    background-color: {theme.BACKGROUND};
    border: 1px solid {theme.BORDER};
    border-radius: 10px;
}}
QWidget#customSizeSection[active="true"] {{
    border: 2px solid {theme.ACCENT};
}}
QWidget#customSizeSection QLabel#fieldLabel {{
    font-size: 11px;
    color: {theme.TEXT_SECONDARY};
}}
QWidget#spinField {{
    background-color: {theme.BACKGROUND};
    border: 1px solid {theme.BORDER};
    border-radius: 8px;
}}
QWidget#spinField[focused="true"] {{
    border: 1px solid {theme.ACCENT};
}}
QSpinBox#spinFieldInput {{
    background-color: transparent;
    border: none;
    font-size: 14px;
    padding: 6px 0px;
}}
QSpinBox#spinFieldInput:focus {{
    outline: none;
}}
QToolButton#spinStepButton {{
    background-color: transparent;
    border: none;
    border-radius: 3px;
    padding: 0px;
}}
QToolButton#spinStepButton:hover {{
    background-color: {theme.ACCENT_LIGHT};
}}
QToolButton#spinStepButton:pressed {{
    background-color: {theme.ACCENT};
}}
QLabel#customSizeSeparator {{
    color: {theme.TEXT_SECONDARY};
    font-weight: 600;
    font-size: 16px;
}}
QWidget#customPreviewBox {{
    background-color: {theme.SURFACE};
    border: 1px solid {theme.BORDER};
    border-radius: 10px;
}}
QLabel#customPreviewSwatch {{
    background-color: {theme.ACCENT};
    border-radius: 3px;
}}
QPushButton#swapButton {{
    background-color: {theme.BACKGROUND};
    border: 1px solid {theme.BORDER};
    border-radius: 6px;
    padding: 0px;
    min-height: 0px;
}}
QPushButton#swapButton:hover {{
    background-color: {theme.ACCENT_LIGHT};
    border-color: {theme.ACCENT};
}}
QPushButton#swapButton:pressed {{
    background-color: {theme.ACCENT_LIGHT};
}}
QFrame#footerDivider {{
    background-color: {theme.BORDER};
    max-height: 1px;
    border: none;
}}
QPushButton#closeButton {{
    background-color: transparent;
    border: none;
    border-radius: 6px;
    padding: 0px;
    min-height: 0px;
}}
QPushButton#closeButton:hover {{
    background-color: {theme.BORDER};
}}
QPushButton#closeButton:pressed {{
    background-color: {theme.ACCENT_LIGHT};
}}
QDialogButtonBox QPushButton {{
    min-height: 22px;
    padding: 8px 18px;
    font-weight: 500;
}}
"""

PRESET_SWATCH_MAX = 22
PRESET_SWATCH_MIN = 8
PRESET_ICON_BOX = 44
PRESET_GRID_COLUMNS = 2
PRESET_CARD_MIN_HEIGHT = 100
BACKDROP_BLUR_RADIUS = 3
BACKDROP_BLUR_DOWNSCALE = 1
BACKDROP_TINT_COLOR = "#1A1613"
BACKDROP_TINT_ALPHA = 35


def _swatch_size(width: int, height: int) -> tuple[int, int]:
    """Scale a preset's aspect ratio down to a small visual swatch."""
    if width >= height:
        swatch_width = PRESET_SWATCH_MAX
        swatch_height = max(PRESET_SWATCH_MIN, round(PRESET_SWATCH_MAX * height / width))
    else:
        swatch_height = PRESET_SWATCH_MAX
        swatch_width = max(PRESET_SWATCH_MIN, round(PRESET_SWATCH_MAX * width / height))
    return swatch_width, swatch_height


def _aspect_ratio_text(width: int, height: int) -> str:
    """Simplify a width/height pair to a readable ratio, e.g. '16:9'."""
    divisor = gcd(width, height)
    ratio_width, ratio_height = width // divisor, height // divisor
    if max(ratio_width, ratio_height) <= 64:
        return f"{ratio_width}:{ratio_height}"
    return f"{width / height:.2f}:1"


def _blur_pixmap(pixmap: QPixmap, radius: float, downscale: int = 1) -> QPixmap:
    """Gaussian-blur a pixmap via QGraphicsBlurEffect. Downscaling first is a
    standard trick to keep a full-window blur fast -- the softness this loses
    is invisible once blurred anyway."""
    if pixmap.isNull():
        return pixmap

    source = pixmap
    if downscale > 1:
        source = pixmap.scaled(
            max(1, pixmap.width() // downscale),
            max(1, pixmap.height() // downscale),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    scene = QGraphicsScene()
    item = QGraphicsPixmapItem(source)
    effect = QGraphicsBlurEffect()
    effect.setBlurRadius(radius)
    item.setGraphicsEffect(effect)
    scene.addItem(item)

    blurred = QPixmap(source.size())
    blurred.fill(Qt.GlobalColor.transparent)
    painter = QPainter(blurred)
    scene.render(painter, QRectF(blurred.rect()), QRectF(source.rect()))
    painter.end()

    if downscale > 1:
        blurred = blurred.scaled(
            pixmap.size(),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    return blurred


class _BlurBackdrop(QWidget):
    """A blurred snapshot of the window behind the dialog, covering its
    client area as a child overlay while the dialog is open. Stacking this
    as a *separate top-level window* turned out to be unreliable -- Windows
    doesn't consistently place a newly created window above an
    already-focused one, even after raise_()/activateWindow(). Child-widget
    stacking within the same top-level window is Qt-managed and reliable,
    and the modal dialog itself (a real top-level window) already reliably
    renders above its parent regardless."""

    def __init__(self, source_window: QWidget) -> None:
        super().__init__(source_window)
        self.setGeometry(0, 0, source_window.width(), source_window.height())

        blurred = _blur_pixmap(source_window.grab(), BACKDROP_BLUR_RADIUS, BACKDROP_BLUR_DOWNSCALE)
        # The app's theme is almost entirely white/pale, so a light tint over
        # a blurred snapshot of it washes out to a flat white void -- a dark
        # dimming tint keeps the blurred shapes visible and gives the white
        # dialog card something to visually stand out against.
        tint = QColor(BACKDROP_TINT_COLOR)
        tint.setAlpha(BACKDROP_TINT_ALPHA)
        painter = QPainter(blurred)
        painter.fillRect(blurred.rect(), tint)
        painter.end()

        label = QLabel(self)
        label.setGeometry(0, 0, self.width(), self.height())
        label.setPixmap(blurred)
        label.setScaledContents(True)


class _SpinField(QWidget):
    """A numeric field with slim custom chevron steppers instead of the native
    QSpinBox's cramped, dated-looking up/down buttons."""

    valueChanged = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("spinField")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setProperty("focused", False)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 4, 0)
        layout.setSpacing(2)

        self.spin = QSpinBox()
        self.spin.setObjectName("spinFieldInput")
        self.spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.spin.setFrame(False)
        self.spin.installEventFilter(self)
        self.spin.valueChanged.connect(self.valueChanged)
        layout.addWidget(self.spin, 1)

        steppers = QVBoxLayout()
        steppers.setContentsMargins(0, 0, 0, 0)
        steppers.setSpacing(1)
        self._up_button = self._make_stepper("fa5s.chevron-up", self.spin.stepUp)
        self._down_button = self._make_stepper("fa5s.chevron-down", self.spin.stepDown)
        steppers.addWidget(self._up_button)
        steppers.addWidget(self._down_button)
        layout.addLayout(steppers)

    def _make_stepper(self, icon_name: str, step: Callable[[], None]) -> QToolButton:
        button = QToolButton()
        button.setObjectName("spinStepButton")
        button.setIcon(icons.icon(icon_name, color=theme.TEXT_SECONDARY))
        button.setIconSize(QSize(8, 8))
        button.setFixedSize(18, 13)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setAutoRepeat(True)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.clicked.connect(step)
        return button

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self.spin:
            if event.type() == QEvent.Type.FocusIn:
                self._set_focused(True)
            elif event.type() == QEvent.Type.FocusOut:
                self._set_focused(False)
        return super().eventFilter(watched, event)

    def _set_focused(self, focused: bool) -> None:
        self.setProperty("focused", focused)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def setRange(self, minimum: int, maximum: int) -> None:
        self.spin.setRange(minimum, maximum)

    def setSuffix(self, suffix: str) -> None:
        self.spin.setSuffix(suffix)

    def setValue(self, value: int) -> None:
        self.spin.setValue(value)

    def value(self) -> int:
        return self.spin.value()

    def blockSignals(self, block: bool) -> bool:
        self.spin.blockSignals(block)
        return super().blockSignals(block)


class _PresetCard(QWidget):
    """A large, keyboard-accessible card showing a preset's name, size, and aspect-ratio swatch."""

    clicked = Signal()

    def __init__(self, preset: CanvasPreset, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.preset = preset
        self.setObjectName("presetCard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setProperty("selected", False)
        self.setMinimumHeight(PRESET_CARD_MIN_HEIGHT)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setToolTip(f"{preset.name} — {preset.width} x {preset.height} px")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 12)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        icon_box = QWidget()
        icon_box.setObjectName("presetIconBox")
        icon_box.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        icon_box.setFixedSize(PRESET_ICON_BOX, PRESET_ICON_BOX)
        icon_box_layout = QVBoxLayout(icon_box)
        icon_box_layout.setContentsMargins(0, 0, 0, 0)
        icon_box_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        swatch_width, swatch_height = _swatch_size(preset.width, preset.height)
        swatch = QLabel()
        swatch.setObjectName("presetSwatch")
        swatch.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        swatch.setFixedSize(swatch_width, swatch_height)
        icon_box_layout.addWidget(swatch)
        layout.addWidget(icon_box, alignment=Qt.AlignmentFlag.AlignHCenter)

        name_label = QLabel(preset.name)
        name_label.setObjectName("presetName")
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setWordWrap(True)
        layout.addWidget(name_label)

        dims_label = QLabel(f"{preset.width} x {preset.height} px")
        dims_label.setObjectName("presetDims")
        dims_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(dims_label)

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            self.clicked.emit()
        super().mousePressEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.clicked.emit()
            return
        super().keyPressEvent(event)


class _DialogTitleBar(QWidget):
    """Custom replacement for the OS title bar: drag-to-move plus a close button,
    since the dialog runs frameless (no native toolbar/title bar)."""

    close_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._drag_offset: QPoint | None = None

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.window().pos()
            event.accept()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.window().move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_offset = None
        super().mouseReleaseEvent(event)


class CanvasSizeDialog(QDialog):
    """Lets the user pick a preset canvas size or enter a custom one before opening the editor."""

    def __init__(self, viewmodel: HomeViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Design")
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setMinimumWidth(920)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setStyleSheet(DIALOG_STYLE)

        self.viewmodel = viewmodel
        self._selected_size = (800, 600)
        self._preset_cards: list[_PresetCard] = []

        self._backdrop: _BlurBackdrop | None = None
        if parent is not None:
            self._backdrop = _BlurBackdrop(parent.window())
            self.finished.connect(self._backdrop.close)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 20, 28, 20)
        layout.setSpacing(14)

        title_bar = _DialogTitleBar()
        header = QHBoxLayout(title_bar)
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(14)
        header_icon = QLabel()
        header_icon.setPixmap(icons.icon("fa5s.magic", color=theme.ACCENT).pixmap(26, 26))
        header.addWidget(header_icon)
        header_text = QVBoxLayout()
        header_text.setSpacing(2)
        title = QLabel("Create a new design")
        title.setObjectName("dialogTitle")
        header_text.addWidget(title)
        subtitle = QLabel("Choose a template size, or set your own custom dimensions")
        subtitle.setObjectName("dialogSubtitle")
        header_text.addWidget(subtitle)
        header.addLayout(header_text, 1)

        close_button = QPushButton(icons.icon("fa5s.times", color=theme.TEXT_SECONDARY), "")
        close_button.setObjectName("closeButton")
        close_button.setFixedSize(28, 28)
        close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        close_button.setToolTip("Close")
        close_button.clicked.connect(self.reject)
        header.addWidget(close_button, alignment=Qt.AlignmentFlag.AlignTop)

        layout.addWidget(title_bar)

        templates_label = QLabel("TEMPLATES")
        templates_label.setObjectName("sectionLabel")
        layout.addWidget(templates_label)

        self.category_scroll = QScrollArea()
        self.category_scroll.setObjectName("categoryScroll")
        self.category_scroll.setWidgetResizable(True)
        self.category_scroll.setFixedHeight(44)
        self.category_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.category_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.category_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        category_content = QWidget()
        category_row = QHBoxLayout(category_content)
        category_row.setContentsMargins(2, 2, 2, 2)
        category_row.setSpacing(8)
        self._category_group = QButtonGroup(self)
        self._category_group.setExclusive(True)
        categories = self.viewmodel.list_categories()
        for index, category in enumerate(categories):
            chip = QPushButton(
                icons.icon(CATEGORY_ICONS[category], color=theme.TEXT_SECONDARY, color_on=theme.TEXT_ON_ACCENT),
                category,
            )
            chip.setObjectName("categoryChip")
            chip.setCheckable(True)
            chip.setChecked(index == 0)
            chip.setCursor(Qt.CursorShape.PointingHandCursor)
            chip.clicked.connect(partial(self._on_category_clicked, category))
            self._category_group.addButton(chip)
            category_row.addWidget(chip)
        category_row.addStretch(1)
        self.category_scroll.setWidget(category_content)
        layout.addWidget(self.category_scroll)

        self.preset_scroll = QScrollArea()
        self.preset_scroll.setObjectName("presetScroll")
        self.preset_scroll.setWidgetResizable(True)
        self.preset_scroll.setFixedHeight(420)
        self.preset_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.preset_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.preset_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        preset_container = QWidget()
        self.preset_grid = QGridLayout(preset_container)
        self.preset_grid.setSpacing(10)
        self.preset_grid.setContentsMargins(2, 2, 10, 2)
        for column in range(PRESET_GRID_COLUMNS):
            self.preset_grid.setColumnStretch(column, 1)
        self.preset_scroll.setWidget(preset_container)
        layout.addWidget(self.preset_scroll)

        self.custom_section = QWidget()
        self.custom_section.setObjectName("customSizeSection")
        self.custom_section.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.custom_section.setProperty("active", False)
        custom_layout = QVBoxLayout(self.custom_section)
        custom_layout.setContentsMargins(14, 12, 14, 12)
        custom_layout.setSpacing(6)

        custom_label = QLabel("CUSTOM SIZE")
        custom_label.setObjectName("sectionLabel")
        custom_layout.addWidget(custom_label)

        content_row = QHBoxLayout()
        content_row.setSpacing(14)

        self.custom_preview_box = QWidget()
        self.custom_preview_box.setObjectName("customPreviewBox")
        self.custom_preview_box.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.custom_preview_box.setFixedSize(PRESET_ICON_BOX, PRESET_ICON_BOX)
        preview_box_layout = QVBoxLayout(self.custom_preview_box)
        preview_box_layout.setContentsMargins(0, 0, 0, 0)
        preview_box_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.custom_preview_swatch = QLabel()
        self.custom_preview_swatch.setObjectName("customPreviewSwatch")
        self.custom_preview_swatch.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        preview_box_layout.addWidget(self.custom_preview_swatch)
        content_row.addWidget(self.custom_preview_box)

        custom_grid = QGridLayout()
        custom_grid.setHorizontalSpacing(10)
        custom_grid.setVerticalSpacing(4)

        width_field_label = QLabel("Width")
        width_field_label.setObjectName("fieldLabel")
        height_field_label = QLabel("Height")
        height_field_label.setObjectName("fieldLabel")
        custom_grid.addWidget(width_field_label, 0, 0)
        custom_grid.addWidget(height_field_label, 0, 2)

        self.width_box = _SpinField()
        self.width_box.setRange(1, 10000)
        self.width_box.setSuffix(" px")
        self.width_box.setFixedWidth(128)
        self.width_box.valueChanged.connect(self._on_custom_changed)

        self.height_box = _SpinField()
        self.height_box.setRange(1, 10000)
        self.height_box.setSuffix(" px")
        self.height_box.setFixedWidth(128)
        self.height_box.valueChanged.connect(self._on_custom_changed)

        separator = QLabel("×")
        separator.setObjectName("customSizeSeparator")
        separator.setAlignment(Qt.AlignmentFlag.AlignCenter)

        custom_grid.addWidget(self.width_box, 1, 0)
        custom_grid.addWidget(separator, 1, 1)
        custom_grid.addWidget(self.height_box, 1, 2)
        content_row.addLayout(custom_grid)

        swap_button = QPushButton(icons.icon("fa5s.exchange-alt", color=theme.TEXT_SECONDARY), "")
        swap_button.setObjectName("swapButton")
        swap_button.setFixedSize(34, 34)
        swap_button.setCursor(Qt.CursorShape.PointingHandCursor)
        swap_button.setToolTip("Swap width and height")
        swap_button.clicked.connect(self._on_swap_clicked)
        content_row.addWidget(swap_button, alignment=Qt.AlignmentFlag.AlignBottom)
        content_row.addStretch(1)
        custom_layout.addLayout(content_row)

        self.hint_label = QLabel()
        self.hint_label.setObjectName("hintLabel")
        custom_layout.addWidget(self.hint_label)

        layout.addWidget(self.custom_section)

        divider = QFrame()
        divider.setObjectName("footerDivider")
        divider.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(divider)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        assert ok_button is not None
        ok_button.setText("Create Design")
        ok_button.setProperty("accent", True)
        ok_button.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        assert cancel_button is not None
        cancel_button.setCursor(Qt.CursorShape.PointingHandCursor)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._rebuild_preset_grid(categories[0])

    def _on_category_clicked(self, category: str) -> None:
        self._rebuild_preset_grid(category)

    def _rebuild_preset_grid(self, category: str) -> None:
        while self.preset_grid.count():
            old_card = self.preset_grid.takeAt(0).widget()
            old_card.hide()
            old_card.deleteLater()

        self._preset_cards = []
        presets = self.viewmodel.list_presets(category)
        for index, preset in enumerate(presets):
            card = _PresetCard(preset)
            card.clicked.connect(partial(self._on_preset_clicked, preset, card))
            self._preset_cards.append(card)
            self.preset_grid.addWidget(card, index // PRESET_GRID_COLUMNS, index % PRESET_GRID_COLUMNS)

        if presets:
            self._on_preset_clicked(presets[0], self._preset_cards[0])

    def _on_preset_clicked(self, preset: CanvasPreset, card: _PresetCard) -> None:
        self.width_box.blockSignals(True)
        self.height_box.blockSignals(True)
        self.width_box.setValue(preset.width)
        self.height_box.setValue(preset.height)
        self.width_box.blockSignals(False)
        self.height_box.blockSignals(False)

        for other in self._preset_cards:
            other.set_selected(other is card)
        self._set_custom_section_active(False)
        self._selected_size = (preset.width, preset.height)
        self._update_custom_preview(preset.width, preset.height)

    def _on_custom_changed(self, _value: int) -> None:
        for card in self._preset_cards:
            card.set_selected(False)
        self._set_custom_section_active(True)
        width, height = self.width_box.value(), self.height_box.value()
        self._selected_size = (width, height)
        self._update_custom_preview(width, height)

    def _on_swap_clicked(self) -> None:
        width, height = self.width_box.value(), self.height_box.value()
        self.width_box.setValue(height)
        self.height_box.setValue(width)

    def _update_custom_preview(self, width: int, height: int) -> None:
        swatch_width, swatch_height = _swatch_size(width, height)
        self.custom_preview_swatch.setFixedSize(swatch_width, swatch_height)
        self.hint_label.setText(f"Ratio {_aspect_ratio_text(width, height)}  ·  Max 10,000 x 10,000 px")

    def _set_custom_section_active(self, active: bool) -> None:
        self.custom_section.setProperty("active", active)
        self.custom_section.style().unpolish(self.custom_section)
        self.custom_section.style().polish(self.custom_section)
        self.custom_section.update()

    def selected_size(self) -> tuple[int, int]:
        return self._selected_size

    def showEvent(self, event: QShowEvent) -> None:
        self._center_on_parent()
        if self._backdrop is not None:
            self._backdrop.show()
            self._backdrop.raise_()
        super().showEvent(event)
        # The dialog's own sizeHint can grow slightly on first paint (icon
        # fonts finishing their one-time load), so re-center once that's
        # settled rather than leaving it slightly off from the size used above.
        QTimer.singleShot(0, self._center_on_parent)

    def _center_on_parent(self) -> None:
        parent = self.parentWidget()
        anchor = parent.window().frameGeometry() if parent is not None else self.screen().availableGeometry()
        x = anchor.x() + (anchor.width() - self.width()) // 2
        y = anchor.y() + (anchor.height() - self.height()) // 2
        self.move(x, y)

    def paintEvent(self, event: QPaintEvent) -> None:
        # QSS border-radius doesn't reliably paint on a translucent top-level
        # window, so the rounded card background is drawn by hand here instead.
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, DIALOG_CORNER_RADIUS, DIALOG_CORNER_RADIUS)
        painter.setPen(QPen(QColor(theme.BORDER), 1))
        painter.setBrush(QColor(theme.BACKGROUND))
        painter.drawPath(path)
