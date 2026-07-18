from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QComboBox, QLabel, QFileDialog
from src.core import icons, theme
from src.features.editor.canvas.scene import DesignScene
from src.features.editor.canvas.view import ZoomableGraphicsView
from src.features.editor.sidebar_left import LeftSidebar
from src.features.editor.sidebar_right import PropertiesPanel
from src.features.editor.exporter import export_scene_to_png

class CoreDesignApp(QMainWindow):
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
        content_layout = QHBoxLayout()

        # --- TOP TOOLBAR ---
        toolbar = QHBoxLayout()
        self.page_selector = QComboBox()
        self.page_selector.currentIndexChanged.connect(self.on_page_combo_changed)
        btn_add_page = QPushButton(icons.icon("fa5s.plus"), "Add Page")
        btn_add_page.clicked.connect(self.add_new_page)

        btn_zoom_in = QPushButton(icons.icon("fa5s.search-plus"), "Zoom In")
        btn_zoom_out = QPushButton(icons.icon("fa5s.search-minus"), "Zoom Out")
        btn_zoom_reset = QPushButton(icons.icon("fa5s.undo"), "Reset")
        btn_zoom_in.clicked.connect(self.zoom_in)
        btn_zoom_out.clicked.connect(self.zoom_out)
        btn_zoom_reset.clicked.connect(self.zoom_reset)

        # NEW EXPORT BUTTON
        btn_export = QPushButton(icons.icon("fa5s.file-export", color=theme.TEXT_ON_ACCENT), "Export PNG")
        btn_export.setProperty("accent", True)
        btn_export.clicked.connect(self.export_page_to_png)

        toolbar.addWidget(QLabel("Pages:"))
        toolbar.addWidget(self.page_selector)
        toolbar.addWidget(btn_add_page)
        toolbar.addSpacing(30)
        toolbar.addWidget(btn_zoom_in)
        toolbar.addWidget(btn_zoom_out)
        toolbar.addWidget(btn_zoom_reset)
        toolbar.addSpacing(30)
        toolbar.addWidget(btn_export)
        toolbar.addStretch()

        # --- PANEL SYSTEM SETUP ---
        left_sidebar_layout = QVBoxLayout()
        # Instantiate our upgraded LeftSidebar panel module
        self.left_panel = LeftSidebar(self)
        left_sidebar_layout.addWidget(self.left_panel)

        right_sidebar_layout = QVBoxLayout()
        right_sidebar_layout.addWidget(QLabel("<b>Properties Panel</b>"))
        self.properties_panel = PropertiesPanel(self)
        right_sidebar_layout.addWidget(self.properties_panel)
        right_sidebar_layout.addStretch()

        # --- CANVAS SETUP ---
        self.scene = DesignScene(self)
        self.view = ZoomableGraphicsView(self.scene, self)

        # Assembly
        content_layout.addLayout(left_sidebar_layout, 1)
        content_layout.addWidget(self.view, 4)
        content_layout.addLayout(right_sidebar_layout, 1)

        main_layout.addLayout(toolbar)
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
