"""Magnetic alignment guides: while an item is dragged, its edges/center are
compared against the page bounds and every other item's edges/center; if any
pair lines up within a small threshold, the drag snaps to it and a guide line
is drawn along the shared coordinate -- the usual Figma/Canva/PowerPoint
"smart guides" behavior.
"""
from __future__ import annotations

from typing import Sequence

from PySide6.QtCore import QLineF, QRectF

# Target *screen* pixels, not scene units -- see _HandleMixin._device_scale()
# for why a fixed scene-unit threshold would feel wildly different depending
# on zoom level.
SNAP_THRESHOLD_PX = 8.0


def _x_edges(rect: QRectF) -> tuple[float, float, float]:
    return (rect.left(), rect.center().x(), rect.right())


def _y_edges(rect: QRectF) -> tuple[float, float, float]:
    return (rect.top(), rect.center().y(), rect.bottom())


def compute_snap(
    proposed_rect: QRectF,
    targets: Sequence[QRectF],
    threshold: float,
) -> tuple[float, float, list[QLineF]]:
    """Finds the smallest x/y adjustment that aligns proposed_rect's left/
    center/right (resp. top/center/bottom) with any target's, each axis
    independently, within `threshold` scene units. Returns (dx, dy,
    guide_lines) -- dx/dy are 0.0 on any axis nothing was close enough to.
    """
    best_dx, best_dx_abs, dx_target, dx_value = 0.0, threshold, None, 0.0
    best_dy, best_dy_abs, dy_target, dy_value = 0.0, threshold, None, 0.0

    for target in targets:
        for item_x in _x_edges(proposed_rect):
            for target_x in _x_edges(target):
                d = target_x - item_x
                if abs(d) < best_dx_abs:
                    best_dx, best_dx_abs, dx_target, dx_value = d, abs(d), target, target_x
        for item_y in _y_edges(proposed_rect):
            for target_y in _y_edges(target):
                d = target_y - item_y
                if abs(d) < best_dy_abs:
                    best_dy, best_dy_abs, dy_target, dy_value = d, abs(d), target, target_y

    snapped_rect = proposed_rect.translated(best_dx, best_dy)
    guides: list[QLineF] = []
    if dx_target is not None:
        top = min(snapped_rect.top(), dx_target.top())
        bottom = max(snapped_rect.bottom(), dx_target.bottom())
        guides.append(QLineF(dx_value, top, dx_value, bottom))
    if dy_target is not None:
        left = min(snapped_rect.left(), dy_target.left())
        right = max(snapped_rect.right(), dy_target.right())
        guides.append(QLineF(left, dy_value, right, dy_value))

    return best_dx, best_dy, guides
