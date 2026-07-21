from __future__ import annotations

from datetime import datetime

from sqlmodel import Field, SQLModel

from app.core.ids import new_id


class Project(SQLModel, table=True):
    """A named folder that designs can be grouped into (mirrors desktop_app's Project)."""

    id: str = Field(default_factory=new_id, primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
