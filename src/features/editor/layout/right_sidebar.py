from __future__ import annotations
from pathlib import Path
from typing import TYPE_CHECKING
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLayout, QCheckBox, QLabel, QPushButton, QFontComboBox, QSlider, QSpinBox
from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsEllipseItem, QGraphicsTextItem, QGraphicsItem, QGraphicsItemGroup
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from src.core import icons, theme
from src.features.editor.properties_viewmodel import PropertiesPanelViewModel

if TYPE_CHECKING:
    from src.features.editor.editor_view import CoreDesignApp

RIGHT_SIDEBAR_STYLE = theme.load_qss(Path(__file__).with_name("right_sidebar.qss"))

ICON_PALETTE = "fa5s.palette"
ICON_ALIGN_LEFT = "fa5s.align-left"
ICON_ALIGN_CENTER = "fa5s.align-center"

# Fixed, not left to the layout's stretch factor -- different item types
# (image vs. text vs. shape) populate main_layout with different content, and
# a stretch-driven width follows whatever that content's minimum size needs
# on each rebuild, visibly resizing the whole column every time the
# selection changes.
PANEL_WIDTH = 300

SECTION_ICONS = {
    "Group": "fa5s.object-group",
    "Shape Styling": ICON_PALETTE,
    "Stroke": "fa5s.pen",
    "Font Family": "fa5s.font",
    "Font Size": "fa5s.text-height",
    "Style": "fa5s.bold",
    "Text Alignment": ICON_ALIGN_LEFT,
    "Arrangement": "fa5s.layer-group",
    "Distribute": "fa5s.arrows-alt-h",
    "Effects": "fa5s.magic",
    "Align to Page": ICON_ALIGN_CENTER,
    "Align Selection": ICON_ALIGN_CENTER,
}

def _clear_qlayout(layout: QLayout) -> None:
    # takeAt() detaches the item from the layout immediately; deleteLater()
    # alone would leave stale widgets rendered until the next event-loop turn.
    # Items added via addLayout() (the button rows below) come back with
    # item.widget() == None -- their child widgets live on as un-laid-out,
    # still-visible children of the panel unless we recurse into the nested
    # layout too, which used to leave old icon buttons floating on screen,
    # overlapping the freshly rebuilt rows.
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget:
            widget.hide()
            widget.setParent(None)
            widget.deleteLater()
        elif item.layout():
            _clear_qlayout(item.layout())

def _section_header(text: str) -> QWidget:
    row = QWidget()
    row_layout = QHBoxLayout(row)
    row_layout.setContentsMargins(0, 0, 0, 0)
    row_layout.setSpacing(6)

    icon_name = SECTION_ICONS.get(text)
    if icon_name:
        icon_label = QLabel()
        icon_label.setPixmap(icons.icon(icon_name, color=theme.ACCENT).pixmap(12, 12))
        row_layout.addWidget(icon_label)

    text_label = QLabel(text.upper())
    text_label.setObjectName("sectionHeader")
    row_layout.addWidget(text_label)
    row_layout.addStretch()
    return row

def _button(icon_name: str, text: str) -> QPushButton:
    btn = QPushButton(icons.icon(icon_name, color=theme.TEXT_PRIMARY), text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    if not text:
        # No label -- a compact square icon button (style/alignment rows)
        # rather than the wide, text-padded default.
        btn.setObjectName("iconButton")
    return btn

def _text_button(text: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    return btn

def _toggle_button(icon_name: str, tooltip: str, checked: bool) -> QPushButton:
    btn = QPushButton(icons.icon(icon_name, color=theme.TEXT_PRIMARY), "")
    btn.setObjectName("toggleButton")
    btn.setToolTip(tooltip)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setCheckable(True)
    btn.setChecked(checked)
    return btn

class PropertiesPanel(QWidget):
    def __init__(self, main_app: "CoreDesignApp", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.main_app = main_app
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(RIGHT_SIDEBAR_STYLE)
        self.setFixedWidth(PANEL_WIDTH)
        self.viewmodel = PropertiesPanelViewModel()

        # Outer layout spans the whole widget (so the border-left runs the full
        # column height); dynamic inspector content lives in the nested
        # main_layout, which clear_layout()/inspect_selection() rebuild in place.
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(16, 16, 16, 16)
        outer_layout.setSpacing(8)

        title_row = QWidget()
        title_layout = QHBoxLayout(title_row)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(8)
        title_icon = QLabel()
        title_icon.setPixmap(icons.icon("fa5s.sliders-h", color=theme.ACCENT).pixmap(16, 16))
        title_layout.addWidget(title_icon)
        title = QLabel("Properties")
        title.setObjectName("panelTitle")
        title_layout.addWidget(title)
        title_layout.addStretch()
        outer_layout.addWidget(title_row)

        self.main_layout = QVBoxLayout()
        self.main_layout.setSpacing(8)
        outer_layout.addLayout(self.main_layout)
        outer_layout.addStretch()

        self.show_empty_state()

    def show_empty_state(self) -> None:
        self.clear_layout()
        hint = QLabel("Select an item on the canvas to edit its properties.")
        hint.setObjectName("hintText")
        hint.setWordWrap(True)
        self.main_layout.addWidget(hint)

    def clear_layout(self) -> None:
        _clear_qlayout(self.main_layout)

    def inspect_selection(self, items: list[QGraphicsItem]) -> None:
        self.clear_layout()
        page_frame = getattr(self.main_app.scene, "page_frame", None)
        real_items = [i for i in items if i != page_frame]

        if not real_items:
            self.show_empty_state()
        elif len(real_items) == 1:
            self._inspect_single(real_items[0])
        else:
            self._inspect_multi(real_items)

    # Kept for compatibility with anything still calling the old single-item entry point.
    def inspect_item(self, item: QGraphicsItem | None) -> None:
        self.inspect_selection([item] if item else [])

    def _inspect_single(self, item: QGraphicsItem) -> None:
        # 1. Custom settings depending on type
        if isinstance(item, QGraphicsItemGroup):
            btn_ungroup = _button("fa5s.object-ungroup", "Ungroup")
            btn_ungroup.clicked.connect(lambda: self.main_app.scene.ungroup_items([item]))
            self.main_layout.addWidget(_section_header("Group"))
            self.main_layout.addWidget(btn_ungroup)

        elif isinstance(item, (QGraphicsRectItem, QGraphicsEllipseItem)):
            self.main_layout.addWidget(_section_header("Shape Styling"))

            btn_color = _button(ICON_PALETTE, "Change Color")
            btn_color.clicked.connect(lambda: self.viewmodel.change_shape_color(item, self.main_app.scene.undo_stack))
            self.main_layout.addWidget(btn_color)

            btn_gradient = _button("fa5s.fill-drip", "Add Gradient")
            btn_gradient.clicked.connect(lambda: self.viewmodel.apply_gradient_fill(item, self.main_app.scene.undo_stack))
            self.main_layout.addWidget(btn_gradient)

            self.main_layout.addWidget(_section_header("Stroke"))
            btn_stroke_color = _button("fa5s.pen", "Stroke Color")
            btn_stroke_color.clicked.connect(lambda: self.viewmodel.change_stroke_color(item, self.main_app.scene.undo_stack))
            self.main_layout.addWidget(btn_stroke_color)

            stroke_width = QSpinBox()
            stroke_width.setRange(0, 40)
            stroke_width.setValue(item.pen().width())
            stroke_width.setSuffix(" px")
            def on_stroke_width_changed(width: int) -> None:
                self.viewmodel.set_stroke_width(item, width, self.main_app.scene.undo_stack)
            stroke_width.valueChanged.connect(on_stroke_width_changed)
            self.main_layout.addWidget(stroke_width)

        elif isinstance(item, QGraphicsTextItem):
            self.main_layout.addWidget(_section_header("Font Family"))
            font_box = QFontComboBox()
            font_box.setCursor(Qt.CursorShape.PointingHandCursor)
            font_box.setCurrentFont(item.font())

            def on_font_changed(font: QFont) -> None:
                self.viewmodel.change_text_font(item, font, self.main_app.scene.undo_stack)
            font_box.currentFontChanged.connect(on_font_changed)
            self.main_layout.addWidget(font_box)

            self.main_layout.addWidget(_section_header("Font Size"))
            size_box = QSpinBox()
            size_box.setRange(8, 120)
            size_box.setValue(item.font().pointSize())

            def on_size_changed(size: int) -> None:
                self.viewmodel.change_text_size(item, size, self.main_app.scene.undo_stack)
            size_box.valueChanged.connect(on_size_changed)
            self.main_layout.addWidget(size_box)

            btn_color = _button(ICON_PALETTE, "Text Color")
            btn_color.clicked.connect(lambda: self.viewmodel.change_text_color(item, self.main_app.scene.undo_stack))
            self.main_layout.addWidget(btn_color)

            self.main_layout.addWidget(_section_header("Style"))
            font = item.font()
            btn_bold = _toggle_button("fa5s.bold", "Bold", font.bold())
            btn_italic = _toggle_button("fa5s.italic", "Italic", font.italic())
            btn_underline = _toggle_button("fa5s.underline", "Underline", font.underline())
            def on_bold_toggled(on: bool) -> None:
                self.viewmodel.toggle_text_bold(item, on, self.main_app.scene.undo_stack)
            def on_italic_toggled(on: bool) -> None:
                self.viewmodel.toggle_text_italic(item, on, self.main_app.scene.undo_stack)
            def on_underline_toggled(on: bool) -> None:
                self.viewmodel.toggle_text_underline(item, on, self.main_app.scene.undo_stack)
            btn_bold.toggled.connect(on_bold_toggled)
            btn_italic.toggled.connect(on_italic_toggled)
            btn_underline.toggled.connect(on_underline_toggled)
            style_row = QHBoxLayout()
            style_row.addWidget(btn_bold)
            style_row.addWidget(btn_italic)
            style_row.addWidget(btn_underline)
            self.main_layout.addLayout(style_row)

            self.main_layout.addSpacing(8)
            self.main_layout.addWidget(_section_header("Text Alignment"))
            align_row = QHBoxLayout()
            align_options = (
                (ICON_ALIGN_LEFT, "Align Left", Qt.AlignmentFlag.AlignLeft),
                (ICON_ALIGN_CENTER, "Align Center", Qt.AlignmentFlag.AlignHCenter),
                ("fa5s.align-right", "Align Right", Qt.AlignmentFlag.AlignRight),
                ("fa5s.align-justify", "Justify", Qt.AlignmentFlag.AlignJustify),
            )
            for icon_name, tooltip, alignment in align_options:
                btn = _button(icon_name, "")
                btn.setToolTip(tooltip)
                btn.clicked.connect(
                    lambda _checked=False, a=alignment: self.viewmodel.set_text_alignment(item, a, self.main_app.scene.undo_stack)
                )
                align_row.addWidget(btn)
            self.main_layout.addLayout(align_row)

        # 2. Effects (opacity + shadow, available for every item type)
        self.main_layout.addSpacing(8)
        self._add_effects_section([item])

        # 3. Align to page (only one item selected, so "the page" is the obvious reference)
        self.main_layout.addSpacing(8)
        self._add_align_section(single_item=True)

        # 4. Arrangement (available for all items)
        self.main_layout.addSpacing(8)
        self.main_layout.addWidget(_section_header("Arrangement"))

        btn_front = _button("fa5s.arrow-up", "Bring to Front")
        btn_front.clicked.connect(lambda: self.main_app.scene.bring_to_front(item))
        self.main_layout.addWidget(btn_front)

        btn_back = _button("fa5s.arrow-down", "Send to Back")
        btn_back.clicked.connect(lambda: self.main_app.scene.send_to_back(item))
        self.main_layout.addWidget(btn_back)

    def _inspect_multi(self, items: list[QGraphicsItem]) -> None:
        count_label = QLabel(f"{len(items)} items selected")
        count_label.setObjectName("hintText")
        self.main_layout.addWidget(count_label)

        self.main_layout.addSpacing(8)
        self._add_effects_section(items)

        self.main_layout.addSpacing(8)
        self._add_align_section(single_item=False)

        self.main_layout.addSpacing(8)
        self.main_layout.addWidget(_section_header("Distribute"))
        btn_dist_h = _button("fa5s.grip-lines-vertical", "Horizontally")
        btn_dist_v = _button("fa5s.grip-lines", "Vertically")
        btn_dist_h.clicked.connect(lambda: self.main_app.scene.distribute_items("horizontal"))
        btn_dist_v.clicked.connect(lambda: self.main_app.scene.distribute_items("vertical"))
        if len(items) < 3:
            btn_dist_h.setEnabled(False)
            btn_dist_v.setEnabled(False)
            btn_dist_h.setToolTip("Needs 3+ items")
            btn_dist_v.setToolTip("Needs 3+ items")
        dist_row = QHBoxLayout()
        dist_row.addWidget(btn_dist_h)
        dist_row.addWidget(btn_dist_v)
        self.main_layout.addLayout(dist_row)

        self.main_layout.addSpacing(8)
        self.main_layout.addWidget(_section_header("Arrangement"))

        btn_front = _button("fa5s.arrow-up", "Bring to Front")
        btn_front.clicked.connect(lambda: self.main_app.scene.bring_items_to_front(items))
        self.main_layout.addWidget(btn_front)

        btn_back = _button("fa5s.arrow-down", "Send to Back")
        btn_back.clicked.connect(lambda: self.main_app.scene.send_items_to_back(items))
        self.main_layout.addWidget(btn_back)

        btn_group = _button("fa5s.object-group", "Group")
        btn_group.clicked.connect(lambda: self.main_app.scene.group_items(items))
        self.main_layout.addWidget(btn_group)

    def _add_effects_section(self, items: list[QGraphicsItem]) -> None:
        self.main_layout.addWidget(_section_header("Effects"))

        opacity_label = QLabel("Opacity")
        opacity_label.setObjectName("hintText")
        self.main_layout.addWidget(opacity_label)

        opacity_slider = QSlider(Qt.Orientation.Horizontal)
        opacity_slider.setRange(0, 100)
        opacity_slider.setValue(round(items[0].opacity() * 100))
        opacity_slider.setCursor(Qt.CursorShape.PointingHandCursor)

        def on_opacity_changed(value: int) -> None:
            fraction = value / 100.0
            if len(items) == 1:
                self.viewmodel.set_opacity(items[0], fraction, self.main_app.scene.undo_stack)
            else:
                self.viewmodel.set_opacity_multi(items, fraction, self.main_app.scene.undo_stack)
        opacity_slider.valueChanged.connect(on_opacity_changed)
        self.main_layout.addWidget(opacity_slider)

        shadow_checkbox = QCheckBox("Drop Shadow")
        shadow_checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        shadow_checkbox.setChecked(items[0].graphicsEffect() is not None)  # type: ignore[reportUnnecessaryComparison]

        def on_shadow_toggled(checked: bool) -> None:
            if len(items) == 1:
                self.viewmodel.toggle_shadow(items[0], checked, self.main_app.scene.undo_stack)
            else:
                self.viewmodel.toggle_shadow_multi(items, checked, self.main_app.scene.undo_stack)
        shadow_checkbox.toggled.connect(on_shadow_toggled)
        self.main_layout.addWidget(shadow_checkbox)

    def _add_align_section(self, single_item: bool) -> None:
        label = "Align to Page" if single_item else "Align Selection"
        self.main_layout.addWidget(_section_header(label))

        h_icons = {"left": ICON_ALIGN_LEFT, "h_center": ICON_ALIGN_CENTER, "right": "fa5s.align-right"}
        h_row = QHBoxLayout()
        for edge, tooltip in (("left", "Align Left"), ("h_center", "Align Center"), ("right", "Align Right")):
            btn = _button(h_icons[edge], "")
            btn.setToolTip(tooltip)
            btn.clicked.connect(lambda _checked=False, e=edge: self.main_app.scene.align_items(e))
            h_row.addWidget(btn)
        self.main_layout.addLayout(h_row)

        v_row = QHBoxLayout()
        for edge, label_text, tooltip in (
            ("top", "Top", "Align Top"),
            ("v_center", "Middle", "Align Middle"),
            ("bottom", "Bottom", "Align Bottom"),
        ):
            btn = _text_button(label_text)
            btn.setToolTip(tooltip)
            btn.clicked.connect(lambda _checked=False, e=edge: self.main_app.scene.align_items(e))
            v_row.addWidget(btn)
        self.main_layout.addLayout(v_row)
