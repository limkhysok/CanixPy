from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from src.core.image_loader import load_pixmap
from src.core.paths import PROJECTS_DIR, sanitize_filename
from src.features.home import storage
from src.features.home.models.models import Project, Task

_UNTITLED_NAME_RE = re.compile(r"^Untitled Design (\d+)$")

MAX_CANVAS_PX = 10000

# Pixels-per-unit at the standard 96 DPI screen-design reference (the same
# reference Canva/Figma use), so a width typed as "1 in" maps to 96 px.
UNIT_PX_PER_UNIT: dict[str, float] = {
    "px": 1.0,
    "in": 96.0,
    "mm": 96.0 / 25.4,
    "cm": 96.0 / 2.54,
}
UNIT_DECIMALS: dict[str, int] = {"px": 0, "in": 2, "mm": 1, "cm": 2}


def px_to_unit(value_px: float, unit: str) -> float:
    return value_px / UNIT_PX_PER_UNIT[unit]


def unit_to_px(value: float, unit: str) -> int:
    return round(value * UNIT_PX_PER_UNIT[unit])


def _clamp_canvas_size(size: tuple[int, int]) -> tuple[int, int]:
    width, height = size
    return (
        min(max(width, 1), MAX_CANVAS_PX),
        min(max(height, 1), MAX_CANVAS_PX),
    )


@dataclass(frozen=True)
class CanvasPreset:
    name: str
    width: int
    height: int
    category: str


class HomeViewModel:
    """Owns the in-memory Home screen state: canvas presets, recent tasks, and projects."""

    # Order here drives both the category chip row and, within "Popular", the
    # curated cross-platform picks -- keep "Popular" first.
    CATEGORIES: tuple[str, ...] = (
        "Popular",
        "Facebook",
        "Instagram",
        "LinkedIn",
        "Pinterest",
        "TikTok",
        "Twitter",
        "YouTube",
    )

    PRESETS: list[CanvasPreset] = [
        # Popular -- curated cross-platform picks plus general-purpose sizes.
        CanvasPreset("Default", 800, 600, "Popular"),
        CanvasPreset("Instagram Post (Square)", 1080, 1080, "Popular"),
        CanvasPreset("Instagram Story", 1080, 1920, "Popular"),
        CanvasPreset("Facebook Post (Landscape)", 1200, 630, "Popular"),
        CanvasPreset("YouTube Thumbnail", 1280, 720, "Popular"),
        CanvasPreset("Presentation (16:9)", 1920, 1080, "Popular"),
        CanvasPreset("Pinterest Pin (Standard)", 1000, 1500, "Popular"),
        CanvasPreset("A4 Document", 794, 1123, "Popular"),
        # Facebook
        CanvasPreset("Facebook Post (Landscape)", 1200, 630, "Facebook"),
        CanvasPreset("Facebook Post (Square)", 1080, 1080, "Facebook"),
        CanvasPreset("Facebook Story", 1080, 1920, "Facebook"),
        CanvasPreset("Facebook Cover Photo", 820, 312, "Facebook"),
        CanvasPreset("Facebook Event Cover", 1920, 1005, "Facebook"),
        CanvasPreset("Facebook Ad", 1080, 1080, "Facebook"),
        CanvasPreset("Facebook App Ad", 1024, 1024, "Facebook"),
        # Instagram
        CanvasPreset("Instagram Post (Square)", 1080, 1080, "Instagram"),
        CanvasPreset("Instagram Post (Portrait)", 1080, 1350, "Instagram"),
        CanvasPreset("Instagram Story", 1080, 1920, "Instagram"),
        CanvasPreset("Instagram Reels Cover", 1080, 1920, "Instagram"),
        CanvasPreset("Instagram Ad", 1080, 1080, "Instagram"),
        # LinkedIn
        CanvasPreset("LinkedIn Post (Square)", 1200, 1200, "LinkedIn"),
        CanvasPreset("LinkedIn Post (Landscape)", 1200, 627, "LinkedIn"),
        CanvasPreset("LinkedIn Cover Photo", 1584, 396, "LinkedIn"),
        CanvasPreset("LinkedIn Company Logo", 300, 300, "LinkedIn"),
        # Pinterest
        CanvasPreset("Pinterest Pin (Standard)", 1000, 1500, "Pinterest"),
        CanvasPreset("Pinterest Pin (Square)", 1080, 1080, "Pinterest"),
        CanvasPreset("Pinterest Story Pin", 1080, 1920, "Pinterest"),
        CanvasPreset("Pinterest Board Cover", 600, 600, "Pinterest"),
        # TikTok
        CanvasPreset("TikTok Video", 1080, 1920, "TikTok"),
        CanvasPreset("TikTok Ad", 1080, 1920, "TikTok"),
        CanvasPreset("TikTok Profile Photo", 200, 200, "TikTok"),
        # Twitter
        CanvasPreset("Twitter Post", 1600, 900, "Twitter"),
        CanvasPreset("Twitter Header", 1500, 500, "Twitter"),
        CanvasPreset("Twitter Ad", 1200, 1200, "Twitter"),
        # YouTube
        CanvasPreset("YouTube Thumbnail", 1280, 720, "YouTube"),
        CanvasPreset("YouTube Channel Art", 2560, 1440, "YouTube"),
        CanvasPreset("YouTube Video", 1920, 1080, "YouTube"),
        CanvasPreset("YouTube Shorts", 1080, 1920, "YouTube"),
    ]

    def __init__(self) -> None:
        self.tasks: list[Task] = []
        self.projects: list[Project] = []
        self._untitled_count = 0
        # task/project id -> its current file/folder under PROJECTS_DIR, so
        # renames and moves know what to move/delete on disk.
        self._task_paths: dict[str, Path] = {}
        self._project_paths: dict[str, Path] = {}
        self._load_from_disk()

    # -- disk sync --------------------------------------------------------

    def _load_from_disk(self) -> None:
        PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
        for entry in sorted(PROJECTS_DIR.iterdir()):
            if entry.is_dir():
                project = Project(name=entry.name)
                self.projects.append(project)
                self._project_paths[project.id] = entry
                for task_file in sorted(entry.glob(f"*{storage.TASK_SUFFIX}")):
                    self._load_task_file(task_file, project_id=project.id)
            elif entry.suffix == storage.TASK_SUFFIX:
                self._load_task_file(entry, project_id=None)

    def _load_task_file(self, path: Path, project_id: str | None) -> None:
        try:
            task = storage.read_task(path)
        except (OSError, ValueError, KeyError):
            return  # skip unreadable/corrupt files rather than fail startup
        task.project_id = project_id
        self.tasks.append(task)
        self._task_paths[task.id] = path

        match = _UNTITLED_NAME_RE.match(task.name)
        if match:
            self._untitled_count = max(self._untitled_count, int(match.group(1)))

    def _write_task(self, task: Task) -> None:
        project_dir_name = None
        if task.project_id is not None:
            project_dir = self._project_paths.get(task.project_id)
            project_dir_name = project_dir.name if project_dir else None

        old_path = self._task_paths.get(task.id)
        path = storage.unique_path(storage.task_path(task, project_dir_name), own_current_path=old_path)
        if old_path is not None and old_path != path and old_path.exists():
            old_path.unlink(missing_ok=True)
        storage.write_task(path, task)
        self._task_paths[task.id] = path

    def list_categories(self) -> tuple[str, ...]:
        return self.CATEGORIES

    def list_presets(self, category: str | None = None) -> list[CanvasPreset]:
        if category is None:
            return self.PRESETS
        return [preset for preset in self.PRESETS if preset.category == category]

    def add_task(self, canvas_size: tuple[int, int], name: str | None = None) -> Task:
        """Create a blank-canvas task. Without an explicit name, auto-generates
        a sequential "Untitled Design N" -- the counter only ever increases, so
        names stay unique even after earlier tasks are deleted."""
        if name is None:
            self._untitled_count += 1
            name = f"Untitled Design {self._untitled_count}"
        task = Task(name=name, canvas_size=_clamp_canvas_size(canvas_size))
        self.tasks.append(task)
        self._write_task(task)
        return task

    def import_task(self, file_path: str) -> Task | None:
        """Create a task from a user-picked file, sized to its rendered
        dimensions. Returns None if the file isn't readable/supported."""
        pixmap = load_pixmap(file_path)
        if pixmap is None or pixmap.isNull():
            return None

        original_filename = os.path.basename(file_path)
        name, extension = os.path.splitext(original_filename)
        task = Task(
            name=name or original_filename,
            canvas_size=_clamp_canvas_size((pixmap.width(), pixmap.height())),
            file_path=file_path,
            original_filename=original_filename,
            file_type=extension.lstrip(".").lower(),
            file_size=os.path.getsize(file_path),
        )
        self.tasks.append(task)
        self._write_task(task)
        return task

    def recent_tasks(self) -> list[Task]:
        return sorted(self.tasks, key=lambda t: t.modified_at, reverse=True)

    def unassigned_tasks(self) -> list[Task]:
        return [t for t in self.tasks if t.project_id is None]

    def tasks_in_project(self, project_id: str) -> list[Task]:
        return [t for t in self.tasks if t.project_id == project_id]

    def create_project(self, name: str) -> Project:
        project = Project(name=name)
        self.projects.append(project)
        path = storage.unique_path(PROJECTS_DIR / sanitize_filename(name))
        path.mkdir(parents=True, exist_ok=True)
        self._project_paths[project.id] = path
        return project

    def move_task_to_project(self, task_id: str, project_id: str | None) -> None:
        for task in self.tasks:
            if task.id == task_id:
                task.project_id = project_id
                self._write_task(task)
                return

    def delete_task(self, task_id: str) -> None:
        path = self._task_paths.pop(task_id, None)
        if path is not None and path.exists():
            path.unlink()
        self.tasks = [task for task in self.tasks if task.id != task_id]

    def rename_task(self, task_id: str, name: str) -> None:
        for task in self.tasks:
            if task.id == task_id:
                task.name = name
                task.modified_at = datetime.now()
                self._write_task(task)
                return

    def save_task_content(self, task_id: str, content: dict[str, Any]) -> None:
        """Store a serialized editor snapshot (persistence.serialize_project)
        on the task, so reopening it restores exactly what was left behind."""
        for task in self.tasks:
            if task.id == task_id:
                task.content = content
                task.modified_at = datetime.now()
                self._write_task(task)
                return

    def delete_project(self, project_id: str) -> None:
        """Delete a project. Its tasks aren't deleted -- they become unassigned,
        and their files move back to the top-level projects/ folder."""
        tasks = self.tasks_in_project(project_id)
        for task in tasks:
            task.project_id = None
        self.projects = [project for project in self.projects if project.id != project_id]

        old_dir = self._project_paths.pop(project_id, None)
        for task in tasks:
            self._write_task(task)
        if old_dir is not None and old_dir.exists():
            try:
                old_dir.rmdir()
            except OSError:
                pass  # not empty (unexpected leftover files) -- leave it rather than force-delete

    def rename_project(self, project_id: str, name: str) -> None:
        for project in self.projects:
            if project.id != project_id:
                continue
            project.name = name

            old_dir = self._project_paths.get(project_id)
            new_dir = storage.unique_path(PROJECTS_DIR / sanitize_filename(name), own_current_path=old_dir)
            if old_dir is not None and old_dir != new_dir and old_dir.exists():
                new_dir.parent.mkdir(parents=True, exist_ok=True)
                old_dir.rename(new_dir)
                for task in self.tasks_in_project(project_id):
                    old_task_path = self._task_paths.get(task.id)
                    if old_task_path is not None:
                        self._task_paths[task.id] = new_dir / old_task_path.name
            self._project_paths[project_id] = new_dir
            return
