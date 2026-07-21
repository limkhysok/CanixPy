from __future__ import annotations

from datetime import datetime

from sqlmodel import Field, SQLModel

from app.core.ids import new_id

# Matches desktop_app's PROJECT_FORMAT_VERSION (src/features/editor/persistence.py)
# so a design's page/element JSON can move between desktop and backend unchanged.
CURRENT_FORMAT_VERSION = 2


class Design(SQLModel, table=True):
    """A single design/work item, e.g. a poster or slide deck (mirrors desktop_app's Task)."""

    id: str = Field(default_factory=new_id, primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    project_id: str | None = Field(default=None, foreign_key="project.id", index=True)
    name: str
    canvas_width: int
    canvas_height: int
    format_version: int = Field(default=CURRENT_FORMAT_VERSION)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    modified_at: datetime = Field(default_factory=datetime.utcnow)
