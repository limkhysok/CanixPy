from typing import Any, Callable

import shiboken6
from PySide6.QtCore import Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QFileDialog, QGraphicsItem, QHBoxLayout, QMainWindow, QVBoxLayout, QWidget
from src.features.editor import persistence
from src.features.editor.canvas.page import Page, page_for_item
from src.features.editor.canvas.scene import DesignScene
from src.features.editor.canvas.view import ZoomableGraphicsView
from src.features.editor.layout.left_sidebar import LeftSidebar
from src.features.editor.layout.page_overlay import PageOverlayManager
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
        # Index into self.scene.pages -- the page most recently interacted
        # with (clicked, selected an item on, scrolled to center on), used by
        # Export and the Properties panel's page-inspect view, both of which
        # need exactly one page in context even though every page is visible
        # at once. See set_active_page().
        self.active_page_index: int = 0
        self._active_properties_page: Page | None = None
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

        # --- PANEL SYSTEM SETUP ---
        self.left_panel = LeftSidebar(self)
        self.properties_panel = PropertiesPanel(self)

        # --- CANVAS SETUP ---
        # One shared scene for the whole document -- pages are stacked
        # regions within it (see DesignScene.add_page), not separate scenes
        # swapped in and out.
        self.scene = DesignScene(self)
        self.scene.add_page(*self.canvas_size)
        self.view = ZoomableGraphicsView(self.scene, self)

        # Per-page floating labels (name/rename/duplicate/delete/move) + a
        # trailing Add Page button, parented onto the viewport and
        # repositioned every repaint -- see ZoomableGraphicsView.paintEvent.
        self.page_overlay_manager = PageOverlayManager(self, self.view.viewport())
        self.page_overlay_manager.rebuild()
        self.view.page_overlay_manager = self.page_overlay_manager

        self.set_active_page(self.scene.pages[0])

        # Assembly
        content_layout.addWidget(self.left_panel, 1)
        content_layout.addWidget(self.view, 4)
        content_layout.addWidget(self.properties_panel, 1)

        main_layout.addWidget(self.top_navbar)
        main_layout.addLayout(content_layout)
        self.setCentralWidget(main_widget)

    def zoom_in(self) -> None: self.view.scale(1.2, 1.2)
    def zoom_out(self) -> None: self.view.scale(0.8, 0.8)
    def zoom_reset(self) -> None: self.view.fit_to_page(self.active_page)

    # --- ACTIVE PAGE ---------------------------------------------------
    @property
    def active_page(self) -> Page:
        index = min(self.active_page_index, len(self.scene.pages) - 1)
        return self.scene.pages[index]

    def set_active_page(self, page: Page) -> None:
        try:
            index = self.scene.pages.index(page)
        except ValueError:
            return
        changed = index != self.active_page_index
        self.active_page_index = index
        if changed:
            self.left_panel.layers_panel.refresh()

    def _page_label(self, page: Page) -> str:
        index = self.scene.pages.index(page)
        return page.name or f"Page {index + 1}"

    def _sync_active_page_from_selection(self) -> None:
        selected = self.scene.selectedItems()
        if selected:
            self.set_active_page(page_for_item(self.scene.pages, selected[0]))

    # --- PAGE CRUD -------------------------------------------------------
    def add_new_page(self) -> None:
        page = self.scene.add_page(*self.canvas_size)
        self.page_overlay_manager.rebuild()
        self.set_active_page(page)
        self.view.scroll_to_page(page)
        self.refresh_editor_panels()

    def duplicate_page(self, source: Page) -> None:
        new_page = self.scene.insert_page_after(
            source, int(source.width), int(source.height), source.background_color
        )
        items_data = persistence.serialize_page_items(self.scene, source)
        # No undo entry -- page-level actions (add/delete/duplicate/move)
        # aren't undoable at all yet (a pre-existing gap, not new here), and
        # add_items_with_undo would leave a half-broken entry that removes
        # the duplicated items but not the duplicated page frame itself.
        self.scene.add_items(persistence.deserialize_page_items(items_data, new_page))
        new_page.name = f"{self._page_label(source)} Copy"

        self.page_overlay_manager.rebuild()
        self.set_active_page(new_page)
        self.view.scroll_to_page(new_page)
        self.refresh_editor_panels()

    def delete_page(self, page: Page) -> None:
        if len(self.scene.pages) <= 1:
            return  # always keep at least one page
        was_active = page is self.active_page
        self.scene.delete_page(page)
        self.page_overlay_manager.rebuild()
        if was_active:
            new_index = min(self.active_page_index, len(self.scene.pages) - 1)
            self.set_active_page(self.scene.pages[new_index])
        self.refresh_editor_panels()

    def move_page(self, page: Page, delta: int) -> None:
        self.scene.move_page(page, delta)
        self.page_overlay_manager.rebuild()
        self.refresh_editor_panels()

    def rename_page(self, page: Page, name: str) -> None:
        name = name.strip()
        index = self.scene.pages.index(page)
        default_name = f"Page {index + 1}"
        page.name = name if name and name != default_name else None

    def update_properties_panel(self) -> None:
        selected = self.scene.selectedItems()
        if selected:
            self._active_properties_page = None
            self.properties_panel.inspect_selection(selected)
        elif self._active_properties_page is not None:
            self.properties_panel.inspect_page(self.scene, self._active_properties_page)
        else:
            self.properties_panel.inspect_selection([])

    def show_page_properties(self, page: Page) -> None:
        self._active_properties_page = page
        self.set_active_page(page)
        self.update_properties_panel()

    def clear_page_properties(self) -> None:
        self._active_properties_page = None
        self.update_properties_panel()

    def refresh_editor_panels(self) -> None:
        """Full rebuild: call after anything that adds/removes/reorders items."""
        if not shiboken6.isValid(self.scene):
            return  # scene's C++ side is mid-teardown (app closing); nothing to refresh
        self._sync_active_page_from_selection()
        self.update_properties_panel()
        self.left_panel.layers_panel.refresh()
        self.update_history_buttons()

    def sync_editor_selection(self) -> None:
        """Lighter sync: call on plain selection changes (no structural change)."""
        if not shiboken6.isValid(self.scene):
            return  # scene's C++ side is mid-teardown (app closing); nothing to sync
        self._sync_active_page_from_selection()
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
        frames = self.scene.page_frames()
        items = [i for i in self.scene.selectedItems() if i not in frames]
        self._clipboard = [d for i in items if (d := persistence.serialize_item(i)) is not None]

    def paste_clipboard(self) -> None:
        self._paste_data(self._clipboard)

    def duplicate_selection(self) -> None:
        frames = self.scene.page_frames()
        items = [i for i in self.scene.selectedItems() if i not in frames]
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
        """Replace the whole document with a previously-serialized project
        (see persistence.serialize_project). Used both by File > Open and by
        the Home screen restoring a task's saved editor content."""
        canvas_size = data.get("canvas_size")
        if canvas_size and len(canvas_size) == 2:
            self.canvas_size = (int(canvas_size[0]), int(canvas_size[1]))

        self._active_properties_page = None
        self.active_page_index = 0

        new_scene = DesignScene(self)
        pages_data: list[dict[str, Any]] = data.get("pages", [])
        for page_entry in pages_data:
            width = int(page_entry.get("width", self.canvas_size[0]))
            height = int(page_entry.get("height", self.canvas_size[1]))
            background_color = page_entry.get("background_color", "#ffffff")
            page = new_scene.add_page(width, height, background_color, page_entry.get("name"))
            new_scene.add_items(persistence.deserialize_page_items(page_entry.get("items", []), page))
        if not new_scene.pages:
            new_scene.add_page(*self.canvas_size)

        self.scene = new_scene
        self.view.setScene(self.scene)
        self.page_overlay_manager.rebuild()
        self.view.request_fit_to_page(self.scene.pages[0])
        self.set_active_page(self.scene.pages[0])
        self.refresh_editor_panels()

    # --- EXPORT ---
    def export_page_to_png(self) -> None:
        self._export(f"design_page_{self.active_page_index + 1}.png", "PNG Image (*.png)", self._do_export_png)

    def export_page_to_png_transparent(self) -> None:
        self._export(
            f"design_page_{self.active_page_index + 1}.png", "PNG Image (*.png)", self._do_export_png_transparent
        )

    def export_page_to_jpg(self) -> None:
        self._export(f"design_page_{self.active_page_index + 1}.jpg", "JPG Image (*.jpg)", self._do_export_jpg)

    def export_page_to_pdf(self) -> None:
        self._export(f"design_page_{self.active_page_index + 1}.pdf", "PDF Document (*.pdf)", self._do_export_pdf)

    def _export(self, default_name: str, file_filter: str, do_export: Callable[[str, Page], None]) -> None:
        file_path, _ = QFileDialog.getSaveFileName(self, "Export Page", default_name, file_filter)
        if not file_path:
            return
        # The active page's actual size, not an app-level default -- a page
        # resized via the Properties panel would otherwise silently export
        # at the wrong dimensions.
        do_export(file_path, self.active_page)

    def _do_export_png(self, file_path: str, page: Page) -> None:
        export_scene_to_png(self.scene, file_path, page)

    def _do_export_png_transparent(self, file_path: str, page: Page) -> None:
        export_scene_to_png(self.scene, file_path, page, transparent=True)

    def _do_export_jpg(self, file_path: str, page: Page) -> None:
        export_scene_to_jpg(self.scene, file_path, page)

    def _do_export_pdf(self, file_path: str, page: Page) -> None:
        export_scene_to_pdf(self.scene, file_path, page)
