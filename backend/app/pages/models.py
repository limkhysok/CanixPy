from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from app.core.ids import new_id


class Page(SQLModel, table=True):
    """One canvas/page within a Design. `items` holds the same element list shape
    desktop_app's `serialize_page()` produces (see editor/persistence.py) -- a list
    of {kind, x, y, z, rotation, ...} dicts -- so pages sync without translation."""

    id: str = Field(default_factory=new_id, primary_key=True)
    design_id: str = Field(foreign_key="design.id", index=True)
    order: int
    name: str | None = None
    items: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
