from PyQt6.QtWidgets import QWidget, QVBoxLayout, QListWidget, QListWidgetItem, QPushButton, QLabel, QFileDialog
from PyQt6.QtCore import Qt, QSize, QPointF
from PyQt6.QtGui import QDrag, QMimeData

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


# Wrap both the list widget and the upload button together into a clean Sidebar Widget
class LeftSidebar(QWidget):
    def __init__(self, main_app, parent=None):
        super().__init__(parent)
        self.main_app = main_app
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(QLabel("<b>Shapes & Layers</b>"))
        self.drag_list = DraggableListWidget()
        layout.addWidget(self.drag_list)

        layout.addSpacing(10)
        layout.addWidget(QLabel("<b>Media Assets</b>"))
        
        btn_upload = QPushButton("📷 Upload Image")
        btn_upload.clicked.connect(self.trigger_image_upload)
        layout.addWidget(btn_upload)

    def trigger_image_upload(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Select Local Image Asset", 
            "", 
            "Images (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        if file_path:
            # Spawn the image right in the middle of the current canvas frame
            center_point = QPointF(400, 300)
            self.main_app.scene.add_image_item(file_path, center_point)