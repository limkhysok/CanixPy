from __future__ import annotations

import os
from dataclasses import dataclass

from PySide6.QtGui import QImageReader

from src.features.home.models.models import Project, Task


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

    def list_categories(self) -> tuple[str, ...]:
        return self.CATEGORIES

    def list_presets(self, category: str | None = None) -> list[CanvasPreset]:
        if category is None:
            return self.PRESETS
        return [preset for preset in self.PRESETS if preset.category == category]

    def add_task(self, name: str, canvas_size: tuple[int, int]) -> Task:
        task = Task(name=name, canvas_size=canvas_size)
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
            canvas_size=(size.width(), size.height()),
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
