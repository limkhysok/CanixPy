"""Mirrors HomeViewModel's tasks/projects onto real files under projects/:
projects/<project>/<task>.canix for tasks in a project, projects/<task>.canix
for unassigned ones. Pure file I/O -- HomeViewModel owns *when* to call this
and keeps the in-memory task-id/project-id -> Path bookkeeping.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from src.core.paths import PROJECTS_DIR, sanitize_filename
from src.features.home.models.models import Task

TASK_SUFFIX = ".canix"
TASK_FORMAT_VERSION = 1


def task_path(task: Task, project_dir_name: str | None) -> Path:
    directory = PROJECTS_DIR / project_dir_name if project_dir_name else PROJECTS_DIR
    return directory / f"{sanitize_filename(task.name)}{TASK_SUFFIX}"


def unique_path(desired: Path, own_current_path: Path | None = None) -> Path:
    """Append " (2)", " (3)", ... if `desired` is already claimed on disk by
    something other than the item currently being renamed/moved."""
    if desired == own_current_path or not desired.exists():
        return desired
    stem, suffix, parent = desired.stem, desired.suffix, desired.parent
    n = 2
    while True:
        candidate = parent / f"{stem} ({n}){suffix}"
        if candidate == own_current_path or not candidate.exists():
            return candidate
        n += 1


def task_to_dict(task: Task) -> dict[str, Any]:
    return {
        "format_version": TASK_FORMAT_VERSION,
        "name": task.name,
        "canvas_size": list(task.canvas_size),
        "created_at": task.created_at.isoformat(),
        "modified_at": task.modified_at.isoformat(),
        "file_path": task.file_path,
        "original_filename": task.original_filename,
        "file_type": task.file_type,
        "file_size": task.file_size,
        "content": task.content,
    }


def task_from_dict(data: dict[str, Any]) -> Task:
    width, height = data["canvas_size"]
    return Task(
        name=data["name"],
        canvas_size=(int(width), int(height)),
        created_at=datetime.fromisoformat(data["created_at"]),
        modified_at=datetime.fromisoformat(data["modified_at"]),
        file_path=data.get("file_path"),
        original_filename=data.get("original_filename"),
        file_type=data.get("file_type"),
        file_size=data.get("file_size"),
        content=data.get("content"),
    )


def write_task(path: Path, task: Task) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(task_to_dict(task), indent=2), encoding="utf-8")


def read_task(path: Path) -> Task:
    return task_from_dict(json.loads(path.read_text(encoding="utf-8")))
