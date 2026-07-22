from typing import Any, Callable

import shiboken6
from PySide6.QtCore import Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QFileDialog, QGraphicsItem, QHBoxLayout, QMainWindow, QVBoxLayout, QWidget
from src.features.editor import persistence
from src.features.editor.canvas.scene import DesignScene
from src.features.editor.canvas.view import ZoomableGraphicsView
from src.features.editor.layout.left_sidebar import LeftSidebar
from src.features.editor.layout.right_sidebar import PropertiesPanel
from src.features.editor.layout.top_navbar import TopNavbar
from src.features.editor.exporter import export_scene_to_jpg, export_scene_to_pdf, export_scene_to_png

PASTE_OFFSET = 20

class CoreDesignApp(QMainWindow):
    back_to_home = Signal()

    def __init__(self, canvas_size: tuple[int, int] = (800, 600)) -> None:
        super().__init__()
        self.setWindowTitle("Native Python Design Studio v3")
        self.setGeometry(100, 100, 1300, 800)

        self.canvas_size = canvas_size
        self.pages: list[DesignScene] = []
        self.current_page_index: int = 0  # index into self.pages
        self._clipboard: list[dict[str, Any]] = []

        self.init_ui()
        self.init_shortcuts()
        self.refresh_editor_panels()

    def init_shortcuts(self) -> None:
        undo_shortcut = QShortcut(QKeySequence.StandardKey.Undo, self)
        undo_shortcut.activated.connect(self.undo)
        redo_shortcut = QShortcut(QKeySequence.StandardKey.Redo, self)
        redo_shortcut.activated.connect(self.redo)
        save_shortcut = QShortcut(QKeySequence.StandardKey.Save, self)
        save_shortcut.activated.connect(self.save_project)
        open_shortcut = QShortcut(QKeySequence.StandardKey.Open, self)
        open_shortcut.activated.connect(self.open_project)

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
        # Page 1 is created directly (not via switch_to_page) so there's never
        # a throwaway scene: an unparented DesignScene that briefly exists only
        # to be immediately discarded is a real crash risk -- once nothing
        # references it, Python's *cyclic* GC (non-deterministic timing) can
        # collect it later and invalidate its C++ side out from under a signal
        # callback ("Internal C++ object already deleted").
        self.pages = [DesignScene(self, *self.canvas_size)]
        self.scene = self.pages[0]
        self.view = ZoomableGraphicsView(self.scene, self)
        self._rebuild_page_selector()

        # Assembly
        content_layout.addWidget(self.left_panel, 1)
        content_layout.addWidget(self.view, 4)
        content_layout.addWidget(self.properties_panel, 1)

        main_layout.addWidget(self.top_navbar)
        main_layout.addLayout(content_layout)
        self.setCentralWidget(main_widget)

    def zoom_in(self) -> None: self.view.scale(1.2, 1.2)
    def zoom_out(self) -> None: self.view.scale(0.8, 0.8)
    def zoom_reset(self) -> None: self.view.fit_to_page()

    def _page_label(self, index: int) -> str:
        return self.pages[index].page_name or f"Page {index + 1}"

    def _rebuild_page_selector(self) -> None:
        # Page identity is just list position -- rebuilding the whole combo
        # from self.pages after any add/duplicate/delete/move keeps its
        # labels and order trivially in sync, no incremental patching needed.
        self.page_selector.blockSignals(True)
        self.page_selector.clear()
        for i in range(len(self.pages)):
            self.page_selector.addItem(self._page_label(i))
        self.page_selector.setCurrentIndex(self.current_page_index)
        self.page_selector.blockSignals(False)

    def on_page_combo_changed(self, index: int) -> None:
        if index >= 0:
            self.switch_to_page(index)

    def switch_to_page(self, index: int) -> None:
        if not (0 <= index < len(self.pages)):
            return
        self.current_page_index = index
        self.scene = self.pages[index]
        self.view.setScene(self.scene)
        self.view.request_fit_to_page()
        if self.page_selector.currentIndex() != index:
            self.page_selector.blockSignals(True)
            self.page_selector.setCurrentIndex(index)
            self.page_selector.blockSignals(False)
        self.refresh_editor_panels()

    def add_new_page(self) -> None:
        self.pages.append(DesignScene(self, *self.canvas_size))
        self._rebuild_page_selector()
        self.switch_to_page(len(self.pages) - 1)

    def duplicate_current_page(self) -> None:
        source = self.pages[self.current_page_index]
        new_scene = DesignScene(self, *self.canvas_size)
        for item_data in persistence.serialize_page(source):
            item = persistence.deserialize_item(item_data)
            if item:
                new_scene.addItem(item)
        new_scene.page_name = f"{self._page_label(self.current_page_index)} Copy"

        insert_at = self.current_page_index + 1
        self.pages.insert(insert_at, new_scene)
        self._rebuild_page_selector()
        self.switch_to_page(insert_at)

    def delete_current_page(self) -> None:
        if len(self.pages) <= 1:
            return  # always keep at least one page
        del self.pages[self.current_page_index]
        self._rebuild_page_selector()
        self.switch_to_page(min(self.current_page_index, len(self.pages) - 1))

    def move_current_page(self, delta: int) -> None:
        index = self.current_page_index
        new_index = index + delta
        if not (0 <= new_index < len(self.pages)):
            return
        self.pages[index], self.pages[new_index] = self.pages[new_index], self.pages[index]
        self._rebuild_page_selector()
        self.switch_to_page(new_index)

    def rename_current_page(self, name: str) -> None:
        name = name.strip()
        current_default = f"Page {self.current_page_index + 1}"
        self.pages[self.current_page_index].page_name = name if name and name != current_default else None
        self._rebuild_page_selector()

    def update_properties_panel(self) -> None:
        self.properties_panel.inspect_selection(self.scene.selectedItems())

    def refresh_editor_panels(self) -> None:
        """Full rebuild: call after anything that adds/removes/reorders items."""
        if not shiboken6.isValid(self.scene):
            return  # scene's C++ side is mid-teardown (app closing); nothing to refresh
        self.update_properties_panel()
        self.left_panel.layers_panel.refresh()
        self.update_history_buttons()

    def sync_editor_selection(self) -> None:
        """Lighter sync: call on plain selection changes (no structural change)."""
        if not shiboken6.isValid(self.scene):
            return  # scene's C++ side is mid-teardown (app closing); nothing to sync
        self.update_properties_panel()
        self.left_panel.layers_panel.sync_selection()

    def update_history_buttons(self) -> None:
        self.top_navbar.set_history_enabled(self.scene.undo_stack.can_undo(), self.scene.undo_stack.can_redo())

    def undo(self) -> None:
        self.scene.undo_stack.undo()
        self.refresh_editor_panels()

    def redo(self) -> None:
        self.scene.undo_stack.redo()
        self.refresh_editor_panels()

    # --- CLIPBOARD (copy / paste / duplicate) ---
    def copy_selection(self) -> None:
        page_frame = getattr(self.scene, "page_frame", None)
        items = [i for i in self.scene.selectedItems() if i != page_frame]
        self._clipboard = [d for i in items if (d := persistence.serialize_item(i)) is not None]

    def paste_clipboard(self) -> None:
        self._paste_data(self._clipboard)

    def duplicate_selection(self) -> None:
        page_frame = getattr(self.scene, "page_frame", None)
        items = [i for i in self.scene.selectedItems() if i != page_frame]
        self.duplicate_items(items)

    def duplicate_items(self, items: list[QGraphicsItem]) -> None:
        """Duplicate specific items regardless of current selection -- e.g.
        an image's right-click "Duplicate" should act on that image even if
        it's locked (and so can't actually be selected)."""
        data = [d for i in items if (d := persistence.serialize_item(i)) is not None]
        self._paste_data(data)

    def _paste_data(self, data: list[dict[str, Any]]) -> None:
        if not data:
            return
        new_items: list[QGraphicsItem] = []
        for item_data in data:
            offset_data = dict(item_data)
            offset_data["x"] = item_data["x"] + PASTE_OFFSET
            offset_data["y"] = item_data["y"] + PASTE_OFFSET
            item = persistence.deserialize_item(offset_data)
            if item:
                new_items.append(item)
        if not new_items:
            return
        self.scene.clearSelection()
        self.scene.add_items_with_undo(new_items)
        for item in new_items:
            item.setSelected(True)

    # --- SAVE / LOAD PROJECT ---
    def save_project(self) -> None:
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Project", "design_project.canix", "CanixPy Project (*.canix)"
        )
        if not file_path:
            return
        persistence.save_project(self, file_path)

    def open_project(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Project", "", "CanixPy Project (*.canix)"
        )
        if not file_path:
            return
        data = persistence.load_project_data(file_path)
        self.apply_project_data(data)

    def apply_project_data(self, data: dict[str, Any]) -> None:
        """Replace all pages with a previously-serialized project (see
        persistence.serialize_project). Used both by File > Open and by the
        Home screen restoring a task's saved editor content."""
        canvas_size = data.get("canvas_size")
        if canvas_size and len(canvas_size) == 2:
            self.canvas_size = (int(canvas_size[0]), int(canvas_size[1]))

        pages_data: list[dict[str, Any]] = data.get("pages", [])
        new_pages: list[DesignScene] = []
        for page_entry in pages_data:
            scene = DesignScene(self, *self.canvas_size)
            scene.page_name = page_entry.get("name")
            for item_data in page_entry.get("items", []):
                item = persistence.deserialize_item(item_data)
                if item:
                    scene.addItem(item)
            new_pages.append(scene)

        self.pages = new_pages or [DesignScene(self, *self.canvas_size)]
        self.current_page_index = 0
        self.scene = self.pages[0]
        self.view.setScene(self.scene)
        self.view.request_fit_to_page()
        self._rebuild_page_selector()
        self.refresh_editor_panels()

    # --- EXPORT ---
    def export_page_to_png(self) -> None:
        self._export(f"design_page_{self.current_page_index + 1}.png", "PNG Image (*.png)", self._do_export_png)

    def export_page_to_png_transparent(self) -> None:
        self._export(
            f"design_page_{self.current_page_index + 1}.png", "PNG Image (*.png)", self._do_export_png_transparent
        )

    def export_page_to_jpg(self) -> None:
        self._export(f"design_page_{self.current_page_index + 1}.jpg", "JPG Image (*.jpg)", self._do_export_jpg)

    def export_page_to_pdf(self) -> None:
        self._export(f"design_page_{self.current_page_index + 1}.pdf", "PDF Document (*.pdf)", self._do_export_pdf)

    def _export(self, default_name: str, file_filter: str, do_export: Callable[[str, int, int], None]) -> None:
        file_path, _ = QFileDialog.getSaveFileName(self, "Export Page", default_name, file_filter)
        if not file_path:
            return
        width, height = self.canvas_size
        do_export(file_path, width, height)

    def _do_export_png(self, file_path: str, width: int, height: int) -> None:
        export_scene_to_png(self.scene, file_path, width, height)

    def _do_export_png_transparent(self, file_path: str, width: int, height: int) -> None:
        export_scene_to_png(self.scene, file_path, width, height, transparent=True)

    def _do_export_jpg(self, file_path: str, width: int, height: int) -> None:
        export_scene_to_jpg(self.scene, file_path, width, height)

    def _do_export_pdf(self, file_path: str, width: int, height: int) -> None:
        export_scene_to_pdf(self.scene, file_path, width, height)
