"""Shared chrome for the app's frameless "card" dialogs: a rounded white
card with no native title bar, floating over a blurred/tinted snapshot of
the window behind it. Native title bars can't be restyled to match the
sage-green theme, so every such dialog (CanvasSizeDialog, ExportDialog, ...)
replaces its own with a drag-to-move DialogTitleBar instead.

Split out of canvas_size_dialog.py once a second dialog needed the same
frameless/blur/rounded-card treatment -- extracting it here means both share
one implementation instead of drifting apart.
"""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
    QPixmap,
    QShowEvent,
)
from PySide6.QtWidgets import (
    QDialog,
    QGraphicsBlurEffect,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QLabel,
    QWidget,
)

from src.core import theme

CARD_CORNER_RADIUS = 16
BACKDROP_BLUR_RADIUS = 18
BACKDROP_BLUR_DOWNSCALE = 3
BACKDROP_TINT_COLOR = "#1A1613"
BACKDROP_TINT_ALPHA = 90


def blur_pixmap(pixmap: QPixmap, radius: float, downscale: int = 1) -> QPixmap:
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


class BlurBackdrop(QWidget):
    """A blurred snapshot of the window behind a dialog, covering its client
    area as a child overlay while the dialog is open. Stacking this as a
    *separate top-level window* turned out to be unreliable -- Windows
    doesn't consistently place a newly created window above an
    already-focused one, even after raise_()/activateWindow(). Child-widget
    stacking within the same top-level window is Qt-managed and reliable,
    and the modal dialog itself (a real top-level window) already reliably
    renders above its parent regardless."""

    def __init__(self, source_window: QWidget) -> None:
        super().__init__(source_window)
        self.setGeometry(0, 0, source_window.width(), source_window.height())

        blurred = blur_pixmap(source_window.grab(), BACKDROP_BLUR_RADIUS, BACKDROP_BLUR_DOWNSCALE)
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


class DialogTitleBar(QWidget):
    """Drag-to-move header strip, replacing the OS title bar since the
    dialog runs frameless (no native toolbar/title bar). Doesn't draw
    anything itself -- subclasses/callers lay their own icon/title/close
    button into it."""

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


class FramelessCardDialog(QDialog):
    """Base for a frameless, translucent-window dialog painted as a single
    rounded white card, with a blurred/tinted backdrop over whatever window
    it was opened from. Subclasses build their own content (typically
    starting with a DialogTitleBar) into a QVBoxLayout on `self` -- the
    header's contents vary too much (icon choice, title, whether there's a
    subtitle) to templatize, so only the window chrome itself is shared."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self._backdrop: BlurBackdrop | None = None
        if parent is not None:
            self._backdrop = BlurBackdrop(parent.window())
            self.finished.connect(self._backdrop.close)

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
        path.addRoundedRect(rect, CARD_CORNER_RADIUS, CARD_CORNER_RADIUS)
        painter.setPen(QPen(QColor(theme.BORDER), 1))
        painter.setBrush(QColor(theme.BACKGROUND))
        painter.drawPath(path)
