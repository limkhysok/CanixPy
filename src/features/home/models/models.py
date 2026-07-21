from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


def _new_id() -> str:
    return uuid.uuid4().hex


@dataclass
class Task:
    """A single design/work item: either a blank canvas or an imported image
    file the user is editing/customizing. Imported tasks carry file metadata;
    blank canvases leave those fields None."""

    name: str
    canvas_size: tuple[int, int]
    id: str = field(default_factory=_new_id)
    project_id: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    modified_at: datetime = field(default_factory=datetime.now)
    file_path: str | None = None
    original_filename: str | None = None
    file_type: str | None = None
    file_size: int | None = None
    content: dict[str, Any] | None = None
    """Serialized editor project data (see persistence.serialize_project),
    written back when the user leaves the editor. None until then."""

    @property
    def is_imported(self) -> bool:
        return self.file_path is not None


@dataclass
class Project:
    """A named folder that tasks can be grouped into."""

    name: str
    id: str = field(default_factory=_new_id)
    created_at: datetime = field(default_factory=datetime.now)
