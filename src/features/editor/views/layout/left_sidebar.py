from __future__ import annotations
from pathlib import Path
from typing import TYPE_CHECKING
from PySide6.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt, QSize, QPointF, QMimeData
from PySide6.QtGui import QDrag, QFont
from src.core import icons, theme
from src.core.image_loader import IMPORT_FILE_FILTER
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
    def __init__(self, viewmodel: "EditorViewModel", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.viewmodel = viewmodel
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
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)
        layout.addWidget(_section_header("Text Styles"))
        for button_label, text, size, bold in TEXT_PRESETS:
            btn = QPushButton(icons.icon(FONT_ICON), button_label)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(
                lambda _checked=False, t=text, s=size, b=bold: self.add_text_preset(t, s, b)
            )
            layout.addWidget(btn)
        layout.addStretch()
        return page

    def add_text_preset(self, text: str, size: int, bold: bool) -> None:
        font = QFont("Arial", size)
        font.setBold(bold)
        # Center of the active page -- not a fixed scene point, since with
        # multiple pages stacked in one scrollable canvas that could land
        # the item on whichever page happens to sit at that coordinate.
        page = self.viewmodel.active_page
        center_point = QPointF(page.x_offset + page.width / 2, page.y_offset + page.height / 2)
        self.viewmodel.scene.add_text_item(text, center_point, font)

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
