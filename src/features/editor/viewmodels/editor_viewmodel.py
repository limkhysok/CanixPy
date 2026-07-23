from __future__ import annotations

from typing import Any, Callable

from PySide6.QtWidgets import QGraphicsItem

from src.features.editor import persistence
from src.features.editor.canvas.page import Page
from src.features.editor.canvas.scene import DesignScene

PASTE_OFFSET = 20


class EditorViewModel:
    """Owns the editor's document state: the scene/pages, active-page
    tracking, clipboard, and undo/redo/project-load data operations. A plain
    class with no Qt-widget dependencies, mirroring HomeViewModel's shape --
    EditorView constructs one and is pulled from by it and the panels it owns.

    DesignScene itself doesn't know about EditorView; the `on_*` callbacks
    passed in here are threaded straight through to it (see DesignScene's
    docstring), so EditorView's panel-refresh methods stay wired up across
    a project reload, when apply_project_data() replaces `scene` outright.
    """

    def __init__(
        self,
        canvas_size: tuple[int, int] = (800, 600),
        on_refresh: Callable[[], None] | None = None,
        on_properties_change: Callable[[], None] | None = None,
        on_history_change: Callable[[], None] | None = None,
    ) -> None:
        self.canvas_size = canvas_size
        self._on_refresh = on_refresh
        self._on_properties_change = on_properties_change
        self._on_history_change = on_history_change
        # Index into self.scene.pages -- the page most recently interacted
        # with (clicked, selected an item on, scrolled to center on), used by
        # Export and the Properties panel's page-inspect view, both of which
        # need exactly one page in context even though every page is visible
        # at once. See set_active_page().
        self.active_page_index: int = 0
        self._clipboard: list[dict[str, Any]] = []

        self.scene = self._new_scene()
        self.scene.add_page(*canvas_size)

    def _new_scene(self) -> DesignScene:
        return DesignScene(
            self.canvas_size,
            on_refresh=self._on_refresh,
            on_properties_change=self._on_properties_change,
            on_history_change=self._on_history_change,
        )

    # --- ACTIVE PAGE -----------------------------------------------------
    @property
    def active_page(self) -> Page:
        index = min(self.active_page_index, len(self.scene.pages) - 1)
        return self.scene.pages[index]

    def set_active_page(self, page: Page) -> bool:
        """Returns True if the active page index actually changed."""
        try:
            index = self.scene.pages.index(page)
        except ValueError:
            return False
        changed = index != self.active_page_index
        self.active_page_index = index
        return changed

    def _page_label(self, page: Page) -> str:
        index = self.scene.pages.index(page)
        return page.name or f"Page {index + 1}"

    # --- PAGE CRUD -------------------------------------------------------
    def add_new_page(self) -> Page:
        return self.scene.add_page(*self.canvas_size)

    def duplicate_page(self, source: Page) -> Page:
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
        return new_page

    def delete_page(self, page: Page) -> None:
        self.scene.delete_page(page)

    def move_page(self, page: Page, delta: int) -> None:
        self.scene.move_page(page, delta)

    def rename_page(self, page: Page, name: str) -> None:
        name = name.strip()
        index = self.scene.pages.index(page)
        default_name = f"Page {index + 1}"
        page.name = name if name and name != default_name else None

    # --- UNDO / REDO -------------------------------------------------------
    def undo(self) -> None:
        self.scene.undo_stack.undo()

    def redo(self) -> None:
        self.scene.undo_stack.redo()

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

    # --- PROJECT DATA ---
    def apply_project_data(self, data: dict[str, Any]) -> None:
        """Replace the whole document with a previously-serialized project
        (see persistence.serialize_project). Used both by File > Open and by
        the Home screen restoring a task's saved editor content."""
        canvas_size = data.get("canvas_size")
        if canvas_size and len(canvas_size) == 2:
            self.canvas_size = (int(canvas_size[0]), int(canvas_size[1]))

        self.active_page_index = 0

        new_scene = self._new_scene()
        pages_data: list[dict[str, Any]] = data.get("pages", [])
        for page_entry in pages_data:
            width = int(page_entry.get("width", self.canvas_size[0]))
            height = int(page_entry.get("height", self.canvas_size[1]))
            background_color = page_entry.get("background_color", "#ffffff")
            page = new_scene.add_page(width, height, background_color, page_entry.get("name"))
            # Older saves (before pages were freely positioned) won't have
            # these -- leave the auto-computed placement add_page() already
            # gave it in that case, rather than forcing (0, 0).
            x, y = page_entry.get("x"), page_entry.get("y")
            if x is not None and y is not None:
                page.frame.setPos(x, y)
            new_scene.add_items(persistence.deserialize_page_items(page_entry.get("items", []), page))
        if not new_scene.pages:
            new_scene.add_page(*self.canvas_size)

        self.scene = new_scene
