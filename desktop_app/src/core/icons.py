"""Typed wrapper around qtawesome, which ships without type stubs or py.typed.

Import `icon` from here instead of calling `qtawesome.icon` directly, so the
"Unknown" type qtawesome produces stays confined to this one file instead of
leaking reportUnknownMemberType/reportUnknownArgumentType into every widget
that uses an icon.
"""
from __future__ import annotations

from typing import Any

import qtawesome as qta  # pyright: ignore[reportMissingTypeStubs]
from PySide6.QtGui import QIcon


def icon(name: str, **kwargs: Any) -> QIcon:
    return qta.icon(name, **kwargs)  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
