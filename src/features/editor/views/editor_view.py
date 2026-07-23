from typing import Any, Callable

import shiboken6
from PySide6.QtCore import Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QFileDialog, QGraphicsItem, QHBoxLayout, QMainWindow, QVBoxLayout, QWidget
from src.features.editor import persistence
from src.features.editor.canvas.page import Page, page_for_item
from src.features.editor.canvas.view import ZoomableGraphicsView
from src.features.editor.viewmodels.editor_viewmodel import EditorViewModel
from src.features.editor.views.layout.left_sidebar import LeftSidebar
from src.features.editor.views.layout.page_overlay import PageOverlayManager
from src.features.editor.views.layout.right_sidebar import PropertiesPanel
from src.features.editor.views.layout.top_navbar import TopNavbar
from src.features.editor.exporter import export_scene_to_jpg, export_scene_to_pdf, export_scene_to_png

class EditorView(QMainWindow):
    back_to_home = Signal()

    def __init__(self, canvas_size: tuple[int, int] = (800, 600)) -> None:
        super().__init__()
        self.setWindowTitle("Native Python Design Studio v3")
        self.setGeometry(100, 100, 1300, 800)

        self._active_properties_page: Page | None = None
        # Document state (scene/pages, active page, clipboard, undo/redo)
        # lives on the viewmodel -- see EditorViewModel. `self.scene` stays
        # as a direct alias since every panel under views/layout/ still
        # reads it that way.
        self.viewmodel = EditorViewModel(
            canvas_size,
            on_refresh=self.refresh_editor_panels,
            on_properties_change=self.update_properties_panel,
            on_history_change=self.update_history_buttons,
        )
        self.scene = self.viewmodel.scene
        self.scene.selectionChanged.connect(self.sync_editor_selection)

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
        # Doesn't take the viewmodel -- it has no state of its own to read,
        # just buttons that emit signals for this composition root to wire up.
        self.top_navbar = TopNavbar()
        self.top_navbar.back_clicked.connect(self.back_to_home.emit)
        self.top_navbar.undo_clicked.connect(self.undo)
        self.top_navbar.redo_clicked.connect(self.redo)
        self.top_navbar.export_png_clicked.connect(self.export_page_to_png)
        self.top_navbar.export_png_transparent_clicked.connect(self.export_page_to_png_transparent)
        self.top_navbar.export_jpg_clicked.connect(self.export_page_to_jpg)
        self.top_navbar.export_pdf_clicked.connect(self.export_page_to_pdf)

        # --- PANEL SYSTEM SETUP ---
        self.left_panel = LeftSidebar(self.viewmodel)
        self.properties_panel = PropertiesPanel(self.viewmodel)

        # --- CANVAS SETUP ---
        self.view = ZoomableGraphicsView(
            self.scene,
            self.viewmodel,
            on_refresh=self.refresh_editor_panels,
            on_properties_change=self.update_properties_panel,
            on_selection_sync=self.sync_editor_selection,
            on_page_properties_shown=self.show_page_properties,
            on_page_properties_cleared=self.clear_page_properties,
        )

        # Per-page floating labels (name/rename/duplicate/delete/move) + a
        # trailing Add Page button, parented onto the viewport and
        # repositioned every repaint -- see ZoomableGraphicsView.paintEvent.
        self.page_overlay_manager = PageOverlayManager(
            self.viewmodel,
            self.view.viewport(),
            on_add=self.add_new_page,
            on_duplicate=self.duplicate_page,
            on_delete=self.delete_page,
            on_move=self.move_page,
            on_rename=self.rename_page,
            on_active_page_changed=self.set_active_page,
        )
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

    # --- ACTIVE PAGE / CANVAS SIZE ---------------------------------------
    @property
    def canvas_size(self) -> tuple[int, int]:
        return self.viewmodel.canvas_size

    @property
    def active_page(self) -> Page:
        return self.viewmodel.active_page

    def set_active_page(self, page: Page) -> None:
        if self.viewmodel.set_active_page(page):
            self.left_panel.layers_panel.refresh()

    def _sync_active_page_from_selection(self) -> None:
        selected = self.scene.selectedItems()
        if selected:
            self.set_active_page(page_for_item(self.scene.pages, selected[0]))

    # --- PAGE CRUD -------------------------------------------------------
    def add_new_page(self) -> None:
        page = self.viewmodel.add_new_page()
        self.page_overlay_manager.rebuild()
        self.set_active_page(page)
        self.view.scroll_to_page(page)
        self.refresh_editor_panels()

    def duplicate_page(self, source: Page) -> None:
        new_page = self.viewmodel.duplicate_page(source)
        self.page_overlay_manager.rebuild()
        self.set_active_page(new_page)
        self.view.scroll_to_page(new_page)
        self.refresh_editor_panels()

    def delete_page(self, page: Page) -> None:
        if len(self.scene.pages) <= 1:
            return  # always keep at least one page
        was_active = page is self.active_page
        self.viewmodel.delete_page(page)
        self.page_overlay_manager.rebuild()
        if was_active:
            self.set_active_page(self.active_page)
        self.refresh_editor_panels()

    def move_page(self, page: Page, delta: int) -> None:
        self.viewmodel.move_page(page, delta)
        self.page_overlay_manager.rebuild()
        self.refresh_editor_panels()

    def rename_page(self, page: Page, name: str) -> None:
        self.viewmodel.rename_page(page, name)

    def update_properties_panel(self) -> None:
        selected = self.scene.selectedItems()
        if selected:
            self._set_page_resize_handles(None)
            self._active_properties_page = None
            self.properties_panel.inspect_selection(selected)
        elif self._active_properties_page is not None:
            self.properties_panel.inspect_page(self.scene, self._active_properties_page)
        else:
            self.properties_panel.inspect_selection([])

    def show_page_properties(self, page: Page) -> None:
        self._set_page_resize_handles(page)
        self._active_properties_page = page
        self.set_active_page(page)
        self.update_properties_panel()

    def clear_page_properties(self) -> None:
        self._set_page_resize_handles(None)
        self._active_properties_page = None
        self.update_properties_panel()

    def _set_page_resize_handles(self, page: Page | None) -> None:
        """On-canvas resize handles (PageFrameItem) track which page's
        inspector is open, not Qt selection -- page frames are never made
        ItemIsSelectable (see DesignScene._create_frame)."""
        if self._active_properties_page is not None and self._active_properties_page is not page:
            self._active_properties_page.frame.set_active_for_resize(False)
        if page is not None:
            page.frame.set_active_for_resize(True)

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
        self.viewmodel.undo()
        self.refresh_editor_panels()

    def redo(self) -> None:
        self.viewmodel.redo()
        self.refresh_editor_panels()

    # --- CLIPBOARD (copy / paste / duplicate) ---
    def copy_selection(self) -> None:
        self.viewmodel.copy_selection()

    def paste_clipboard(self) -> None:
        self.viewmodel.paste_clipboard()

    def duplicate_selection(self) -> None:
        self.viewmodel.duplicate_selection()

    def duplicate_items(self, items: list[QGraphicsItem]) -> None:
        """Duplicate specific items regardless of current selection -- e.g.
        an image's right-click "Duplicate" should act on that image even if
        it's locked (and so can't actually be selected)."""
        self.viewmodel.duplicate_items(items)

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
        self._active_properties_page = None
        self.viewmodel.apply_project_data(data)
        self.scene = self.viewmodel.scene
        self.scene.selectionChanged.connect(self.sync_editor_selection)
        self.view.setScene(self.scene)
        self.page_overlay_manager.rebuild()
        self.view.request_fit_to_page(self.scene.pages[0])
        self.set_active_page(self.scene.pages[0])
        self.refresh_editor_panels()

    # --- EXPORT ---
    def export_page_to_png(self) -> None:
        self._export(f"design_page_{self.viewmodel.active_page_index + 1}.png", "PNG Image (*.png)", self._do_export_png)

    def export_page_to_png_transparent(self) -> None:
        self._export(
            f"design_page_{self.viewmodel.active_page_index + 1}.png",
            "PNG Image (*.png)",
            self._do_export_png_transparent,
        )

    def export_page_to_jpg(self) -> None:
        self._export(f"design_page_{self.viewmodel.active_page_index + 1}.jpg", "JPG Image (*.jpg)", self._do_export_jpg)

    def export_page_to_pdf(self) -> None:
        self._export(f"design_page_{self.viewmodel.active_page_index + 1}.pdf", "PDF Document (*.pdf)", self._do_export_pdf)

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
