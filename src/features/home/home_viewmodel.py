from __future__ import annotations

from dataclasses import dataclass

from src.features.home.models import Project, Task


@dataclass(frozen=True)
class CanvasPreset:
    name: str
    width: int
    height: int


class HomeViewModel:
    """Owns the in-memory Home screen state: canvas presets, recent tasks, and projects."""

    PRESETS: list[CanvasPreset] = [
        CanvasPreset("Default", 800, 600),
        CanvasPreset("Instagram Post", 1080, 1080),
        CanvasPreset("Instagram Story", 1080, 1920),
        CanvasPreset("Presentation (16:9)", 1920, 1080),
        CanvasPreset("A4 Document", 794, 1123),
    ]

    def __init__(self) -> None:
        # Sample data so the Home/Projects UI has something to show before real
        # save/load of designs exists.
        self.tasks: list[Task] = [
            Task(name="Summer Sale Post", canvas_size=(1080, 1080)),
            Task(name="Event Flyer", canvas_size=(794, 1123)),
            Task(name="Team Slide Deck", canvas_size=(1920, 1080)),
        ]
        self.projects: list[Project] = []

    def list_presets(self) -> list[CanvasPreset]:
        return self.PRESETS

    def add_task(self, name: str, canvas_size: tuple[int, int]) -> Task:
        task = Task(name=name, canvas_size=canvas_size)
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
