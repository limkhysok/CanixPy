"""One page within a DesignScene's multi-page document. Pages are freely
positioned (drag them on the canvas -- see PageFrameItem in canvas/items.py),
not auto-stacked.

`Page` deliberately doesn't store width/height/x_offset/y_offset/
background_color as independent fields -- it reads through to its own
QGraphicsRectItem frame, so there's exactly one source of truth for a page's
geometry (the frame itself) instead of two that could drift apart.
"""
from __future__ import annotations

import math
from typing import Iterable

from PySide6.QtCore import QRectF
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import QGraphicsItem, QGraphicsRectItem

# Scene units below the previous page a freshly added/duplicated page starts
# at -- just an initial placement, not an enforced invariant; pages are
# freely draggable afterward.
PAGE_GAP = 80

# Smallest a page can be resized to, whether typed into the Properties panel's
# W/H boxes or dragged via PageFrameItem's resize handles (see canvas/items.py).
PAGE_MIN_SIZE = 100


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
    def x_offset(self) -> float:
        return self.frame.pos().x()

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

    def rect(self) -> QRectF:
        """This page's bounds in scene coordinates."""
        return QRectF(self.x_offset, self.y_offset, self.width, self.height)


def page_for_item(pages: list[Page], item: QGraphicsItem) -> Page:
    """Which page an item "belongs to" -- derived from its current position,
    never stored, since items can legitimately be dragged from one page's
    region into another's (or into the gap between freely-positioned pages).
    Falls back to the nearest page by 2D distance-to-rect when the item's
    center isn't actually inside any page."""
    center = item.sceneBoundingRect().center()

    def distance(page: Page) -> float:
        rect = page.rect()
        if rect.contains(center):
            return 0.0
        dx = max(rect.left() - center.x(), 0.0, center.x() - rect.right())
        dy = max(rect.top() - center.y(), 0.0, center.y() - rect.bottom())
        return math.hypot(dx, dy)

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
