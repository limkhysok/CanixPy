from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QMimeData, QPointF, QSize, Qt
from PySide6.QtGui import QColor, QDrag, QFont
from PySide6.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from src.core import icons, theme
from src.core.fonts import default_font_family
from src.core.image_loader import IMPORT_FILE_FILTER
from src.features.editor.canvas import items
from src.features.editor.canvas.items import RotatableTextItem
from src.features.editor.viewmodels.properties_viewmodel import PropertiesPanelViewModel
from src.features.editor.views.layout.layers_panel import LayersPanel

if TYPE_CHECKING:
    from src.features.editor.viewmodels.editor_viewmodel import EditorViewModel

LEFT_SIDEBAR_STYLE = theme.load_qss(Path(__file__).with_name("left_sidebar.qss"))

FONT_ICON = "fa5s.font"

SHAPE_ICONS = {
    "Rectangle": "fa5s.square",
    "Circle": "fa5s.circle",
    "Line": "fa5s.grip-lines",
    "Triangle": "fa5s.play",
    "Diamond": "fa5s.gem",
    "Star": "fa5s.star",
    "Arrow": "fa5s.long-arrow-alt-right",
    "Text Box": FONT_ICON,
}

# (label, icon name) for each nav-rail entry, in the order they're shown.
# "Elements", "Layers", "Texts", and "Upload" have real panels wired up below;
# the rest render a "coming soon" placeholder until their features exist.
NAV_ITEMS: list[tuple[str, str]] = [
    ("Templates", "fa5s.clone"),
    ("Elements", "fa5s.shapes"),
    ("Layers", "fa5s.layer-group"),
    ("Texts", FONT_ICON),
    ("Brand", "fa5s.paint-brush"),
    ("Upload", "fa5s.upload"),
    ("Tools", "fa5s.tools"),
    ("Projects", "fa5s.folder-open"),
    ("Apps", "fa5s.th-large"),
    ("Magic Media", "fa5s.magic"),
    ("Google Drive", "fa5b.google-drive"),
]

# (button label, inserted text, font size, bold) for each quick-insert
# preset shown on the Texts panel.
TEXT_PRESETS: list[tuple[str, str, int, bool]] = [
    ("Add a heading", "Add a heading", 32, True),
    ("Add a subheading", "Add a subheading", 22, True),
    ("Add body text", "Add a little bit of body text", 16, False),
]

RAIL_WIDTH = 72


def _section_header(text: str) -> QWidget:
    row = QWidget()
    row_layout = QHBoxLayout(row)
    row_layout.setContentsMargins(0, 0, 0, 0)
    row_layout.setSpacing(6)
    text_label = QLabel(text.upper())
    text_label.setObjectName("sectionHeader")
    row_layout.addWidget(text_label)
    row_layout.addStretch()
    return row


def _clear_qlayout(layout: QLayout) -> None:
    # See right_sidebar.py's identical helper -- takeAt() detaches
    # immediately and nested button-row layouts need recursing into too,
    # otherwise their child widgets stay floating on screen post-rebuild.
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget:
            widget.hide()
            widget.setParent(None)
            widget.deleteLater()
        elif item.layout():
            _clear_qlayout(item.layout())


class DraggableListWidget(QListWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        # Capped (not unlimited) height -- it's a static palette, not a
        # growing list, so it shouldn't compete with the Layers list below
        # for vertical space; it scrolls internally once it outgrows this.
        self.setMaximumHeight(200)
        for shape in SHAPE_ICONS:
            self.add_shape_item(shape)

    def add_shape_item(self, text: str) -> None:
        item = QListWidgetItem(icons.icon(SHAPE_ICONS[text]), text, self)
        item.setSizeHint(QSize(80, 40))
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

    def startDrag(self, supported_actions: Qt.DropAction) -> None:
        item = self.currentItem()
        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setText(item.text())
        drag.setMimeData(mime_data)
        drag.exec(Qt.DropAction.CopyAction)


class _PlaceholderPanel(QWidget):
    """Shown for rail sections that don't have a feature built yet."""

    def __init__(self, title: str, icon_name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addStretch()

        icon_label = QLabel()
        icon_label.setPixmap(icons.icon(icon_name, color=theme.TEXT_SECONDARY).pixmap(36, 36))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)

        text_label = QLabel(f"{title} coming soon")
        text_label.setObjectName("placeholderText")
        text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(text_label)

        layout.addStretch()


class NavRailButton(QToolButton):
    def __init__(self, label: str, icon_name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._icon_name = icon_name
        self.setObjectName("navRailButton")
        self.setText(label)
        self.setIconSize(QSize(18, 18))
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedWidth(RAIL_WIDTH)
        self.toggled.connect(self._update_icon_color)
        self._update_icon_color(False)

    def _update_icon_color(self, checked: bool) -> None:
        color = theme.ACCENT_PRESSED if checked else theme.TEXT_SECONDARY
        self.setIcon(icons.icon(self._icon_name, color=color))


# Wrap the nav rail and the swappable content panel into a clean Sidebar Widget
class LeftSidebar(QWidget):
    def __init__(self, viewmodel: EditorViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.viewmodel = viewmodel
        # Item-property mutation helpers (same class right_sidebar.py's
        # Properties panel uses) -- reused here so "apply saved style" goes
        # through the one grouped, undo-tracked mutation path rather than
        # left_sidebar reaching into item internals directly.
        self._properties_vm = PropertiesPanelViewModel()
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(LEFT_SIDEBAR_STYLE)

        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        rail = QWidget()
        rail.setObjectName("navRail")
        rail.setFixedWidth(RAIL_WIDTH)
        rail_layout = QVBoxLayout(rail)
        rail_layout.setContentsMargins(0, 12, 0, 12)
        rail_layout.setSpacing(2)

        self.stack = QStackedWidget()
        self.stack.setObjectName("sidebarStack")

        page_builders = {
            "Elements": self._build_elements_page,
            "Layers": self._build_layers_page,
            "Texts": self._build_texts_page,
            "Upload": self._build_upload_page,
        }

        self._button_group = QButtonGroup(self)
        self._button_group.setExclusive(True)

        default_button: NavRailButton | None = None
        for label, icon_name in NAV_ITEMS:
            builder = page_builders.get(label)
            page = builder() if builder else _PlaceholderPanel(label, icon_name)
            index = self.stack.addWidget(page)

            button = NavRailButton(label, icon_name)
            self._button_group.addButton(button, index)
            button.clicked.connect(lambda _checked, i=index: self.stack.setCurrentIndex(i))
            rail_layout.addWidget(button)
            if label == "Elements":
                default_button = button

        rail_layout.addStretch()

        root_layout.addWidget(rail)
        root_layout.addWidget(self.stack, 1)

        if default_button is not None:
            default_button.setChecked(True)
            self.stack.setCurrentIndex(self._button_group.id(default_button))

    def _build_elements_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)
        layout.addWidget(_section_header("Shapes"))
        self.drag_list = DraggableListWidget()
        layout.addWidget(self.drag_list)
        layout.addStretch()
        return page

    def _build_layers_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)
        layout.addWidget(_section_header("Layers"))
        self.layers_panel = LayersPanel(self.viewmodel)
        layout.addWidget(self.layers_panel, 1)
        return page

    def _build_texts_page(self) -> QWidget:
        page = QWidget()
        self.texts_layout = QVBoxLayout(page)
        self.texts_layout.setContentsMargins(16, 16, 16, 16)
        self.texts_layout.setSpacing(8)
        self._populate_texts_page()
        return page

    def refresh_texts_panel(self) -> None:
        """Rebuilds the Texts page in place -- called whenever saved styles
        or the selection change (see EditorView.refresh_editor_panels /
        sync_editor_selection), since the "Save current style as..." button's
        enabled state and the Saved Styles list both depend on that."""
        if hasattr(self, "texts_layout"):
            self._populate_texts_page()

    def _populate_texts_page(self) -> None:
        _clear_qlayout(self.texts_layout)

        self.texts_layout.addWidget(_section_header("Text Styles"))
        for button_label, text, size, bold in TEXT_PRESETS:
            btn = QPushButton(icons.icon(FONT_ICON), button_label)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(
                lambda _checked=False, t=text, s=size, b=bold: self.add_text_preset(t, s, b)
            )
            self.texts_layout.addWidget(btn)

        self.texts_layout.addSpacing(8)
        self.texts_layout.addWidget(_section_header("Saved Styles"))
        if not self.viewmodel.text_styles:
            hint = QLabel("No saved styles yet -- select a text box and use \"Save current style as...\" below.")
            hint.setObjectName("placeholderText")
            hint.setWordWrap(True)
            self.texts_layout.addWidget(hint)
        for index, style in enumerate(self.viewmodel.text_styles):
            row = QHBoxLayout()
            btn = QPushButton(icons.icon(FONT_ICON), style.get("name", "Style"))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _checked=False, s=style: self.apply_text_style(s))
            row.addWidget(btn, 1)
            btn_delete = QToolButton()
            btn_delete.setIcon(icons.icon("fa5s.times", color=theme.TEXT_SECONDARY))
            btn_delete.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_delete.setToolTip("Delete style")
            btn_delete.clicked.connect(lambda _checked=False, i=index: self.delete_text_style(i))
            row.addWidget(btn_delete)
            self.texts_layout.addLayout(row)

        self.texts_layout.addSpacing(8)
        btn_save = QPushButton(icons.icon("fa5s.save"), "Save current style as...")
        btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save.setEnabled(self._single_selected_text_item() is not None)
        btn_save.clicked.connect(self.save_current_style)
        self.texts_layout.addWidget(btn_save)

        self.texts_layout.addStretch()

    def _single_selected_text_item(self) -> RotatableTextItem | None:
        selected = self.viewmodel.scene.selectedItems()
        if len(selected) == 1 and isinstance(selected[0], RotatableTextItem):
            return selected[0]
        return None

    def _active_page_center(self) -> QPointF:
        # Center of the active page -- not a fixed scene point, since with
        # multiple pages stacked in one scrollable canvas that could land
        # the item on whichever page happens to sit at that coordinate.
        page = self.viewmodel.active_page
        return QPointF(page.x_offset + page.width / 2, page.y_offset + page.height / 2)

    def add_text_preset(self, text: str, size: int, bold: bool) -> None:
        font = QFont(default_font_family(), size)
        font.setBold(bold)
        self.viewmodel.scene.add_text_item(text, self._active_page_center(), font)

    def apply_text_style(self, style: dict[str, Any]) -> None:
        item = self._single_selected_text_item()
        if item is not None:
            self._properties_vm.apply_text_style(item, style, self.viewmodel.scene.undo_stack)
            return
        # No text selected -- insert a new text item carrying the style,
        # same drop point as a preset (see add_text_preset above).
        font = QFont(style.get("font_family", default_font_family()), style.get("font_size", 16))
        font.setBold(style.get("bold", False))
        font.setItalic(style.get("italic", False))
        font.setUnderline(style.get("underline", False))
        color = QColor(style.get("color", "#2c3e50"))
        new_item = self.viewmodel.scene.add_text_item(
            "Double Click to Edit", self._active_page_center(), font, color
        )
        items.set_text_letter_spacing(new_item, style.get("letter_spacing", 0.0))
        items.set_text_line_height(new_item, style.get("line_height", 100.0))

    def save_current_style(self) -> None:
        item = self._single_selected_text_item()
        if item is None:
            return
        name, ok = QInputDialog.getText(self, "Save Text Style", "Style name:")
        name = name.strip()
        if not ok or not name:
            return
        font = item.font()
        style = {
            "name": name,
            "font_family": font.family(),
            "font_size": font.pointSize(),
            "bold": font.bold(),
            "italic": font.italic(),
            "underline": font.underline(),
            "color": item.defaultTextColor().name(),
            "letter_spacing": items.get_text_letter_spacing(item),
            "line_height": items.get_text_line_height(item),
        }
        self.viewmodel.add_text_style(style)
        self._populate_texts_page()

    def delete_text_style(self, index: int) -> None:
        self.viewmodel.remove_text_style(index)
        self._populate_texts_page()

    def _build_upload_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)
        layout.addWidget(_section_header("Media Assets"))
        btn_upload = QPushButton(icons.icon("fa5s.image"), "Upload Image")
        btn_upload.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_upload.clicked.connect(self.trigger_image_upload)
        layout.addWidget(btn_upload)
        layout.addStretch()
        return page

    def trigger_image_upload(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Local Image Asset",
            "",
            IMPORT_FILE_FILTER,
        )
        if file_path:
            # Center of the active page -- see add_text_preset's comment.
            active_page = self.viewmodel.active_page
            center_point = QPointF(
                active_page.x_offset + active_page.width / 2, active_page.y_offset + active_page.height / 2
            )
            self.viewmodel.scene.add_image_item(file_path, center_point)
