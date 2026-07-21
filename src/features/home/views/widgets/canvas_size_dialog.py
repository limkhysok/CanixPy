from __future__ import annotations

from functools import partial
from math import gcd
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QEvent, QObject, QPoint, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QEnterEvent,
    QFont,
    QFontMetrics,
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
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFrame,
    QGraphicsBlurEffect,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from src.core import icons, theme
from src.features.home.viewmodels.home_viewmodel import (
    MAX_CANVAS_PX,
    UNIT_DECIMALS,
    UNIT_PX_PER_UNIT,
    CanvasPreset,
    HomeViewModel,
    px_to_unit,
    unit_to_px,
)

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

# Each category icon's real brand/original color, used when its chip is unchecked.
CATEGORY_ICON_COLORS: dict[str, str] = {
    "Popular": "#FF6B35",
    "Facebook": "#1877F2",
    "Instagram": "#E4405F",
    "LinkedIn": "#0A66C2",
    "Pinterest": "#E60023",
    "TikTok": "#000000",
    "Twitter": "#1DA1F2",
    "YouTube": "#FF0000",
}

CATEGORY_CHIP_ICON_SIZE = 14

DIALOG_CORNER_RADIUS = 16

DIALOG_STYLE = theme.load_qss(Path(__file__).with_name("canvas_size_dialog.qss"))

PRESET_SWATCH_MAX = 24
PRESET_SWATCH_MIN = 8
PRESET_ICON_BOX = 48
PRESET_GRID_COLUMNS = 4
PRESET_NAME_FONT_SIZE = 14
PRESET_NAME_FONT_WEIGHT = QFont.Weight.DemiBold
BACKDROP_BLUR_RADIUS = 18
BACKDROP_BLUR_DOWNSCALE = 3
BACKDROP_TINT_COLOR = "#1A1613"
BACKDROP_TINT_ALPHA = 90


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
    QDoubleSpinBox's cramped, dated-looking up/down buttons. Uses a double
    spin box (not an int one) even for whole-pixel values, since the same
    field is reused to display fractional inch/mm/cm sizes when the unit
    dropdown is switched off "px"."""

    valueChanged = Signal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("spinField")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setProperty("focused", False)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 4, 0)
        layout.setSpacing(2)

        self.spin = QDoubleSpinBox()
        self.spin.setObjectName("spinFieldInput")
        self.spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.spin.setFrame(False)
        self.spin.setDecimals(0)
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

    def setRange(self, minimum: float, maximum: float) -> None:
        self.spin.setRange(minimum, maximum)

    def setSuffix(self, suffix: str) -> None:
        self.spin.setSuffix(suffix)

    def setDecimals(self, decimals: int) -> None:
        self.spin.setDecimals(decimals)

    def setValue(self, value: float) -> None:
        self.spin.setValue(value)

    def value(self) -> float:
        return self.spin.value()

    def blockSignals(self, block: bool) -> bool:
        self.spin.blockSignals(block)
        return super().blockSignals(block)


UNIT_FIELD_CHEVRON_SIZE = 8
UNIT_FIELD_MIN_WIDTH = 92


class _UnitCombo(QComboBox):
    """QComboBox that pins its popup to its own width -- Qt's default popup
    sizing instead follows the widest item text, which for short unit labels
    like "px"/"in" leaves the dropdown narrower than the field itself."""

    def showPopup(self) -> None:
        self.view().setFixedWidth(self.width())
        # The popup's own top-level window is opaque by default, so the
        # QSS border-radius on the view paints rounded content over square
        # window corners -- same square-corner-under-rounded-shape issue
        # CanvasSizeDialog itself works around, just one level down.
        self.view().window().setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        super().showPopup()


class _UnitField(QWidget):
    """A unit dropdown styled to match _SpinField's bordered container: a
    QComboBox's native drop-down arrow is unstyleable to match the dialog's
    fontawesome iconography, so it's hidden and replaced with the same
    chevron icon the spin steppers use."""

    currentTextChanged = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("unitField")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setProperty("focused", False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumWidth(UNIT_FIELD_MIN_WIDTH)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 8, 0)
        layout.setSpacing(4)

        self.combo = _UnitCombo()
        self.combo.setObjectName("unitFieldInput")
        self.combo.setFrame(False)
        self.combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.combo.installEventFilter(self)
        self.combo.currentTextChanged.connect(self.currentTextChanged)
        layout.addWidget(self.combo, 1)

        self._chevron = QLabel()
        self._chevron.setPixmap(
            icons.icon("fa5s.chevron-down", color=theme.TEXT_SECONDARY).pixmap(
                UNIT_FIELD_CHEVRON_SIZE, UNIT_FIELD_CHEVRON_SIZE
            )
        )
        self._chevron.installEventFilter(self)
        layout.addWidget(self._chevron, 0, Qt.AlignmentFlag.AlignVCenter)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self.combo:
            if event.type() == QEvent.Type.FocusIn:
                self._set_focused(True)
            elif event.type() == QEvent.Type.FocusOut:
                self._set_focused(False)
        elif watched is self._chevron and event.type() == QEvent.Type.MouseButtonPress:
            # The chevron is a plain QLabel sitting outside the QComboBox's own
            # geometry, so clicks on it never reach the combo -- forward them
            # here so the visible arrow is actually clickable, not a dead zone.
            self.combo.showPopup()
            return True
        return super().eventFilter(watched, event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        # Clicking the field's own padding (outside both the combo and the
        # chevron) should also open the dropdown, matching the pointing-hand
        # cursor set over the whole field.
        if event.button() == Qt.MouseButton.LeftButton:
            self.combo.showPopup()
            event.accept()
            return
        super().mousePressEvent(event)

    def _set_focused(self, focused: bool) -> None:
        self.setProperty("focused", focused)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def addItems(self, items: list[str]) -> None:
        self.combo.addItems(items)

    def setCurrentText(self, text: str) -> None:
        self.combo.setCurrentText(text)

    def currentText(self) -> str:
        return self.combo.currentText()


CATEGORY_CHIP_RADIUS = 15


class _CategoryChip(QPushButton):
    """QPushButton overridden to size itself from its child layout (the base
    class computes its sizeHint purely from its own text/icon properties and
    ignores any layout placed on it, which left chips clipped now that their
    icon and label are child QLabels rather than the button's own text/icon)
    and to paint its own rounded background: QSS border-radius is dropped
    for the :checked state specifically once a child layout is involved, so
    the pill background/border is drawn by hand instead, same workaround
    CanvasSizeDialog itself already relies on for its own translucent window."""

    def sizeHint(self) -> QSize:
        layout = self.layout()
        return layout.sizeHint() if layout is not None else super().sizeHint()

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def enterEvent(self, event: QEnterEvent) -> None:
        super().enterEvent(event)
        self.update()

    def leaveEvent(self, event: QEvent) -> None:
        super().leaveEvent(event)
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        if self.isChecked():
            background, border = theme.ACCENT, theme.ACCENT
        elif self.underMouse():
            background, border = theme.ACCENT_LIGHT, theme.ACCENT
        else:
            background, border = theme.BACKGROUND, theme.BORDER

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, CATEGORY_CHIP_RADIUS, CATEGORY_CHIP_RADIUS)
        painter.setPen(QPen(QColor(border), 1))
        painter.setBrush(QColor(background))
        painter.drawPath(path)


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
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setToolTip(f"{preset.name} — {preset.width} × {preset.height} px")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 16, 14, 14)
        layout.setSpacing(10)
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
        name_label.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        name_label.setWordWrap(True)
        # Fixed to exactly two text lines so a long name (e.g. "Facebook Event
        # Cover") and a short one (e.g. "Default") still produce identically
        # sized cards -- otherwise cards wrap unevenly and rows look ragged.
        name_font = QFont()
        name_font.setPixelSize(PRESET_NAME_FONT_SIZE)
        name_font.setWeight(PRESET_NAME_FONT_WEIGHT)
        name_label.setFixedHeight(QFontMetrics(name_font).lineSpacing() * 2)
        layout.addWidget(name_label)

        dims_label = QLabel(f"{preset.width} × {preset.height} px")
        dims_label.setObjectName("presetDims")
        dims_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(dims_label)

        # Lock in the height every card now naturally computes to (all inner
        # parts above are fixed-size), so the grid's rows line up evenly
        # instead of stretching short cards to match a taller row-mate.
        self.setFixedHeight(self.sizeHint().height())

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
        self.setMinimumWidth(1100)
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
            chip = self._make_category_chip(category, checked=index == 0)
            chip.clicked.connect(partial(self._on_category_clicked, category))
            self._category_group.addButton(chip)
            category_row.addWidget(chip)
        category_row.addStretch(1)
        self.category_scroll.setWidget(category_content)
        layout.addWidget(self.category_scroll)

        self.preset_scroll = QScrollArea()
        self.preset_scroll.setObjectName("presetScroll")
        self.preset_scroll.setWidgetResizable(True)
        self.preset_scroll.setFixedHeight(320)
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
        # Width/Height stretch to fill whatever space is left; the separator
        # and unit dropdown stay at their natural size -- so the row as a
        # whole spans edge-to-edge instead of leaving dead space on the right.
        custom_grid.setColumnStretch(0, 1)
        custom_grid.setColumnStretch(2, 1)

        width_field_label = QLabel("Width")
        width_field_label.setObjectName("fieldLabel")
        height_field_label = QLabel("Height")
        height_field_label.setObjectName("fieldLabel")
        unit_field_label = QLabel("Unit")
        unit_field_label.setObjectName("fieldLabel")
        custom_grid.addWidget(width_field_label, 0, 0)
        custom_grid.addWidget(height_field_label, 0, 2)
        custom_grid.addWidget(unit_field_label, 0, 3)

        self.width_box = _SpinField()
        self.width_box.valueChanged.connect(self._on_custom_changed)

        self.height_box = _SpinField()
        self.height_box.valueChanged.connect(self._on_custom_changed)

        separator = QLabel("×")
        separator.setObjectName("customSizeSeparator")
        separator.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.unit_combo = _UnitField()
        self.unit_combo.addItems(list(UNIT_PX_PER_UNIT))
        self.unit_combo.currentTextChanged.connect(self._on_unit_changed)

        custom_grid.addWidget(self.width_box, 1, 0)
        custom_grid.addWidget(separator, 1, 1)
        custom_grid.addWidget(self.height_box, 1, 2)
        custom_grid.addWidget(self.unit_combo, 1, 3)
        content_row.addLayout(custom_grid, 1)
        custom_layout.addLayout(content_row)

        self._unit = "px"
        self.width_box.blockSignals(True)
        self.height_box.blockSignals(True)
        self._configure_spin_fields_for_unit()
        self.width_box.setValue(self._px_to_unit(self._selected_size[0]))
        self.height_box.setValue(self._px_to_unit(self._selected_size[1]))
        self.width_box.blockSignals(False)
        self.height_box.blockSignals(False)

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

    def _make_category_chip(self, category: str, checked: bool) -> QPushButton:
        # Built from child QLabels rather than QPushButton's native icon+text,
        # since Qt's QStyleSheetStyle mis-centers the text vertically whenever
        # a styled QPushButton carries both an icon and a label -- plain
        # QLabels don't go through that painting path and center correctly.
        chip = _CategoryChip()
        chip.setObjectName("categoryChip")
        chip.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        chip.setCheckable(True)
        chip.setCursor(Qt.CursorShape.PointingHandCursor)

        chip_layout = QHBoxLayout(chip)
        chip_layout.setContentsMargins(14, 6, 14, 6)
        chip_layout.setSpacing(6)

        icon_label = QLabel()
        text_label = QLabel(category)
        text_label.setObjectName("categoryChipText")
        chip_layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignVCenter)
        chip_layout.addWidget(text_label, 0, Qt.AlignmentFlag.AlignVCenter)

        def apply_state(is_checked: bool) -> None:
            icon_color = theme.TEXT_ON_ACCENT if is_checked else CATEGORY_ICON_COLORS[category]
            icon_label.setPixmap(
                icons.icon(CATEGORY_ICONS[category], color=icon_color).pixmap(
                    CATEGORY_CHIP_ICON_SIZE, CATEGORY_CHIP_ICON_SIZE
                )
            )
            text_color = theme.TEXT_ON_ACCENT if is_checked else theme.TEXT_PRIMARY
            text_label.setStyleSheet(f"color: {text_color};")

        chip.toggled.connect(apply_state)
        chip.setChecked(checked)
        apply_state(checked)
        return chip

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
        self.width_box.setValue(self._px_to_unit(preset.width))
        self.height_box.setValue(self._px_to_unit(preset.height))
        self.width_box.blockSignals(False)
        self.height_box.blockSignals(False)

        for other in self._preset_cards:
            other.set_selected(other is card)
        self._set_custom_section_active(False)
        self._selected_size = (preset.width, preset.height)
        self._update_custom_preview(preset.width, preset.height)

    def _on_custom_changed(self, _value: float) -> None:
        for card in self._preset_cards:
            card.set_selected(False)
        self._set_custom_section_active(True)
        width = self._unit_to_px(self.width_box.value())
        height = self._unit_to_px(self.height_box.value())
        self._selected_size = (width, height)
        self._update_custom_preview(width, height)

    def _on_unit_changed(self, unit: str) -> None:
        # Capture the current size, and block signals, before touching range/
        # decimals: setRange() clamps the field's still-old-unit value into
        # the new unit's range and fires an unblocked valueChanged, which
        # would otherwise clobber self._selected_size with a bogus clamp
        # before we get a chance to write the correctly-converted value.
        width_px, height_px = self._selected_size
        self._unit = unit
        self.width_box.blockSignals(True)
        self.height_box.blockSignals(True)
        self._configure_spin_fields_for_unit()
        self.width_box.setValue(self._px_to_unit(width_px))
        self.height_box.setValue(self._px_to_unit(height_px))
        self.width_box.blockSignals(False)
        self.height_box.blockSignals(False)

    def _configure_spin_fields_for_unit(self) -> None:
        decimals = UNIT_DECIMALS[self._unit]
        for field in (self.width_box, self.height_box):
            field.setDecimals(decimals)
            field.setRange(self._px_to_unit(1), self._px_to_unit(MAX_CANVAS_PX))
            field.setSuffix(f" {self._unit}")

    def _px_to_unit(self, value_px: int) -> float:
        return px_to_unit(value_px, self._unit)

    def _unit_to_px(self, value: float) -> int:
        return unit_to_px(value, self._unit)

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
