from __future__ import annotations

from datetime import datetime

from sqlmodel import Field, SQLModel

from app.core.ids import new_id


class Asset(SQLModel, table=True):
    """An uploaded media file (e.g. an imported image). Elements of kind "image"
    reference an Asset by id instead of embedding image bytes, unlike
    desktop_app's local png_base64 serialization -- see Page.items."""

    id: str = Field(default_factory=new_id, primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    filename: str
    content_type: str
    size: int
    storage_path: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
