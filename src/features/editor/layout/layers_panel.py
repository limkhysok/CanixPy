from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsItemGroup,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsTextItem,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.core import icons, theme
from src.features.editor.canvas.items import ResizablePolygonItem, get_layer_name, is_layer_locked, set_layer_locked, set_layer_name

if TYPE_CHECKING:
    from src.features.editor.editor_view import CoreDesignApp

_TYPE_ICONS: list[tuple[type[QGraphicsItem], str]] = [
    (QGraphicsItemGroup, "fa5s.object-group"),
    (QGraphicsRectItem, "fa5s.square"),
    (QGraphicsEllipseItem, "fa5s.circle"),
    (QGraphicsTextItem, "fa5s.font"),
    (QGraphicsPixmapItem, "fa5s.image"),
]

_POLYGON_ICONS = {
    "Triangle": "fa5s.play",
    "Diamond": "fa5s.gem",
    "Star": "fa5s.star",
    "Arrow": "fa5s.long-arrow-alt-right",
}

_MAX_LABEL_LEN = 18
_ROW_HEIGHT = 30
_ICON_SIZE = 14
_TOGGLE_SIZE = 20

LAYERS_PANEL_STYLE = theme.load_qss(Path(__file__).with_name("layers_panel.qss"))


def _icon_for(item: QGraphicsItem) -> str:
    shape_kind = getattr(item, "shape_kind", None)
    if shape_kind == "Line":
        return "fa5s.grip-lines"
    if isinstance(item, ResizablePolygonItem):
        return _POLYGON_ICONS.get(item.shape_kind, "fa5s.shapes")
    for cls, name in _TYPE_ICONS:
        if isinstance(item, cls):
            return name
    return "fa5s.shapes"


def _default_label(item: QGraphicsItem) -> str:
    if getattr(item, "shape_kind", None) == "Line":
        return "Line"
    if isinstance(item, QGraphicsItemGroup):
        return "Group"
    if isinstance(item, QGraphicsTextItem):
        text = item.toPlainText().strip() or "Text"
        return text if len(text) <= _MAX_LABEL_LEN else text[:_MAX_LABEL_LEN] + "…"
    if isinstance(item, ResizablePolygonItem):
        return item.shape_kind
    if isinstance(item, QGraphicsRectItem):
        return "Rectangle"
    if isinstance(item, QGraphicsEllipseItem):
        return "Circle"
    if isinstance(item, QGraphicsPixmapItem):
        return "Image"
    return "Item"


def _label_for(item: QGraphicsItem) -> str:
    return get_layer_name(item) or _default_label(item)


class LayerRow(QWidget):
    """One row in the layers list: type icon, (renameable) name, visibility
    toggle, lock toggle. Selecting/clicking talks to the panel rather than
    the scene directly, so the panel can decide replace-vs-toggle semantics."""

    def __init__(self, item: QGraphicsItem, panel: "LayersPanel", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.item = item
        self.panel = panel
        self.setObjectName("layerRow")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(_ROW_HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 4, 2)
        layout.setSpacing(6)

        self.icon_label = QLabel()
        self.icon_label.setPixmap(icons.icon(_icon_for(item), color=theme.TEXT_PRIMARY).pixmap(_ICON_SIZE, _ICON_SIZE))
        layout.addWidget(self.icon_label)

        self.name_label = QLabel(_label_for(item))
        self.name_label.setObjectName("layerName")
        layout.addWidget(self.name_label, 1)

        self.name_edit = QLineEdit(_label_for(item))
        self.name_edit.setVisible(False)
        self.name_edit.editingFinished.connect(self._commit_rename)
        layout.addWidget(self.name_edit, 1)

        self.visible_btn = self._toggle_button()
        self.visible_btn.clicked.connect(self._toggle_visible)
        layout.addWidget(self.visible_btn)

        self.lock_btn = self._toggle_button()
        self.lock_btn.clicked.connect(self._toggle_lock)
        layout.addWidget(self.lock_btn)

        self._refresh_toggle_icons()

    def _toggle_button(self) -> QPushButton:
        btn = QPushButton()
        btn.setObjectName("layerToggle")
        btn.setFixedSize(_TOGGLE_SIZE, _TOGGLE_SIZE)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        return btn

    def _refresh_toggle_icons(self) -> None:
        visible = self.item.isVisible()
        self.visible_btn.setIcon(icons.icon("fa5s.eye" if visible else "fa5s.eye-slash", color=theme.TEXT_SECONDARY))
        self.visible_btn.setToolTip("Hide layer" if visible else "Show layer")

        locked = is_layer_locked(self.item)
        self.lock_btn.setIcon(icons.icon("fa5s.lock" if locked else "fa5s.unlock", color=theme.TEXT_SECONDARY))
        self.lock_btn.setToolTip("Unlock layer" if locked else "Lock layer")

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", selected)
        style = self.style()
        style.unpolish(self)
        style.polish(self)

    def refresh_label(self) -> None:
        self.name_label.setText(_label_for(self.item))

    def mousePressEvent(self, event) -> None:  # noqa: N802
        toggle = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        self.panel.select_item(self.item, toggle=toggle)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        self._start_rename()
        super().mouseDoubleClickEvent(event)

    def _start_rename(self) -> None:
        self.name_edit.setText(self.name_label.text())
        self.name_label.setVisible(False)
        self.name_edit.setVisible(True)
        self.name_edit.setFocus()
        self.name_edit.selectAll()

    def _commit_rename(self) -> None:
        if not self.name_edit.isVisible():
            return
        new_name = self.name_edit.text().strip()
        if new_name:
            set_layer_name(self.item, new_name)
        self.name_edit.setVisible(False)
        self.name_label.setVisible(True)
        self.refresh_label()

    def _toggle_visible(self) -> None:
        self.item.setVisible(not self.item.isVisible())
        self._refresh_toggle_icons()

    def _toggle_lock(self) -> None:
        set_layer_locked(self.item, not is_layer_locked(self.item))
        self._refresh_toggle_icons()
        self.panel.sync_selection()


class LayersPanel(QWidget):
    """Lists items on the current page, front-most first, and keeps the
    canvas selection in sync in both directions."""

    def __init__(self, main_app: "CoreDesignApp", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.main_app = main_app
        self.setStyleSheet(LAYERS_PANEL_STYLE)
        self._rows: dict[QGraphicsItem, LayerRow] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.rows_container = QWidget()
        self.rows_layout = QVBoxLayout(self.rows_container)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(2)
        self.rows_layout.addStretch()

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setWidget(self.rows_container)
        layout.addWidget(self.scroll_area, 1)

        self.empty_hint = QLabel("Nothing on this page yet — drag a shape onto the canvas.")
        self.empty_hint.setObjectName("hintText")
        self.empty_hint.setWordWrap(True)
        layout.addWidget(self.empty_hint)

    def _items_front_to_back(self) -> list[QGraphicsItem]:
        scene = self.main_app.scene
        page_frame = getattr(scene, "page_frame", None)
        # Grouped children are reachable only through their group -- listing
        # them separately would duplicate the group's contents as top-level rows.
        items = [i for i in scene.items() if i != page_frame and i.parentItem() is None]
        items.sort(key=lambda i: i.zValue(), reverse=True)
        return items

    def refresh(self) -> None:
        while self.rows_layout.count() > 1:  # keep the trailing stretch
            item = self.rows_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()

        items = self._items_front_to_back()
        self._rows = {}
        for item in items:
            row = LayerRow(item, self)
            self.rows_layout.insertWidget(self.rows_layout.count() - 1, row)
            self._rows[item] = row

        self.sync_selection()
        self.scroll_area.setVisible(bool(items))
        self.empty_hint.setVisible(not items)

    def sync_selection(self) -> None:
        selected = set(self.main_app.scene.selectedItems())
        for item, row in self._rows.items():
            row.set_selected(item in selected)

    def select_item(self, item: QGraphicsItem, toggle: bool) -> None:
        if is_layer_locked(item):
            return
        if toggle:
            item.setSelected(not item.isSelected())
        else:
            self.main_app.scene.clearSelection()
            item.setSelected(True)
