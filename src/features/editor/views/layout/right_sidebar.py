from __future__ import annotations
from pathlib import Path
from typing import TYPE_CHECKING
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLayout, QCheckBox, QLabel, QPushButton, QFontComboBox, QSlider, QSpinBox
from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsEllipseItem, QGraphicsTextItem, QGraphicsItem, QGraphicsItemGroup
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from src.core import icons, theme
from src.features.editor.canvas.items import MIN_SIZE, can_edit_height, get_item_size, is_aspect_locked
from src.features.editor.canvas.page import PAGE_MIN_SIZE
from src.features.editor.viewmodels.properties_viewmodel import PropertiesPanelViewModel

if TYPE_CHECKING:
    from src.features.editor.canvas.page import Page
    from src.features.editor.canvas.scene import DesignScene
    from src.features.editor.viewmodels.editor_viewmodel import EditorViewModel

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
    "Position & Size": "fa5s.arrows-alt",
    "Page": "fa5s.file-image",
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
    def __init__(self, editor_viewmodel: "EditorViewModel", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # Two different viewmodels in play: `editor_viewmodel` (document
        # state -- the scene) vs. `self.viewmodel` (item-property mutation
        # helpers, PropertiesPanelViewModel -- see viewmodels/properties_viewmodel.py).
        self.editor_viewmodel = editor_viewmodel
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
        frames = self.editor_viewmodel.scene.page_frames()
        real_items = [i for i in items if i not in frames]

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
        # 1. Position & size (every item has X/Y; W/H only for items with an
        # independent size -- see _add_transform_section)
        self._add_transform_section(item)
        self.main_layout.addSpacing(8)

        # 2. Custom settings depending on type
        if isinstance(item, QGraphicsItemGroup):
            btn_ungroup = _button("fa5s.object-ungroup", "Ungroup")
            btn_ungroup.clicked.connect(lambda: self.editor_viewmodel.scene.ungroup_items([item]))
            self.main_layout.addWidget(_section_header("Group"))
            self.main_layout.addWidget(btn_ungroup)

        elif isinstance(item, (QGraphicsRectItem, QGraphicsEllipseItem)):
            self.main_layout.addWidget(_section_header("Shape Styling"))

            btn_color = _button(ICON_PALETTE, "Change Color")
            btn_color.clicked.connect(lambda: self.viewmodel.change_shape_color(item, self.editor_viewmodel.scene.undo_stack))
            self.main_layout.addWidget(btn_color)

            btn_gradient = _button("fa5s.fill-drip", "Add Gradient")
            btn_gradient.clicked.connect(lambda: self.viewmodel.apply_gradient_fill(item, self.editor_viewmodel.scene.undo_stack))
            self.main_layout.addWidget(btn_gradient)

            self.main_layout.addWidget(_section_header("Stroke"))
            btn_stroke_color = _button("fa5s.pen", "Stroke Color")
            btn_stroke_color.clicked.connect(lambda: self.viewmodel.change_stroke_color(item, self.editor_viewmodel.scene.undo_stack))
            self.main_layout.addWidget(btn_stroke_color)

            stroke_width = QSpinBox()
            stroke_width.setRange(0, 40)
            stroke_width.setValue(item.pen().width())
            stroke_width.setSuffix(" px")
            def on_stroke_width_changed(width: int) -> None:
                self.viewmodel.set_stroke_width(item, width, self.editor_viewmodel.scene.undo_stack)
            stroke_width.valueChanged.connect(on_stroke_width_changed)
            self.main_layout.addWidget(stroke_width)

        elif isinstance(item, QGraphicsTextItem):
            self.main_layout.addWidget(_section_header("Font Family"))
            font_box = QFontComboBox()
            font_box.setCursor(Qt.CursorShape.PointingHandCursor)
            font_box.setCurrentFont(item.font())

            def on_font_changed(font: QFont) -> None:
                self.viewmodel.change_text_font(item, font, self.editor_viewmodel.scene.undo_stack)
            font_box.currentFontChanged.connect(on_font_changed)
            self.main_layout.addWidget(font_box)

            self.main_layout.addWidget(_section_header("Font Size"))
            size_box = QSpinBox()
            size_box.setRange(8, 120)
            size_box.setValue(item.font().pointSize())

            def on_size_changed(size: int) -> None:
                self.viewmodel.change_text_size(item, size, self.editor_viewmodel.scene.undo_stack)
            size_box.valueChanged.connect(on_size_changed)
            self.main_layout.addWidget(size_box)

            btn_color = _button(ICON_PALETTE, "Text Color")
            btn_color.clicked.connect(lambda: self.viewmodel.change_text_color(item, self.editor_viewmodel.scene.undo_stack))
            self.main_layout.addWidget(btn_color)

            self.main_layout.addWidget(_section_header("Style"))
            font = item.font()
            btn_bold = _toggle_button("fa5s.bold", "Bold", font.bold())
            btn_italic = _toggle_button("fa5s.italic", "Italic", font.italic())
            btn_underline = _toggle_button("fa5s.underline", "Underline", font.underline())
            def on_bold_toggled(on: bool) -> None:
                self.viewmodel.toggle_text_bold(item, on, self.editor_viewmodel.scene.undo_stack)
            def on_italic_toggled(on: bool) -> None:
                self.viewmodel.toggle_text_italic(item, on, self.editor_viewmodel.scene.undo_stack)
            def on_underline_toggled(on: bool) -> None:
                self.viewmodel.toggle_text_underline(item, on, self.editor_viewmodel.scene.undo_stack)
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
                    lambda _checked=False, a=alignment: self.viewmodel.set_text_alignment(item, a, self.editor_viewmodel.scene.undo_stack)
                )
                align_row.addWidget(btn)
            self.main_layout.addLayout(align_row)

        # 3. Effects (opacity + shadow, available for every item type)
        self.main_layout.addSpacing(8)
        self._add_effects_section([item])

        # 4. Align to page (only one item selected, so "the page" is the obvious reference)
        self.main_layout.addSpacing(8)
        self._add_align_section(single_item=True)

        # 5. Arrangement (available for all items)
        self.main_layout.addSpacing(8)
        self.main_layout.addWidget(_section_header("Arrangement"))

        btn_front = _button("fa5s.arrow-up", "Bring to Front")
        btn_front.clicked.connect(lambda: self.editor_viewmodel.scene.bring_to_front(item))
        self.main_layout.addWidget(btn_front)

        btn_back = _button("fa5s.arrow-down", "Send to Back")
        btn_back.clicked.connect(lambda: self.editor_viewmodel.scene.send_to_back(item))
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
        btn_dist_h.clicked.connect(lambda: self.editor_viewmodel.scene.distribute_items("horizontal"))
        btn_dist_v.clicked.connect(lambda: self.editor_viewmodel.scene.distribute_items("vertical"))
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
        btn_front.clicked.connect(lambda: self.editor_viewmodel.scene.bring_items_to_front(items))
        self.main_layout.addWidget(btn_front)

        btn_back = _button("fa5s.arrow-down", "Send to Back")
        btn_back.clicked.connect(lambda: self.editor_viewmodel.scene.send_items_to_back(items))
        self.main_layout.addWidget(btn_back)

        btn_group = _button("fa5s.object-group", "Group")
        btn_group.clicked.connect(lambda: self.editor_viewmodel.scene.group_items(items))
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
                self.viewmodel.set_opacity(items[0], fraction, self.editor_viewmodel.scene.undo_stack)
            else:
                self.viewmodel.set_opacity_multi(items, fraction, self.editor_viewmodel.scene.undo_stack)
        opacity_slider.valueChanged.connect(on_opacity_changed)
        self.main_layout.addWidget(opacity_slider)

        shadow_checkbox = QCheckBox("Drop Shadow")
        shadow_checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        shadow_checkbox.setChecked(items[0].graphicsEffect() is not None)  # type: ignore[reportUnnecessaryComparison]

        def on_shadow_toggled(checked: bool) -> None:
            if len(items) == 1:
                self.viewmodel.toggle_shadow(items[0], checked, self.editor_viewmodel.scene.undo_stack)
            else:
                self.viewmodel.toggle_shadow_multi(items, checked, self.editor_viewmodel.scene.undo_stack)
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
            btn.clicked.connect(lambda _checked=False, e=edge: self.editor_viewmodel.scene.align_items(e))
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
            btn.clicked.connect(lambda _checked=False, e=edge: self.editor_viewmodel.scene.align_items(e))
            v_row.addWidget(btn)
        self.main_layout.addLayout(v_row)

    def _add_transform_section(self, item: QGraphicsItem) -> None:
        self.main_layout.addWidget(_section_header("Position & Size"))

        x_box, y_box = QSpinBox(), QSpinBox()
        for box, prefix, value in ((x_box, "X  ", item.pos().x()), (y_box, "Y  ", item.pos().y())):
            box.setRange(-100000, 100000)
            box.setPrefix(prefix)
            box.setCursor(Qt.CursorShape.IBeamCursor)
            box.setValue(round(value))

        def on_pos_changed(_value: int = 0) -> None:
            self.viewmodel.set_item_position(item, x_box.value(), y_box.value(), self.editor_viewmodel.scene.undo_stack)
        x_box.valueChanged.connect(on_pos_changed)
        y_box.valueChanged.connect(on_pos_changed)
        pos_row = QHBoxLayout()
        pos_row.addWidget(x_box)
        pos_row.addWidget(y_box)
        self.main_layout.addLayout(pos_row)

        size = get_item_size(item)
        if size is None:
            return  # e.g. a group -- no independent size to show/edit

        w_box, h_box = QSpinBox(), QSpinBox()
        for box, prefix, value in ((w_box, "W  ", size[0]), (h_box, "H  ", size[1])):
            box.setRange(int(MIN_SIZE), 100000)
            box.setPrefix(prefix)
            box.setCursor(Qt.CursorShape.IBeamCursor)
            box.setValue(round(value))

        editable_height = can_edit_height(item)
        h_box.setEnabled(editable_height)
        if not editable_height:
            h_box.setToolTip("Text height follows its content")

        def sync_size_boxes(new_size: tuple[float, float] | None) -> None:
            # Reflects the item's *real* resulting size back into the boxes --
            # aspect-locked images silently override whatever height was
            # asked for (see is_aspect_locked below), so without this the
            # boxes would show a value that didn't actually stick.
            if new_size is None:
                return
            w_box.blockSignals(True)
            h_box.blockSignals(True)
            w_box.setValue(round(new_size[0]))
            h_box.setValue(round(new_size[1]))
            w_box.blockSignals(False)
            h_box.blockSignals(False)

        def on_width_changed(width: int) -> None:
            new_size = self.viewmodel.set_item_size(item, width, h_box.value(), self.editor_viewmodel.scene.undo_stack)
            sync_size_boxes(new_size)

        def on_height_changed(height: int) -> None:
            width = w_box.value()
            if is_aspect_locked(item):
                # The mixin's resize always re-derives height from width for
                # aspect-locked items, so a plain (width, height) pair would
                # ignore the height the user just typed -- solve for the
                # paired width instead so it actually takes effect.
                current = get_item_size(item)
                if current is not None and current[1]:
                    width = height * (current[0] / current[1])
            new_size = self.viewmodel.set_item_size(item, width, height, self.editor_viewmodel.scene.undo_stack)
            sync_size_boxes(new_size)

        w_box.valueChanged.connect(on_width_changed)
        h_box.valueChanged.connect(on_height_changed)
        size_row = QHBoxLayout()
        size_row.addWidget(w_box)
        size_row.addWidget(h_box)
        self.main_layout.addLayout(size_row)

    def inspect_page(self, scene: "DesignScene", page: "Page") -> None:
        self.clear_layout()
        self.main_layout.addWidget(_section_header("Page"))

        w_box, h_box = QSpinBox(), QSpinBox()
        for box, prefix, value in ((w_box, "W  ", page.width), (h_box, "H  ", page.height)):
            box.setRange(int(PAGE_MIN_SIZE), 10000)
            box.setPrefix(prefix)
            box.setCursor(Qt.CursorShape.IBeamCursor)
            box.setValue(int(value))

        def on_page_size_changed(_value: int = 0) -> None:
            self.viewmodel.set_page_size(scene, page, w_box.value(), h_box.value(), scene.undo_stack)
            # No forced view re-fit here -- reflow already keeps geometry
            # correct, and snapping the viewport to this page on every
            # keystroke would be jarring if the user is scrolled elsewhere.
        w_box.valueChanged.connect(on_page_size_changed)
        h_box.valueChanged.connect(on_page_size_changed)
        size_row = QHBoxLayout()
        size_row.addWidget(w_box)
        size_row.addWidget(h_box)
        self.main_layout.addLayout(size_row)

        self.main_layout.addSpacing(8)
        btn_bg = _button(ICON_PALETTE, "Background Color")
        btn_bg.clicked.connect(lambda: self.viewmodel.change_page_background(page, scene.undo_stack))
        self.main_layout.addWidget(btn_bg)
