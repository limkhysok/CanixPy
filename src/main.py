import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QGraphicsScene, QGraphicsView, 
    QGraphicsRectItem, QGraphicsEllipseItem, QGraphicsTextItem, QGraphicsItem,
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QListWidget, 
    QListWidgetItem, QLabel, QComboBox, QColorDialog, QFontComboBox, QSpinBox
)
from PyQt6.QtCore import Qt, QSize, QPointF, QMimeData
from PyQt6.QtGui import QBrush, QColor, QFont, QDrag, QPainter

# 1. Custom Graphics View to handle key bindings and zooming
class ZoomableGraphicsView(QGraphicsView):
    def __init__(self, scene, main_app, parent=None):
        super().__init__(scene, parent)
        self.main_app = main_app
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setAcceptDrops(True)

    def wheelEvent(self, event):
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            zoom_factor = 1.25 if event.angleDelta().y() > 0 else 0.8
            self.scale(zoom_factor, zoom_factor)
        else:
            super().wheelEvent(event)

    def keyPressEvent(self, event):
        # Native keyboard action: Delete selected item on pressing Backspace or Delete
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            selected_items = self.scene().selectedItems()
            for item in selected_items:
                # Do not delete the background page layout frame
                if item != getattr(self.scene(), 'page_frame', None):
                    self.scene().removeItem(item)
            self.main_app.update_properties_panel()
        else:
            super().keyPressEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        event.acceptProposedAction()

    def dropEvent(self, event):
        shape_type = event.mimeData().text()
        drop_pos = self.mapToScene(event.position().toPoint())
        self.scene().add_dropped_item(shape_type, drop_pos)
        event.acceptProposedAction()


# 2. Main Canvas Scene
class DesignScene(QGraphicsScene):
    def __init__(self, main_app, parent=None):
        super().__init__(0, 0, 800, 600, parent)
        self.main_app = main_app
        self.setBackgroundBrush(QBrush(QColor("#ffffff")))
        self.create_page_boundary()
        # Trigger contextual UI updates when things are selected
        self.selectionChanged.connect(self.main_app.update_properties_panel)

    def create_page_boundary(self):
        self.page_frame = self.addRect(0, 0, 800, 600)
        self.page_frame.setPen(QColor("#cccccc"))
        self.page_frame.setZValue(-100)

    def add_dropped_item(self, shape_type, pos):
        if shape_type == "Rectangle":
            item = QGraphicsRectItem(0, 0, 150, 100)
            item.setBrush(QBrush(QColor("#3498db")))
        elif shape_type == "Circle":
            item = QGraphicsEllipseItem(0, 0, 100, 100)
            item.setBrush(QBrush(QColor("#e74c3c")))
        elif shape_type == "Text Box":
            item = QGraphicsTextItem("Double Click to Edit")
            item.setFont(QFont("Arial", 16))
            item.setDefaultTextColor(QColor("#2c3e50"))
            item.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditable)
        else:
            return

        item.setPos(pos.x() - 50, pos.y() - 50)
        item.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable | 
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
        )
        self.addItem(item)


# 3. Sidebar Drag Source Widgets
class DraggableListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.add_shape_item("Rectangle")
        self.add_shape_item("Circle")
        self.add_shape_item("Text Box")

    def add_shape_item(self, text):
        item = QListWidgetItem(text, self)
        item.setSizeHint(QSize(80, 40))
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

    def startDrag(self, supportedActions):
        item = self.currentItem()
        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setText(item.text())
        drag.setMimeData(mime_data)
        drag.exec(Qt.DropAction.CopyAction)


# 4. Main Integrated UI
class CoreDesignApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Native Python Design Studio v2")
        self.setGeometry(100, 100, 1300, 800)

        self.pages = {}
        self.current_page_index = 1

        self.init_ui()
        self.switch_to_page(1)

    def init_ui(self):
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        content_layout = QHBoxLayout()

        # --- TOP GLOBAL TOOLBAR ---
        toolbar = QHBoxLayout()
        
        self.page_selector = QComboBox()
        self.page_selector.currentIndexChanged.connect(self.on_page_combo_changed)
        btn_add_page = QPushButton("+ Add Page")
        btn_add_page.clicked.connect(self.add_new_page)

        btn_zoom_in = QPushButton("Zoom In (+)")
        btn_zoom_out = QPushButton("Zoom Out (-)")
        btn_zoom_reset = QPushButton("Reset")
        btn_zoom_in.clicked.connect(self.zoom_in)
        btn_zoom_out.clicked.connect(self.zoom_out)
        btn_zoom_reset.clicked.connect(self.zoom_reset)

        toolbar.addWidget(QLabel("Pages:"))
        toolbar.addWidget(self.page_selector)
        toolbar.addWidget(btn_add_page)
        toolbar.addSpacing(30)
        toolbar.addWidget(btn_zoom_in)
        toolbar.addWidget(btn_zoom_out)
        toolbar.addWidget(btn_zoom_reset)
        toolbar.addStretch()

        # --- LEFT SIDEBAR (Elements Layout) ---
        left_sidebar = QVBoxLayout()
        left_sidebar.addWidget(QLabel("<b>Toolbox</b>"))
        self.drag_list = DraggableListWidget()
        left_sidebar.addWidget(self.drag_list)

        # --- RIGHT SIDEBAR (Properties Customizer Panel) ---
        self.right_sidebar = QVBoxLayout()
        self.prop_container = QWidget()
        self.prop_layout = QVBoxLayout(self.prop_container)
        self.right_sidebar.addWidget(QLabel("<b>Properties Panel</b>"))
        self.right_sidebar.addWidget(self.prop_container)
        self.right_sidebar.addStretch()

        # --- CANVAS VIEWPORT ---
        self.scene = DesignScene(self)
        self.view = ZoomableGraphicsView(self.scene, self)

        # Layout Assembly
        content_layout.addLayout(left_sidebar, 1)
        content_layout.addWidget(self.view, 4)
        content_layout.addLayout(self.right_sidebar, 1)
        
        main_layout.addLayout(toolbar)
        main_layout.addLayout(content_layout)
        self.setCentralWidget(main_widget)

    # --- ACTION CONTROLS ---
    def zoom_in(self): self.view.scale(1.2, 1.2)
    def zoom_out(self): self.view.scale(0.8, 0.8)
    def zoom_reset(self): self.view.resetTransform()

    def add_new_page(self):
        new_page_num = len(self.pages) + 1
        self.page_selector.addItem(f"Page {new_page_num}", new_page_num)
        self.page_selector.setCurrentIndex(new_page_num - 1)

    def on_page_combo_changed(self, index):
        if index >= 0:
            self.switch_to_page(self.page_selector.itemData(index))

    def switch_to_page(self, page_num):
        if page_num not in self.pages:
            self.pages[page_num] = DesignScene(self)
            if self.page_selector.count() < page_num:
                self.page_selector.addItem(f"Page {page_num}", page_num)

        self.current_page_index = page_num
        self.scene = self.pages[page_num]
        self.view.setScene(self.scene)
        self.update_properties_panel()

    # --- PROPERTIES EDITOR LOGIC ---
    def update_properties_panel(self):
        # Flush the old panel tools out of layout context safely
        for i in reversed(range(self.prop_layout.count())): 
            widget = self.prop_layout.itemAt(i).widget()
            if widget: widget.deleteLater()

        selected = self.scene.selectedItems()
        if not selected or selected[0] == getattr(self.scene, 'page_frame', None):
            self.prop_layout.addWidget(QLabel("Select an item to edit its assets."))
            return

        item = selected[0]

        # Scenario A: Item is a Vector Shape (Rectangle/Circle)
        if isinstance(item, (QGraphicsRectItem, QGraphicsEllipseItem)):
            btn_color = QPushButton("Change Color")
            btn_color.clicked.connect(lambda: self.change_shape_color(item))
            self.prop_layout.addWidget(QLabel("Shape Styling:"))
            self.prop_layout.addWidget(btn_color)

        # Scenario B: Item is Text Engine
        elif isinstance(item, QGraphicsTextItem):
            self.prop_layout.addWidget(QLabel("Font Family:"))
            font_box = QFontComboBox()
            font_box.setCurrentFont(item.font())
            font_box.currentFontChanged.connect(lambda f: self.change_text_font(item, f))
            self.prop_layout.addWidget(font_box)

            self.prop_layout.addWidget(QLabel("Font Size:"))
            size_box = QSpinBox()
            size_box.setRange(8, 120)
            size_box.setValue(item.font().pointSize())
            size_box.valueChanged.connect(lambda s: self.change_text_size(item, s))
            self.prop_layout.addWidget(size_box)

            btn_color = QPushButton("Text Color")
            btn_color.clicked.connect(lambda: self.change_text_color(item))
            self.prop_layout.addWidget(btn_color)

    def change_shape_color(self, item):
        color = QColorDialog.getColor()
        if color.isValid():
            item.setBrush(QBrush(color))

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
        if color.isValid():
            item.setDefaultTextColor(color)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CoreDesignApp()
    window.show()
    sys.exit(app.exec())