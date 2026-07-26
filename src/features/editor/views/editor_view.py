from pathlib import Path
from typing import Any

import shiboken6
from PySide6.QtCore import QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QGraphicsItem,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QVBoxLayout,
    QWidget,
)

from src.features.editor import persistence
from src.features.editor.canvas.page import Page, page_for_item
from src.features.editor.canvas.view import ZoomableGraphicsView
from src.features.editor.exporter import export_all_pages, export_extension, export_page
from src.features.editor.viewmodels.editor_viewmodel import EditorViewModel
from src.features.editor.views.layout.export_dialog import ALL_PAGES, ExportDialog
from src.features.editor.views.layout.left_sidebar import LeftSidebar
from src.features.editor.views.layout.page_overlay import PageOverlayManager
from src.features.editor.views.layout.right_sidebar import PropertiesPanel
from src.features.editor.views.layout.top_navbar import TopNavbar

# fmt -> file dialog filter, keyed by the same _EXPORTERS keys ExportDialog hands back.
_EXPORT_FILE_FILTERS: dict[str, str] = {
    "png": "PNG Image (*.png)",
    "png_transparent": "PNG Image (*.png)",
    "jpg": "JPG Image (*.jpg)",
    "pdf": "PDF Document (*.pdf)",
    "svg": "SVG Image (*.svg)",
}


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
        self.top_navbar.grid_toggled.connect(lambda checked: self.view.set_grid_visible(checked))
        self.top_navbar.export_clicked.connect(self.open_export_dialog)

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
        self.left_panel.refresh_texts_panel()
        self.update_history_buttons()

    def sync_editor_selection(self) -> None:
        """Lighter sync: call on plain selection changes (no structural change)."""
        if not shiboken6.isValid(self.scene):
            return  # scene's C++ side is mid-teardown (app closing); nothing to sync
        self._sync_active_page_from_selection()
        self.update_properties_panel()
        self.left_panel.layers_panel.sync_selection()
        self.left_panel.refresh_texts_panel()

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
    def open_export_dialog(self) -> None:
        dialog = ExportDialog(self.scene.pages, self.viewmodel.active_page_index, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        fmt, dpi, target = dialog.export_key(), dialog.dpi(), dialog.selected_page()
        if target is ALL_PAGES:
            self._export_all_pages(fmt, dpi)
        else:
            self._export_single_page(fmt, dpi, target)

    def _export_single_page(self, fmt: str, dpi: int, page: Page) -> None:
        page_number = self.scene.pages.index(page) + 1
        default_name = f"design_page_{page_number}.{export_extension(fmt)}"
        file_path, _ = QFileDialog.getSaveFileName(self, "Export Page", default_name, _EXPORT_FILE_FILTERS[fmt])
        if not file_path:
            return

        # Indeterminate (range 0-0): a single render+save isn't meaningfully
        # subdivisible into steps. setMinimumDuration's deferred-show timer
        # needs the event loop pumped to fire, which never happens during
        # the blocking export_page() call below -- so instead of relying on
        # it, force the dialog to show and actually paint *before* the
        # blocking call starts.
        progress = QProgressDialog("Exporting…", "Cancel", 0, 0, self)
        progress.setWindowTitle("Export")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setCancelButton(None)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.show()
        QApplication.processEvents()
        try:
            export_page(self.scene, file_path, page, fmt, dpi=dpi)
        finally:
            progress.close()

        self._notify_export_done(f"Exported {Path(file_path).name}", Path(file_path).parent)

    def _export_all_pages(self, fmt: str, dpi: int) -> None:
        """Exports every page in the document to its own file in a chosen
        folder -- unlike a single-page export, which always targets exactly
        one page picked in the dialog."""
        directory = QFileDialog.getExistingDirectory(self, "Export All Pages To")
        if not directory:
            return

        total = len(self.scene.pages)
        progress = QProgressDialog("Preparing export…", "Cancel", 0, total, self)
        progress.setWindowTitle("Export All Pages")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(400)
        progress.setAutoClose(False)

        def report_progress(done: int, page_total: int) -> bool:
            progress.setLabelText(f"Exporting page {done} of {page_total}…")
            progress.setValue(done)
            QApplication.processEvents()
            return not progress.wasCanceled()

        paths = export_all_pages(
            self.scene, self.scene.pages, directory, fmt, dpi=dpi, on_progress=report_progress
        )
        progress.close()

        exported = len(paths)
        noun = "page" if exported == 1 else "pages"
        suffix = "" if exported == total else f" (stopped early -- {total - exported} remaining)"
        self._notify_export_done(f"Exported {exported} {noun} to {Path(directory).name}{suffix}", Path(directory))

    def _notify_export_done(self, message: str, folder: Path) -> None:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Information)
        box.setWindowTitle("Export Complete")
        box.setText(message)
        open_folder_button = box.addButton("Open Folder", QMessageBox.ButtonRole.ActionRole)
        box.addButton(QMessageBox.StandardButton.Ok)
        box.exec()
        if box.clickedButton() is open_folder_button:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
