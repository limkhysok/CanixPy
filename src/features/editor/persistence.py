"""Serialize/deserialize graphics items and whole projects.

A single item-level format backs three features: saving/loading a project
to disk, copy/paste, and duplicate -- all three just need "turn this item
into plain data" and "turn that data back into a live item", so it made
sense to build it once here instead of three separate ad-hoc paths.

Groups serialize their children recursively (a child's x/y is already
relative to its parent group, exactly what gets stored), and rebuild via
QGraphicsItemGroup.addToGroup() rather than scene.createItemGroup() --
createItemGroup derives the group's own geometry from its children's
*current scene position*, which doesn't exist yet for items that aren't in
a scene. addToGroup() just reparents, preserving the relative positions
already baked into the serialized data.
"""
from __future__ import annotations

import base64
import json
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QGradient, QLinearGradient, QPen, QPixmap, QTextOption
from PySide6.QtWidgets import (
    QAbstractGraphicsShapeItem,
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsItemGroup,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsTextItem,
)

from src.features.editor.canvas.items import (
    ResizableEllipseItem,
    ResizablePixmapItem,
    ResizablePolygonItem,
    ResizableRectItem,
    RotatableTextItem,
    get_layer_name,
    get_shape_kind,
    is_layer_locked,
    make_shadow_effect,
    set_layer_locked,
    set_layer_name,
    set_shape_kind,
)

if TYPE_CHECKING:
    from src.features.editor.canvas.scene import DesignScene
    from src.features.editor.editor_view import CoreDesignApp

PROJECT_FORMAT_VERSION = 2


def _common_fields(item: QGraphicsItem) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "x": item.pos().x(), "y": item.pos().y(), "z": item.zValue(),
        "rotation": item.rotation(),
        "visible": item.isVisible(),
        "locked": is_layer_locked(item),
        "opacity": item.opacity(),
        "shadow": item.graphicsEffect() is not None,  # type: ignore[reportUnnecessaryComparison]
    }
    name = get_layer_name(item)
    if name:
        fields["name"] = name
    shape_kind = get_shape_kind(item)
    if shape_kind and not isinstance(item, ResizablePolygonItem):
        # ResizablePolygonItem's own shape_kind is the *template* selector
        # (serialized separately in its "polygon" branch below); this is
        # only for tags on otherwise-plain items, e.g. "Line" on a thin rect.
        fields["shape_kind"] = shape_kind
    return fields


def _apply_common_fields(item: QGraphicsItem, data: dict[str, Any]) -> None:
    item.setPos(data["x"], data["y"])
    item.setZValue(data.get("z", 0))
    item.setRotation(data.get("rotation", 0.0))
    item.setVisible(data.get("visible", True))
    item.setOpacity(data.get("opacity", 1.0))
    if data.get("shadow"):
        item.setGraphicsEffect(make_shadow_effect())
    if data.get("name"):
        set_layer_name(item, data["name"])
    if data.get("shape_kind"):
        set_shape_kind(item, data["shape_kind"])
    item.setFlags(
        QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
        QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
    )
    if data.get("locked"):
        set_layer_locked(item, True)


def _fill_fields(item: QAbstractGraphicsShapeItem) -> dict[str, Any]:
    brush = item.brush()
    fields: dict[str, Any]
    if brush.style() == Qt.BrushStyle.LinearGradientPattern and brush.gradient() is not None:  # type: ignore[reportUnnecessaryComparison]
        stops = brush.gradient().stops()
        start = stops[0][1].name() if len(stops) > 0 else "#000000"
        end = stops[-1][1].name() if len(stops) > 1 else start
        fields = {"gradient": [start, end]}
    else:
        fields = {"color": brush.color().name()}

    pen = item.pen()
    if pen.width() > 0:
        fields["stroke_width"] = pen.width()
        fields["stroke_color"] = pen.color().name()
    return fields


def _apply_fill_fields(item: QAbstractGraphicsShapeItem, data: dict[str, Any]) -> None:
    gradient_colors = data.get("gradient")
    if gradient_colors:
        gradient = QLinearGradient(0, 0, 1, 1)
        gradient.setCoordinateMode(QGradient.CoordinateMode.ObjectBoundingMode)
        gradient.setColorAt(0.0, QColor(gradient_colors[0]))
        gradient.setColorAt(1.0, QColor(gradient_colors[1]))
        item.setBrush(QBrush(gradient))
    else:
        item.setBrush(QBrush(QColor(data.get("color", "#3498db"))))

    if data.get("stroke_width"):
        pen = QPen(QColor(data.get("stroke_color", "#000000")))
        pen.setWidth(data["stroke_width"])
        item.setPen(pen)


def serialize_item(item: QGraphicsItem) -> dict[str, Any] | None:
    if isinstance(item, QGraphicsItemGroup):
        children = [c for c in (serialize_item(child) for child in item.childItems()) if c is not None]
        return {
            "kind": "group",
            "children": children,
            **_common_fields(item),
        }
    if isinstance(item, ResizablePolygonItem):
        rect = item.local_rect()
        return {
            "kind": "polygon",
            "shape_kind": item.shape_kind,
            "width": rect.width(), "height": rect.height(),
            **_fill_fields(item),
            **_common_fields(item),
        }
    if isinstance(item, QGraphicsRectItem):
        rect = item.rect()
        return {
            "kind": "rect",
            "width": rect.width(), "height": rect.height(),
            **_fill_fields(item),
            **_common_fields(item),
        }
    if isinstance(item, QGraphicsEllipseItem):
        rect = item.rect()
        return {
            "kind": "ellipse",
            "width": rect.width(), "height": rect.height(),
            **_fill_fields(item),
            **_common_fields(item),
        }
    if isinstance(item, QGraphicsTextItem):
        font = item.font()
        alignment = item.document().defaultTextOption().alignment()
        return {
            "kind": "text",
            "text": item.toPlainText(),
            "font_family": font.family(),
            "font_size": font.pointSize(),
            "bold": font.bold(),
            "italic": font.italic(),
            "underline": font.underline(),
            "alignment": int(alignment),
            "text_width": item.textWidth(),
            "color": item.defaultTextColor().name(),
            **_common_fields(item),
        }
    if isinstance(item, QGraphicsPixmapItem):
        buffer = QByteArray()
        io_device = QBuffer(buffer)
        io_device.open(QIODevice.OpenModeFlag.WriteOnly)
        item.pixmap().save(io_device, "PNG")
        io_device.close()
        return {
            "kind": "image",
            "png_base64": base64.b64encode(buffer.data()).decode("ascii"),
            "scale": item.scale(),
            **_common_fields(item),
        }
    return None


def _deserialize_polygon(data: dict[str, Any]) -> QGraphicsItem:
    item = ResizablePolygonItem(data["shape_kind"], data["width"], data["height"])
    _apply_fill_fields(item, data)
    return item


def _deserialize_rect(data: dict[str, Any]) -> QGraphicsItem:
    item = ResizableRectItem(0, 0, data["width"], data["height"])
    _apply_fill_fields(item, data)
    return item


def _deserialize_ellipse(data: dict[str, Any]) -> QGraphicsItem:
    item = ResizableEllipseItem(0, 0, data["width"], data["height"])
    _apply_fill_fields(item, data)
    return item


def _deserialize_text(data: dict[str, Any]) -> QGraphicsItem:
    item = RotatableTextItem(data["text"])
    font = QFont(data["font_family"])
    font.setPointSize(data["font_size"])
    font.setBold(data.get("bold", False))
    font.setItalic(data.get("italic", False))
    font.setUnderline(data.get("underline", False))
    item.setFont(font)
    item.setDefaultTextColor(QColor(data["color"]))
    item.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditable)
    if data.get("text_width", -1) >= 0:
        item.setTextWidth(data["text_width"])
    if "alignment" in data:
        option = QTextOption(item.document().defaultTextOption())
        option.setAlignment(Qt.AlignmentFlag(data["alignment"]))
        item.document().setDefaultTextOption(option)
    return item


def _deserialize_image(data: dict[str, Any]) -> QGraphicsItem:
    pixmap = QPixmap()
    pixmap.loadFromData(base64.b64decode(data["png_base64"]), "PNG")
    item = ResizablePixmapItem(pixmap)
    item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
    item.setScale(data.get("scale", 1.0))
    return item


# "group" isn't in here -- it recurses into deserialize_item for its children
# and doesn't fit the flat (data) -> item shape the others share, so
# deserialize_item handles it directly instead of through this dispatch table.
_ITEM_BUILDERS: dict[str, Callable[[dict[str, Any]], QGraphicsItem]] = {
    "polygon": _deserialize_polygon,
    "rect": _deserialize_rect,
    "ellipse": _deserialize_ellipse,
    "text": _deserialize_text,
    "image": _deserialize_image,
}


def deserialize_item(data: dict[str, Any]) -> QGraphicsItem | None:
    kind = data.get("kind")

    if kind == "group":
        group = QGraphicsItemGroup()
        for child_data in data.get("children", []):
            child = deserialize_item(child_data)
            if child is not None:
                group.addToGroup(child)
        _apply_common_fields(group, data)
        return group

    if not isinstance(kind, str):
        return None

    builder = _ITEM_BUILDERS.get(kind)
    if builder is None:
        return None

    item = builder(data)
    _apply_common_fields(item, data)
    return item


def serialize_page(scene: "DesignScene") -> list[dict[str, Any]]:
    page_frame = getattr(scene, "page_frame", None)
    result: list[dict[str, Any]] = []
    for item in scene.items():
        # Grouped children are serialized recursively as part of their
        # group (see the QGraphicsItemGroup case in serialize_item), not
        # as separate top-level entries here.
        if item is page_frame or item.parentItem() is not None:  # type: ignore[reportUnnecessaryComparison]
            continue
        data = serialize_item(item)
        if data is not None:
            result.append(data)
    return result


def serialize_page_entry(scene: "DesignScene") -> dict[str, Any]:
    entry: dict[str, Any] = {"items": serialize_page(scene)}
    if scene.page_name:
        entry["name"] = scene.page_name
    return entry


def serialize_project(app: "CoreDesignApp") -> dict[str, Any]:
    return {
        "format_version": PROJECT_FORMAT_VERSION,
        "canvas_size": list(app.canvas_size),
        # A plain ordered list -- page order/identity is just list position,
        # so reordering pages doesn't need any renumbering bookkeeping.
        "pages": [serialize_page_entry(scene) for scene in app.pages],
    }


def save_project(app: "CoreDesignApp", file_path: str) -> None:
    with open(file_path, "w", encoding="utf-8") as handle:
        json.dump(serialize_project(app), handle)


def load_project_data(file_path: str) -> dict[str, Any]:
    with open(file_path, "r", encoding="utf-8") as handle:
        return json.load(handle)
