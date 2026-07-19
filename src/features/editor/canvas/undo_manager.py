from __future__ import annotations

from typing import Callable

Action = tuple[Callable[[], None], Callable[[], None]]


class UndoStack:
    """Closure-based undo/redo history.

    Each entry is an (undo_fn, redo_fn) pair captured at the moment a
    mutation happens, so callers don't need to serialize item state --
    add/delete just re-attach/detach the same QGraphicsItem instance, and
    property/position changes just re-apply the old/new value.
    """

    def __init__(self, limit: int = 100, on_change: Callable[[], None] | None = None) -> None:
        self._undo_stack: list[Action] = []
        self._redo_stack: list[Action] = []
        self._limit = limit
        self._on_change = on_change

    def push(self, undo_fn: Callable[[], None], redo_fn: Callable[[], None]) -> None:
        self._undo_stack.append((undo_fn, redo_fn))
        if len(self._undo_stack) > self._limit:
            self._undo_stack.pop(0)
        self._redo_stack.clear()
        self._notify()

    def undo(self) -> None:
        if not self._undo_stack:
            return
        undo_fn, redo_fn = self._undo_stack.pop()
        undo_fn()
        self._redo_stack.append((undo_fn, redo_fn))
        self._notify()

    def redo(self) -> None:
        if not self._redo_stack:
            return
        undo_fn, redo_fn = self._redo_stack.pop()
        redo_fn()
        self._undo_stack.append((undo_fn, redo_fn))
        self._notify()

    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    def can_redo(self) -> bool:
        return bool(self._redo_stack)

    def _notify(self) -> None:
        if self._on_change:
            self._on_change()
