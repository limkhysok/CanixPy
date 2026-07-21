from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from PySide6.QtGui import QImageReader

from src.features.home.models.models import Project, Task

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
        # Sample data so the Home/Projects UI has something to show before real
        # save/load of designs exists.
        self.tasks: list[Task] = [
            Task(name="Summer Sale Post", canvas_size=(1080, 1080)),
            Task(name="Event Flyer", canvas_size=(794, 1123)),
            Task(name="Team Slide Deck", canvas_size=(1920, 1080)),
            Task(name="Instagram Story Ad", canvas_size=(1080, 1920)),
            Task(name="Product Launch Banner", canvas_size=(1920, 1080)),
            Task(name="Business Card", canvas_size=(1050, 600)),
        ]
        self.projects: list[Project] = []
        self._untitled_count = 0

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
        return task

    def import_task(self, file_path: str) -> Task | None:
        """Create a task from a user-picked image file, sized to the image's
        own dimensions. Returns None if the file isn't a readable image."""
        reader = QImageReader(file_path)
        size = reader.size()
        if not size.isValid():
            return None

        original_filename = os.path.basename(file_path)
        name, extension = os.path.splitext(original_filename)
        task = Task(
            name=name or original_filename,
            canvas_size=_clamp_canvas_size((size.width(), size.height())),
            file_path=file_path,
            original_filename=original_filename,
            file_type=extension.lstrip(".").lower(),
            file_size=os.path.getsize(file_path),
        )
        self.tasks.append(task)
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
        return project

    def move_task_to_project(self, task_id: str, project_id: str | None) -> None:
        for task in self.tasks:
            if task.id == task_id:
                task.project_id = project_id
                return

    def delete_task(self, task_id: str) -> None:
        self.tasks = [task for task in self.tasks if task.id != task_id]

    def rename_task(self, task_id: str, name: str) -> None:
        for task in self.tasks:
            if task.id == task_id:
                task.name = name
                task.modified_at = datetime.now()
                return

    def save_task_content(self, task_id: str, content: dict[str, Any]) -> None:
        """Store a serialized editor snapshot (persistence.serialize_project)
        on the task, so reopening it restores exactly what was left behind."""
        for task in self.tasks:
            if task.id == task_id:
                task.content = content
                task.modified_at = datetime.now()
                return

    def delete_project(self, project_id: str) -> None:
        """Delete a project. Its tasks aren't deleted -- they become unassigned."""
        self.projects = [project for project in self.projects if project.id != project_id]
        for task in self.tasks:
            if task.project_id == project_id:
                task.project_id = None

    def rename_project(self, project_id: str, name: str) -> None:
        for project in self.projects:
            if project.id == project_id:
                project.name = name
                return
