from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime


def _new_id() -> str:
    return uuid.uuid4().hex


@dataclass
class Task:
    """A single design/work item, e.g. one canvas the user has created."""

    name: str
    canvas_size: tuple[int, int]
    id: str = field(default_factory=_new_id)
    project_id: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    modified_at: datetime = field(default_factory=datetime.now)


@dataclass
class Project:
    """A named folder that tasks can be grouped into."""

    name: str
    id: str = field(default_factory=_new_id)
    created_at: datetime = field(default_factory=datetime.now)
