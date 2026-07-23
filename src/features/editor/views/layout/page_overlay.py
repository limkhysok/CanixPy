"""Floating per-page controls: a small pill under each page's bottom edge
(name, double-click to rename, "..." menu for duplicate/delete/move) plus a
trailing "+ Add Page" pill next to the last page's label. Positioned by
ZoomableGraphicsView every repaint (see PageOverlayManager.sync) so they
track scroll/zoom/page-resize/reflow without the view needing to know what
they actually are -- replaces the old single page-name-combo PageBar, which
doesn't make sense once every page is visible at once instead of switched
between.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QPoint, QRectF, Qt
from PySide6.QtGui import QAction, QColor, QMouseEvent
from PySide6.QtWidgets import (
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QToolButton,
    QWidget,
)

from src.core import icons, theme
from src.features.editor.canvas.page import Page

if TYPE_CHECKING:
    from src.features.editor.canvas.view import ZoomableGraphicsView
    from src.features.editor.editor_view import CoreDesignApp

PAGE_OVERLAY_STYLE = theme.load_qss(Path(__file__).with_name("page_overlay.qss"))

# Viewport-pixel gap between a page's bottom edge and the floating label
# tracking it.
OVERLAY_GAP = 10
# Pages whose on-screen rect doesn't come within this many viewport pixels of
# the visible area have their label hidden -- avoids repositioning/painting
# widgets for pages nowhere near the viewport in larger documents.
CULL_MARGIN = 200


def _make_shadow() -> QGraphicsDropShadowEffect:
    shadow = QGraphicsDropShadowEffect()
    shadow.setBlurRadius(18)
    shadow.setOffset(0, 3)
    shadow.setColor(QColor(0, 0, 0, 60))
    return shadow


class PageLabel(QWidget):
    """Floating pill under one page: name (double-click to rename inline) +
    a "..." menu (Duplicate/Delete/Move Up/Move Down) acting on that exact
    Page -- no ambiguous "current page" involved."""

    def __init__(self, main_app: "CoreDesignApp", page: Page, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.main_app = main_app
        self.page = page
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(PAGE_OVERLAY_STYLE)
        self.setGraphicsEffect(_make_shadow())

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 8, 6)
        layout.setSpacing(6)

        self.name_label = QLabel()
        self.name_label.setObjectName("pageName")
        self.name_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.name_label.setToolTip("Double-click to rename")
        layout.addWidget(self.name_label)

        self.name_edit = QLineEdit()
        self.name_edit.setObjectName("pageNameEdit")
        self.name_edit.setVisible(False)
        self.name_edit.editingFinished.connect(self._finish_rename)
        layout.addWidget(self.name_edit)

        btn_menu = QToolButton(self)
        btn_menu.setObjectName("pageMenuButton")
        btn_menu.setText("…")
        btn_menu.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_menu.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)

        menu = QMenu(btn_menu)
        duplicate_action = QAction(icons.icon("fa5s.clone"), "Duplicate Page", menu)
        duplicate_action.triggered.connect(lambda: main_app.duplicate_page(self.page))
        delete_action = QAction(icons.icon("fa5s.trash-alt"), "Delete Page", menu)
        delete_action.triggered.connect(lambda: main_app.delete_page(self.page))
        move_up_action = QAction(icons.icon("fa5s.arrow-up"), "Move Up", menu)
        move_up_action.triggered.connect(lambda: main_app.move_page(self.page, -1))
        move_down_action = QAction(icons.icon("fa5s.arrow-down"), "Move Down", menu)
        move_down_action.triggered.connect(lambda: main_app.move_page(self.page, 1))
        menu.addAction(duplicate_action)
        menu.addAction(delete_action)
        menu.addSeparator()
        menu.addAction(move_up_action)
        menu.addAction(move_down_action)
        btn_menu.setMenu(menu)
        layout.addWidget(btn_menu)

        self.refresh_label()

    def refresh_label(self) -> None:
        self.name_label.setText(self.page.name or self._auto_name())

    def _auto_name(self) -> str:
        index = self.main_app.scene.pages.index(self.page)
        return f"Page {index + 1}"

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self._start_rename()
        super().mouseDoubleClickEvent(event)

    def _start_rename(self) -> None:
        self.name_edit.setText(self.page.name or self._auto_name())
        self.name_label.setVisible(False)
        self.name_edit.setVisible(True)
        self.name_edit.setFocus(Qt.FocusReason.MouseFocusReason)
        self.name_edit.selectAll()

    def _finish_rename(self) -> None:
        self.name_edit.setVisible(False)
        self.name_label.setVisible(True)
        self.main_app.rename_page(self.page, self.name_edit.text())
        self.refresh_label()


class AddPageButton(QWidget):
    """Trailing "+ Add Page" pill next to the last page's label."""

    def __init__(self, main_app: "CoreDesignApp", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(PAGE_OVERLAY_STYLE)
        self.setGraphicsEffect(_make_shadow())

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        btn = QToolButton(self)
        btn.setObjectName("addPageButton")
        btn.setText("Add Page")
        btn.setIcon(icons.icon("fa5s.plus", color=theme.TEXT_PRIMARY))
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(main_app.add_new_page)
        layout.addWidget(btn)


class PageOverlayManager:
    """Owns one PageLabel per Page plus the trailing AddPageButton, all
    parented onto the view's viewport. `rebuild()` re-derives the label set
    after structural changes (add/delete/duplicate/move); `sync()` runs every
    repaint to reposition labels under their page and report the
    most-visible page back to CoreDesignApp as the active page."""

    def __init__(self, main_app: "CoreDesignApp", viewport: QWidget) -> None:
        self.main_app = main_app
        self.viewport = viewport
        self.labels: dict[Page, PageLabel] = {}
        self.add_button = AddPageButton(main_app, viewport)
        self.add_button.show()

    def rebuild(self) -> None:
        pages = self.main_app.scene.pages
        stale = [page for page in self.labels if page not in pages]
        for page in stale:
            self.labels.pop(page).deleteLater()
        for page in pages:
            if page not in self.labels:
                label = PageLabel(self.main_app, page, self.viewport)
                label.show()
                self.labels[page] = label
            else:
                self.labels[page].refresh_label()
        self.add_button.raise_()

    def sync(self, view: "ZoomableGraphicsView") -> None:
        scene = self.main_app.scene
        if set(scene.pages) != set(self.labels):
            self.rebuild()
        if not scene.pages:
            return

        viewport_rect = QRectF(0, 0, view.viewport().width(), view.viewport().height())
        best_page: Page | None = None
        best_area = 0.0
        last_page = scene.pages[-1]
        last_label_rect: QRectF | None = None

        for page in scene.pages:
            label = self.labels[page]
            frame_rect = page.frame.sceneBoundingRect()
            page_view_rect = QRectF(
                view.mapFromScene(frame_rect.topLeft()), view.mapFromScene(frame_rect.bottomRight())
            )
            visible = page_view_rect.adjusted(
                -CULL_MARGIN, -CULL_MARGIN, CULL_MARGIN, CULL_MARGIN
            ).intersects(viewport_rect)
            label.setVisible(visible)
            if visible:
                bottom_center = view.mapFromScene(frame_rect.center().x(), frame_rect.bottom())
                size = label.sizeHint()
                pos = QPoint(bottom_center.x() - size.width() // 2, bottom_center.y() + OVERLAY_GAP)
                if label.pos() != pos:
                    label.move(pos)
                if page is last_page:
                    last_label_rect = QRectF(pos, size)

            intersection = page_view_rect.intersected(viewport_rect)
            area = max(intersection.width(), 0.0) * max(intersection.height(), 0.0)
            if area > best_area:
                best_area = area
                best_page = page

        if last_label_rect is not None:
            # Right next to the last page's own (visible) label.
            pos = QPoint(int(last_label_rect.right()) + OVERLAY_GAP, int(last_label_rect.top()))
        else:
            # Last page's label is culled (scrolled far away) -- fall back to
            # hanging the button directly off the page itself.
            frame_rect = last_page.frame.sceneBoundingRect()
            bottom_center = view.mapFromScene(frame_rect.center().x(), frame_rect.bottom())
            size = self.add_button.sizeHint()
            pos = QPoint(bottom_center.x() - size.width() // 2, bottom_center.y() + OVERLAY_GAP)
        if self.add_button.pos() != pos:
            self.add_button.move(pos)

        if best_page is not None:
            self.main_app.set_active_page(best_page)
