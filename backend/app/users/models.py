from __future__ import annotations

from datetime import datetime

from sqlmodel import Field, SQLModel

from app.core.ids import new_id


class User(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
