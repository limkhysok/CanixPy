"""One page within a DesignScene's stacked multi-page document.

`Page` deliberately doesn't store width/height/y_offset/background_color as
independent fields -- it reads through to its own QGraphicsRectItem frame,
so there's exactly one source of truth for a page's geometry (the frame
itself) instead of two that could drift apart.
"""
from __future__ import annotations

from typing import Iterable

from PySide6.QtCore import QRectF
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import QGraphicsItem, QGraphicsRectItem

# Scene units between stacked pages -- visual breathing room so adjacent
# pages read as separate sheets, not one continuous surface.
PAGE_GAP = 80


class Page:
    def __init__(self, frame: QGraphicsRectItem, name: str | None = None) -> None:
        self.frame = frame
        self.name = name  # None means "auto-numbered by position"

    @property
    def width(self) -> float:
        return self.frame.rect().width()

    @property
    def height(self) -> float:
        return self.frame.rect().height()

    @property
    def y_offset(self) -> float:
        return self.frame.pos().y()

    @property
    def background_color(self) -> str:
        return self.frame.brush().color().name()

    def set_size(self, width: float, height: float) -> None:
        self.frame.setRect(0, 0, width, height)

    def set_background_color(self, color: QColor) -> None:
        self.frame.setBrush(QBrush(color))

    def set_y_offset(self, y: float) -> None:
        self.frame.setPos(0, y)

    def rect(self) -> QRectF:
        """This page's bounds in scene coordinates."""
        return QRectF(0, self.y_offset, self.width, self.height)


def page_for_item(pages: list[Page], item: QGraphicsItem) -> Page:
    """Which page an item "belongs to" -- derived from its current position,
    never stored, since items can legitimately be dragged from one page's
    region into another's. Falls back to the nearest page by edge distance
    when the item's center sits in the gap between pages."""
    y = item.sceneBoundingRect().center().y()

    def distance(page: Page) -> float:
        top, bottom = page.y_offset, page.y_offset + page.height
        if top <= y <= bottom:
            return 0.0
        return min(abs(y - top), abs(y - bottom))

    return min(pages, key=distance)


def partition_items_by_page(
    scene_items: Iterable[QGraphicsItem], frames: set[QGraphicsItem], pages: list[Page]
) -> dict[int, list[QGraphicsItem]]:
    """Groups top-level (non-frame, unparented) items by page index, in each
    page's original relative (z-order) iteration order."""
    result: dict[int, list[QGraphicsItem]] = {i: [] for i in range(len(pages))}
    for item in scene_items:
        if item in frames or item.parentItem() is not None:
            continue
        page = page_for_item(pages, item)
        result[pages.index(page)].append(item)
    return result
