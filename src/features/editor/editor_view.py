from PySide6.QtCore import Signal
from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QFileDialog
from src.features.editor.canvas.scene import DesignScene
from src.features.editor.canvas.view import ZoomableGraphicsView
from src.features.editor.layout.left_sidebar import LeftSidebar
from src.features.editor.layout.right_sidebar import PropertiesPanel
from src.features.editor.layout.top_navbar import TopNavbar
from src.features.editor.exporter import export_scene_to_png

class CoreDesignApp(QMainWindow):
    back_to_home = Signal()

    def __init__(self, canvas_size: tuple[int, int] = (800, 600)) -> None:
        super().__init__()
        self.setWindowTitle("Native Python Design Studio v3")
        self.setGeometry(100, 100, 1300, 800)

        self.canvas_size = canvas_size
        self.pages: dict[int, DesignScene] = {}
        self.current_page_index: int = 1

        self.init_ui()
        self.switch_to_page(1)

    def init_ui(self) -> None:
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # --- TOP NAVBAR ---
        self.top_navbar = TopNavbar(self)
        self.top_navbar.back_clicked.connect(self.back_to_home.emit)
        self.page_selector = self.top_navbar.page_selector

        # --- PANEL SYSTEM SETUP ---
        # Instantiate our upgraded LeftSidebar panel module
        self.left_panel = LeftSidebar(self)
        self.properties_panel = PropertiesPanel(self)

        # --- CANVAS SETUP ---
        self.scene = DesignScene(self)
        self.view = ZoomableGraphicsView(self.scene, self)

        # Assembly
        content_layout.addWidget(self.left_panel, 1)
        content_layout.addWidget(self.view, 4)
        content_layout.addWidget(self.properties_panel, 1)

        main_layout.addWidget(self.top_navbar)
        main_layout.addLayout(content_layout)
        self.setCentralWidget(main_widget)

    def zoom_in(self) -> None: self.view.scale(1.2, 1.2)
    def zoom_out(self) -> None: self.view.scale(0.8, 0.8)
    def zoom_reset(self) -> None: self.view.resetTransform()

    def add_new_page(self) -> None:
        new_page_num = len(self.pages) + 1
        self.page_selector.addItem(f"Page {new_page_num}", new_page_num)
        self.page_selector.setCurrentIndex(new_page_num - 1)

    def on_page_combo_changed(self, index: int) -> None:
        if index >= 0:
            self.switch_to_page(int(self.page_selector.itemData(index)))

    def switch_to_page(self, page_num: int) -> None:
        if page_num not in self.pages:
            self.pages[page_num] = DesignScene(self, *self.canvas_size)
            if self.page_selector.count() < page_num:
                self.page_selector.addItem(f"Page {page_num}", page_num)

        self.current_page_index = page_num
        self.scene = self.pages[page_num]
        self.view.setScene(self.scene)
        self.update_properties_panel()

    def update_properties_panel(self) -> None:
        selected = self.scene.selectedItems()
        if selected:
            self.properties_panel.inspect_item(selected[0])
        else:
            self.properties_panel.inspect_item(None)

    # --- NEW HIGH-RES EXPORT FEATURE ---
    def export_page_to_png(self) -> None:
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Page as PNG", f"design_page_{self.current_page_index}.png", "PNG Image (*.png)"
        )
        if not file_path:
            return

        width, height = self.canvas_size
        export_scene_to_png(self.scene, file_path, width, height)
