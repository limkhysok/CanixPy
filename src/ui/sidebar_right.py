from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QFontComboBox, QSpinBox, QColorDialog
from PyQt6.QtWidgets import QGraphicsRectItem, QGraphicsEllipseItem, QGraphicsTextItem
from PyQt6.QtGui import QBrush

class PropertiesPanel(QWidget):
    def __init__(self, main_app, parent=None):
        super().__init__(parent)
        self.main_app = main_app
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.show_empty_state()

    def show_empty_state(self):
        self.clear_layout()
        self.layout.addWidget(QLabel("Select an item to edit its assets."))

    def clear_layout(self):
        for i in reversed(range(self.layout.count())):
            widget = self.layout.itemAt(i).widget()
            if widget: widget.deleteLater()

    def inspect_item(self, item):
        self.clear_layout()
        if not item or item == getattr(self.main_app.scene, 'page_frame', None):
            self.show_empty_state()
            return

        # 1. Custom settings depending on type
        if isinstance(item, (QGraphicsRectItem, QGraphicsEllipseItem)):
            btn_color = QPushButton("Change Color")
            btn_color.clicked.connect(lambda: self.change_shape_color(item))
            self.layout.addWidget(QLabel("Shape Styling:"))
            self.layout.addWidget(btn_color)

        elif isinstance(item, QGraphicsTextItem):
            self.layout.addWidget(QLabel("Font Family:"))
            font_box = QFontComboBox()
            font_box.setCurrentFont(item.font())
            font_box.currentFontChanged.connect(lambda f: self.change_text_font(item, f))
            self.layout.addWidget(font_box)

            self.layout.addWidget(QLabel("Font Size:"))
            size_box = QSpinBox()
            size_box.setRange(8, 120)
            size_box.setValue(item.font().pointSize())
            size_box.valueChanged.connect(lambda s: self.change_text_size(item, s))
            self.layout.addWidget(size_box)

            btn_color = QPushButton("Text Color")
            btn_color.clicked.connect(lambda: self.change_text_color(item))
            self.layout.addWidget(btn_color)

        # 2. GLOBAL ARRANGE TOOL LAYOUT (Available for all items)
        self.layout.addSpacing(15)
        self.layout.addWidget(QLabel("<b>Arrangement</b>"))
        
        btn_front = QPushButton("Bring to Front")
        btn_front.clicked.connect(lambda: self.main_app.scene.bring_to_front(item))
        self.layout.addWidget(btn_front)

        btn_back = QPushButton("Send to Back")
        btn_back.clicked.connect(lambda: self.main_app.scene.send_to_back(item))
        self.layout.addWidget(btn_back)

    def change_shape_color(self, item):
        color = QColorDialog.getColor()
        if color.isValid(): item.setBrush(QBrush(color))

    def change_text_font(self, item, font):
        current_font = item.font()
        current_font.setFamily(font.family())
        item.setFont(current_font)

    def change_text_size(self, item, size):
        current_font = item.font()
        current_font.setPointSize(size)
        item.setFont(current_font)

    def change_text_color(self, item):
        color = QColorDialog.getColor()
        if color.isValid(): item.setDefaultTextColor(color)