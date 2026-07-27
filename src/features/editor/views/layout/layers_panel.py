from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, cast

from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtGui import (
    QAction,
    QContextMenuEvent,
    QEnterEvent,
    QKeyEvent,
    QMouseEvent,
)
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsItemGroup,
    QGraphicsOpacityEffect,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsTextItem,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.core import icons, theme
from src.features.editor.canvas.items import (
    ResizablePolygonItem,
    get_layer_name,
    is_layer_locked,
    set_layer_locked,
    set_layer_name,
)
from src.features.editor.canvas.page import Page, page_for_item

if TYPE_CHECKING:
    from src.features.editor.viewmodels.editor_viewmodel import EditorViewModel

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
_INDENT_STEP = 16
_ICON_CHEVRON_DOWN = "fa5s.chevron-down"
_ICON_CHEVRON_RIGHT = "fa5s.chevron-right"

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
        return item.toPlainText().strip() or "Text"
    if isinstance(item, ResizablePolygonItem):
        return item.shape_kind
    if isinstance(item, QGraphicsRectItem):
        return "Rectangle"
    if isinstance(item, QGraphicsEllipseItem):
        return "Circle"
    if isinstance(item, QGraphicsPixmapItem):
        return "Image"
    return "Item"


def _elide(text: str) -> str:
    return text if len(text) <= _MAX_LABEL_LEN else text[:_MAX_LABEL_LEN] + "…"


def _label_for(item: QGraphicsItem) -> str:
    return _elide(_edit_label_for(item))


def _edit_label_for(item: QGraphicsItem) -> str:
    # Un-truncated, unlike _label_for -- seeding the rename box from the
    # ellipsized display label would let a blur-triggered commit (see
    # _RenameLineEdit) permanently shorten a text layer's name to
    # "Lorem ipsum dolo…". Also used as the tooltip so a long custom name is
    # never fully hidden, just abbreviated in the row.
    return get_layer_name(item) or _default_label(item)


class _RenameLineEdit(QLineEdit):
    """Rename field for both LayerRow and PageRow. Escape reverts to the
    text it started with and drops focus, rather than leaving the default
    QLineEdit behavior in place -- editingFinished fires on any blur (not
    just Enter), so without this, hitting Escape or simply clicking
    elsewhere while a half-typed edit is in the box would still commit it."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._original = ""

    def start_editing(self, text: str) -> None:
        self._original = text
        self.setText(text)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.setText(self._original)
            self.clearFocus()
            return
        super().keyPressEvent(event)


class _DragHandle(QLabel):
    """The only part of a LayerRow that initiates a reorder-drag -- keeping
    it a separate child widget (rather than watching for drag gestures on
    the row as a whole) keeps drag-to-reorder from fighting the row's own
    click-to-select/double-click-to-rename handling over the rest of its
    area."""

    def __init__(self, row: LayerRow) -> None:
        super().__init__()
        self.row = row
        self.setPixmap(icons.icon("fa5s.grip-vertical", color=theme.TEXT_SECONDARY).pixmap(_ICON_SIZE, _ICON_SIZE))
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setFixedWidth(_ICON_SIZE + 4)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.row.panel.begin_drag(self.row)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.row.panel.update_drag(event.globalPosition().toPoint())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.row.panel.end_drag()
        super().mouseReleaseEvent(event)


class LayerRow(QWidget):
    """One row in the layers list: drag handle, type icon, (renameable)
    name, visibility toggle, lock toggle. Selecting/clicking talks to the
    panel rather than the scene directly, so the panel can decide
    replace-vs-toggle semantics.

    `page` and `depth` place this row in the tree: `page` is which page's
    block it lives under (needed to scope reordering to that page -- see
    LayersPanel.end_drag), and `depth` is 1 for an item sitting directly on
    the page and 2+ for a group's nested children, indented one step per
    level. Only depth-1 rows get a drag handle -- reordering inside a group
    isn't supported here, so nested rows render as a plain read-only tree."""

    def __init__(
        self, item: QGraphicsItem, panel: LayersPanel, page: Page, depth: int, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.item = item
        self.panel = panel
        self.page = page
        # Named nesting_depth, not depth -- QWidget inherits QPaintDevice.depth(),
        # a bound method, so an attribute named plainly `depth` would collide with it.
        self.nesting_depth = depth
        self.setObjectName("layerRow")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(_ROW_HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6 + depth * _INDENT_STEP, 2, 4, 2)
        layout.setSpacing(6)

        self._hovering = False
        self._drag_handle: _DragHandle | None = None
        self._drag_handle_effect: QGraphicsOpacityEffect | None = None
        if depth == 1:
            self._drag_handle = _DragHandle(self)
            self._drag_handle_effect = QGraphicsOpacityEffect(self._drag_handle)
            self._drag_handle.setGraphicsEffect(self._drag_handle_effect)
            layout.addWidget(self._drag_handle)
        else:
            spacer = QLabel()
            spacer.setFixedWidth(_ICON_SIZE + 4)
            layout.addWidget(spacer)

        has_children = isinstance(item, QGraphicsItemGroup) and bool(item.childItems())
        if has_children:
            self.expand_btn = QPushButton()
            self.expand_btn.setObjectName("layerToggle")
            self.expand_btn.setFixedSize(_TOGGLE_SIZE, _TOGGLE_SIZE)
            self.expand_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            collapsed = panel.is_group_collapsed(item)
            self.expand_btn.setIcon(icons.icon(_ICON_CHEVRON_RIGHT if collapsed else _ICON_CHEVRON_DOWN, color=theme.TEXT_SECONDARY))
            self.expand_btn.clicked.connect(lambda: panel.toggle_group_collapsed(item))
            layout.addWidget(self.expand_btn)
        else:
            spacer = QLabel()
            spacer.setFixedWidth(_TOGGLE_SIZE)
            layout.addWidget(spacer)

        self.icon_label = QLabel()
        self.icon_label.setPixmap(icons.icon(_icon_for(item), color=theme.TEXT_PRIMARY).pixmap(_ICON_SIZE, _ICON_SIZE))
        layout.addWidget(self.icon_label)

        self.name_label = QLabel(_label_for(item))
        self.name_label.setObjectName("layerName")
        self.name_label.setToolTip(_edit_label_for(item))
        layout.addWidget(self.name_label, 1)

        self.name_edit = _RenameLineEdit()
        self.name_edit.setVisible(False)
        self.name_edit.editingFinished.connect(self._commit_rename)
        layout.addWidget(self.name_edit, 1)

        self.visible_btn = self._toggle_button()
        self._visible_effect = QGraphicsOpacityEffect(self.visible_btn)
        self.visible_btn.setGraphicsEffect(self._visible_effect)
        self.visible_btn.clicked.connect(self._toggle_visible)
        layout.addWidget(self.visible_btn)

        self.lock_btn = self._toggle_button()
        self._lock_effect = QGraphicsOpacityEffect(self.lock_btn)
        self.lock_btn.setGraphicsEffect(self._lock_effect)
        self.lock_btn.clicked.connect(self._toggle_lock)
        layout.addWidget(self.lock_btn)

        # Always attached (rather than added lazily in _refresh_row_state), like the
        # handle/visible/lock effects above -- opacity 1.0 is visually identical to no
        # effect, and this sidesteps setGraphicsEffect(None), which the PySide6 stubs
        # don't type as accepted even though Qt allows it at runtime.
        self._row_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._row_effect)

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
        self._refresh_row_state(locked=locked, hidden=not visible)
        self._refresh_hover_opacity()

    def enterEvent(self, event: QEnterEvent) -> None:
        self._hovering = True
        self._refresh_hover_opacity()
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        self._hovering = False
        self._refresh_hover_opacity()
        super().leaveEvent(event)

    def _refresh_hover_opacity(self) -> None:
        # Reveal-on-hover keeps a row in its default state (visible,
        # unlocked) uncluttered -- the drag handle and the eye/lock buttons
        # only hold permanent screen space once they represent a
        # *non-default* state (hidden or locked) worth noticing at a glance
        # without hovering every row.
        if self._drag_handle_effect is not None:
            self._drag_handle_effect.setOpacity(1.0 if self._hovering else 0.0)
        visible = self.item.isVisible()
        locked = is_layer_locked(self.item)
        self._visible_effect.setOpacity(1.0 if self._hovering or not visible else 0.0)
        self._lock_effect.setOpacity(1.0 if self._hovering or locked else 0.0)

    def _refresh_row_state(self, *, locked: bool, hidden: bool) -> None:
        # Locked items lose ItemIsSelectable everywhere (see
        # items.set_layer_locked), so clicking this row's mousePressEvent is
        # already a no-op for them -- without a visible cue, that no-op
        # looks like the panel is broken. Hidden items stay selectable, so
        # only the dimming (not the cursor/tooltip) applies to them. The
        # drag handle and the visible/lock buttons set their own cursor, so
        # this doesn't affect those still-functional child widgets.
        self.setCursor(Qt.CursorShape.ForbiddenCursor if locked else Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Locked -- unlock to select" if locked else "")
        self._row_effect.setOpacity(0.5 if locked or hidden else 1.0)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        menu = QMenu(self)

        duplicate_action = QAction(icons.icon("fa5s.clone", color=theme.TEXT_PRIMARY), "Duplicate", menu)
        duplicate_action.triggered.connect(lambda: self.panel.viewmodel.duplicate_items([self.item]))
        menu.addAction(duplicate_action)

        locked = is_layer_locked(self.item)
        lock_action = QAction(
            icons.icon("fa5s.unlock" if locked else "fa5s.lock", color=theme.TEXT_PRIMARY),
            "Unlock" if locked else "Lock",
            menu,
        )
        lock_action.triggered.connect(self._toggle_lock)
        menu.addAction(lock_action)

        if self.nesting_depth == 1:
            # z-order is scene-global, but a group child's z-value is local
            # to its parent group -- mixing the two would produce a
            # meaningless jump, so these actions match the drag-to-reorder
            # restriction (see LayersPanel.begin_drag) and only apply to
            # items sitting directly on a page.
            menu.addSeparator()
            scene = self.panel.viewmodel.scene
            front_action = QAction(icons.icon("fa5s.arrow-up", color=theme.TEXT_PRIMARY), "Bring to Front", menu)
            front_action.triggered.connect(lambda: scene.bring_to_front(self.item))
            menu.addAction(front_action)

            forward_action = QAction(icons.icon("fa5s.chevron-up", color=theme.TEXT_PRIMARY), "Bring Forward", menu)
            forward_action.triggered.connect(lambda: scene.step_forward([self.item]))
            menu.addAction(forward_action)

            backward_action = QAction(icons.icon(_ICON_CHEVRON_DOWN, color=theme.TEXT_PRIMARY), "Send Backward", menu)
            backward_action.triggered.connect(lambda: scene.step_backward([self.item]))
            menu.addAction(backward_action)

            back_action = QAction(icons.icon("fa5s.arrow-down", color=theme.TEXT_PRIMARY), "Send to Back", menu)
            back_action.triggered.connect(lambda: scene.send_to_back(self.item))
            menu.addAction(back_action)

        menu.addSeparator()
        delete_action = QAction(icons.icon("fa5s.trash-alt", color=theme.TEXT_PRIMARY), "Delete", menu)
        delete_action.triggered.connect(lambda: self.panel.viewmodel.scene.delete_items([self.item]))
        menu.addAction(delete_action)

        menu.exec(event.globalPos())

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", selected)
        font = self.name_label.font()
        font.setBold(selected)
        self.name_label.setFont(font)
        style = self.style()
        style.unpolish(self)
        style.polish(self)

    def refresh_label(self) -> None:
        self.name_label.setText(_label_for(self.item))
        self.name_label.setToolTip(_edit_label_for(self.item))

    def mousePressEvent(self, event: QMouseEvent) -> None:
        modifiers = event.modifiers()
        toggle = bool(modifiers & Qt.KeyboardModifier.ControlModifier)
        range_select = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)
        self.panel.select_item(self.item, toggle=toggle, range_select=range_select)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        self._start_rename()
        super().mouseDoubleClickEvent(event)

    def _start_rename(self) -> None:
        self.name_edit.start_editing(_edit_label_for(self.item))
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


class PageRow(QWidget):
    """Header row for one page in the Layers tree -- every page is listed
    (not just the active one), so the items nested under it always have a
    parent to render under. Click to make it the active page (see
    EditorViewModel.active_page); double-click to rename; the chevron
    collapses/expands its items without changing which page is active."""

    def __init__(self, page: Page, panel: LayersPanel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.page = page
        self.panel = panel
        self.setObjectName("pageRow")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(_ROW_HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 4, 2)
        layout.setSpacing(6)

        self.expand_btn = QPushButton()
        self.expand_btn.setObjectName("layerToggle")
        self.expand_btn.setFixedSize(_TOGGLE_SIZE, _TOGGLE_SIZE)
        self.expand_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.expand_btn.clicked.connect(lambda: panel.toggle_page_collapsed(page))
        layout.addWidget(self.expand_btn)

        self.icon_label = QLabel()
        self.icon_label.setPixmap(icons.icon("fa5s.file", color=theme.TEXT_PRIMARY).pixmap(_ICON_SIZE, _ICON_SIZE))
        layout.addWidget(self.icon_label)

        self.name_label = QLabel()
        self.name_label.setObjectName("layerName")
        bold_font = self.name_label.font()
        bold_font.setBold(True)
        self.name_label.setFont(bold_font)
        layout.addWidget(self.name_label, 1)

        self.name_edit = _RenameLineEdit()
        self.name_edit.setVisible(False)
        self.name_edit.editingFinished.connect(self._commit_rename)
        layout.addWidget(self.name_edit, 1)

        self.refresh_label()
        self._refresh_expand_icon()

    def _full_name(self) -> str:
        index = self.panel.viewmodel.scene.pages.index(self.page)
        return self.page.name or f"Page {index + 1}"

    def refresh_label(self) -> None:
        full_name = self._full_name()
        self.name_label.setText(_elide(full_name))
        self.name_label.setToolTip(full_name)

    def _refresh_expand_icon(self) -> None:
        collapsed = self.panel.is_page_collapsed(self.page)
        self.expand_btn.setIcon(icons.icon(_ICON_CHEVRON_RIGHT if collapsed else _ICON_CHEVRON_DOWN, color=theme.TEXT_SECONDARY))

    def set_active(self, active: bool) -> None:
        self.setProperty("selected", active)
        style = self.style()
        style.unpolish(self)
        style.polish(self)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.panel.activate_page(self.page)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        self._start_rename()
        super().mouseDoubleClickEvent(event)

    def _start_rename(self) -> None:
        self.name_edit.start_editing(self._full_name())
        self.name_label.setVisible(False)
        self.name_edit.setVisible(True)
        self.name_edit.setFocus()
        self.name_edit.selectAll()

    def _commit_rename(self) -> None:
        if not self.name_edit.isVisible():
            return
        new_name = self.name_edit.text().strip()
        if new_name:
            self.panel.viewmodel.rename_page(self.page, new_name)
        self.name_edit.setVisible(False)
        self.name_label.setVisible(True)
        self.refresh_label()


class LayersPanel(QWidget):
    """Tree of every page in the document, each listing its own items
    front-most first with grouped items nested under their group, and
    keeps the canvas selection in sync in both directions."""

    def __init__(self, viewmodel: EditorViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.viewmodel = viewmodel
        self.setStyleSheet(LAYERS_PANEL_STYLE)
        self._rows: dict[QGraphicsItem, LayerRow] = {}
        self._page_rows: dict[Page, PageRow] = {}
        self._collapsed_pages: set[Page] = set()
        self._collapsed_groups: set[QGraphicsItem] = set()
        self._dragging_row: LayerRow | None = None
        self._drag_subtree: list[LayerRow] = []
        self._range_anchor: QGraphicsItem | None = None

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

        self.empty_hint = QLabel("Nothing in this project yet — add a shape, text, or image to get started.")
        self.empty_hint.setObjectName("hintText")
        self.empty_hint.setWordWrap(True)
        layout.addWidget(self.empty_hint)

    def _items_front_to_back(self, page: Page) -> list[QGraphicsItem]:
        scene = self.viewmodel.scene
        frames = scene.page_frames()
        # Grouped children are reachable only through their group -- listing
        # them separately here would duplicate the group's contents as
        # top-level rows (they're added as nested rows in refresh() instead).
        items = [
            i for i in scene.items()
            # The PySide6 stub types parentItem() as always returning QGraphicsItem,
            # but top-level items really do return None at runtime -- cast so the
            # comparison below isn't flagged as always-false.
            if i not in frames
            and cast("QGraphicsItem | None", i.parentItem()) is None
            and page_for_item(scene.pages, i) is page
        ]
        items.sort(key=lambda i: i.zValue(), reverse=True)
        return items

    def refresh(self) -> None:
        while self.rows_layout.count() > 1:  # keep the trailing stretch
            item = self.rows_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()

        self._rows = {}
        self._page_rows = {}
        for page in self.viewmodel.scene.pages:
            page_row = PageRow(page, self)
            self.rows_layout.insertWidget(self.rows_layout.count() - 1, page_row)
            self._page_rows[page] = page_row
            if page in self._collapsed_pages:
                continue
            for item in self._items_front_to_back(page):
                self._add_item_row(item, page, depth=1)

        self.sync_selection()
        self.empty_hint.setVisible(not self._rows)

    def _add_item_row(self, item: QGraphicsItem, page: Page, depth: int) -> None:
        row = LayerRow(item, self, page, depth)
        self.rows_layout.insertWidget(self.rows_layout.count() - 1, row)
        self._rows[item] = row
        if isinstance(item, QGraphicsItemGroup) and item not in self._collapsed_groups:
            children = sorted(item.childItems(), key=lambda i: i.zValue(), reverse=True)
            for child in children:
                self._add_item_row(child, page, depth + 1)

    def is_page_collapsed(self, page: Page) -> bool:
        return page in self._collapsed_pages

    def is_group_collapsed(self, item: QGraphicsItem) -> bool:
        return item in self._collapsed_groups

    def toggle_page_collapsed(self, page: Page) -> None:
        if page in self._collapsed_pages:
            self._collapsed_pages.discard(page)
        else:
            self._collapsed_pages.add(page)
        self.refresh()

    def toggle_group_collapsed(self, item: QGraphicsItem) -> None:
        if item in self._collapsed_groups:
            self._collapsed_groups.discard(item)
        else:
            self._collapsed_groups.add(item)
        self.refresh()

    def activate_page(self, page: Page) -> None:
        self.viewmodel.set_active_page(page)
        self.sync_selection()

    def sync_selection(self) -> None:
        selected = set(self.viewmodel.scene.selectedItems())
        for item, row in self._rows.items():
            row.set_selected(item in selected)
        active_page = self.viewmodel.active_page
        for page, row in self._page_rows.items():
            row.set_active(page is active_page)

    def select_item(self, item: QGraphicsItem, *, toggle: bool = False, range_select: bool = False) -> None:
        if is_layer_locked(item):
            return
        if range_select and self._range_anchor is not None:
            self._select_range(self._range_anchor, item)
            return
        if toggle:
            item.setSelected(not item.isSelected())
        else:
            self.viewmodel.scene.clearSelection()
            item.setSelected(True)
        # Shift+click extends from the last plain/Ctrl click, Explorer-style
        # -- a range-select itself doesn't move the anchor, so repeated
        # Shift+clicks keep extending/shrinking from the same start point.
        self._range_anchor = item

    def _select_range(self, anchor: QGraphicsItem, target: QGraphicsItem) -> None:
        # Rebuilt fresh by refresh() after every mutation (including drag
        # reorder), so this always matches the current on-screen row order
        # -- including across pages, top to bottom.
        ordered = list(self._rows.keys())
        if anchor not in ordered or target not in ordered:
            return
        start, end = sorted((ordered.index(anchor), ordered.index(target)))
        self.viewmodel.scene.clearSelection()
        for row_item in ordered[start : end + 1]:
            if not is_layer_locked(row_item):
                row_item.setSelected(True)

    # -- drag-to-reorder (see _DragHandle) ---------------------------------
    # Only depth-1 rows (items sitting directly on a page) are draggable,
    # and only among their own page's other depth-1 rows -- z-order is
    # scene-global but reordering across pages or into/out of a group isn't
    # a supported gesture here. A dragged group's nested rows (deeper depth,
    # immediately following it) ride along as one block so the tree doesn't
    # visually separate a group from its own children mid-drag.
    def begin_drag(self, row: LayerRow) -> None:
        # A locked item can't be moved on canvas either (ItemIsMovable is
        # cleared -- see items.set_layer_locked), so letting its z-order
        # change via panel drag would be an inconsistent backdoor.
        if row.nesting_depth != 1 or is_layer_locked(row.item):
            return
        self._dragging_row = row
        self._drag_subtree = self._subtree_widgets(row)
        row.setCursor(Qt.CursorShape.ClosedHandCursor)

    def _subtree_widgets(self, row: LayerRow) -> list[LayerRow]:
        widgets = [row]
        index = self.rows_layout.indexOf(row)
        count = self.rows_layout.count() - 1  # exclude trailing stretch
        for i in range(index + 1, count):
            widget = self.rows_layout.itemAt(i).widget()
            if not isinstance(widget, LayerRow) or widget.nesting_depth <= row.nesting_depth:
                break
            widgets.append(widget)
        return widgets

    def update_drag(self, global_pos: QPoint) -> None:
        row = self._dragging_row
        if row is None:
            return
        local_y = self.rows_container.mapFromGlobal(global_pos).y()
        target_index = self._index_for_y(local_y, row)
        subtree = self._drag_subtree
        current_index = self.rows_layout.indexOf(subtree[0])
        if target_index != -1 and target_index != current_index:
            for widget in subtree:
                self.rows_layout.removeWidget(widget)
            for offset, widget in enumerate(subtree):
                self.rows_layout.insertWidget(target_index + offset, widget)

    def _index_for_y(self, y: int, row: LayerRow) -> int:
        dragged_ids = {id(widget) for widget in self._drag_subtree}
        count = self.rows_layout.count() - 1  # exclude trailing stretch
        fallback = self.rows_layout.indexOf(self._page_rows[row.page]) + 1
        for i in range(count):
            widget = self.rows_layout.itemAt(i).widget()
            if id(widget) in dragged_ids:
                continue
            if not (isinstance(widget, LayerRow) and widget.nesting_depth == 1 and widget.page is row.page):
                continue
            midpoint = widget.geometry().y() + widget.geometry().height() / 2
            if y < midpoint:
                return i
            fallback = i + 1
        return fallback

    def end_drag(self) -> None:
        row = self._dragging_row
        self._dragging_row = None
        self._drag_subtree = []
        if row is None:
            return
        row.unsetCursor()
        new_order = [
            widget.item
            for i in range(self.rows_layout.count() - 1)
            if isinstance(widget := self.rows_layout.itemAt(i).widget(), LayerRow)
            and widget.nesting_depth == 1 and widget.page is row.page
        ]
        self._apply_new_order(row.page, new_order)

    def _apply_new_order(self, page: Page, new_order: list[QGraphicsItem]) -> None:
        """Assigns fresh, strictly-ordered z-values matching `new_order`.
        Items commonly share the same (default 0) z-value -- Qt then breaks
        the tie by insertion order, not a value this panel can read back --
        so redistributing the *existing* z-value set across the new order
        can silently no-op. New values are picked just above every other
        page's max z instead (z-order is scene-global, not page-scoped --
        see DesignScene.bring_to_front), which also has the reasonable side
        effect of bringing the reordered page's items to the very front."""
        old_order = self._items_front_to_back(page)
        if new_order == old_order:
            self.refresh()  # snaps any half-dragged widget back into place
            return
        frames = self.viewmodel.scene.page_frames()
        others_z = [
            i.zValue() for i in self.viewmodel.scene.items()
            if i not in frames and i not in old_order
        ]
        base = max(others_z) + 1 if others_z else 0.0
        old_z = {item: item.zValue() for item in old_order}
        new_z = {item: base + (len(new_order) - 1 - i) for i, item in enumerate(new_order)}

        def undo() -> None:
            for item, z in old_z.items():
                item.setZValue(z)
            self.refresh()

        def redo() -> None:
            for item, z in new_z.items():
                item.setZValue(z)
            self.refresh()

        redo()
        self.viewmodel.scene.undo_stack.push(undo, redo)
