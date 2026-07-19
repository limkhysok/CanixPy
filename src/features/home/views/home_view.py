from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QMouseEvent, QResizeEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.core import icons, theme
from src.features.home.models.models import Project, Task
from src.features.home.viewmodels.home_viewmodel import HomeViewModel
from src.features.home.views.layout.left_sidebar import LeftSidebar
from src.features.home.views.layout.navbar import Navbar
from src.features.home.views.widgets.canvas_size_dialog import CanvasSizeDialog

CONTENT_STYLE = f"""
QLabel#pageTitle {{
    font-size: 26px;
    font-weight: 500;
    color: {theme.TEXT_PRIMARY};
}}
QLabel#sectionHeader {{
    font-size: 18px;
    font-weight: 500;
    color: {theme.TEXT_PRIMARY};
}}
QLabel#sectionCount {{
    color: {theme.TEXT_SECONDARY};
    font-size: 13px;
}}
QLabel#hintText {{
    color: {theme.TEXT_SECONDARY};
    font-size: 12px;
}}
QListWidget {{
    padding: 6px;
}}
QListWidget::item {{
    padding: 12px 10px;
    border-bottom: 1px solid {theme.BORDER};
    font-size: 15px;
}}
QListWidget#recentList {{
    padding: 0px;
    border: none;
}}
QListWidget#recentList::item {{
    padding: 0px;
    border: none;
}}
QWidget#recentCard {{
    background-color: {theme.BACKGROUND};
    border: 1px solid {theme.BORDER};
    border-radius: 8px;
}}
QLabel#recentThumbnail {{
    background-color: {theme.ACCENT_LIGHT};
    border-radius: 6px;
}}
QLabel#recentCardTitle {{
    font-size: 14px;
    font-weight: 600;
    color: {theme.TEXT_PRIMARY};
}}
QLabel#recentCardMeta {{
    font-size: 12px;
    color: {theme.TEXT_SECONDARY};
}}
"""

TASK_ICON = "fa5s.file-alt"

RECENT_THUMBNAIL_HEIGHT = 64
RECENT_CARD_HEIGHT = 156
RECENT_CARD_SPACING = 10
RECENT_CARD_MIN_WIDTH = 150
# (min viewport width, columns) breakpoints, widest first -- desktop/tablet/mobile.
RECENT_BREAKPOINTS = ((850, 4), (550, 3), (0, 2))


def _recent_columns_for_width(width: int) -> int:
    """Pick how many recent-task cards fit per row for a given viewport width."""
    for min_width, columns in RECENT_BREAKPOINTS:
        if width >= min_width:
            return columns
    return RECENT_BREAKPOINTS[-1][1]


class _RecentTaskList(QListWidget):
    """A horizontal QListWidget that reports its own resizes so cards can adapt."""

    resized = Signal()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.resized.emit()


class _RecentTaskCard(QWidget):
    """A single recent-task card: thumbnail, then title / size / edited-time rows."""

    activated = Signal()

    def __init__(self, task: Task, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("recentCard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._full_title = task.name

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        self.thumbnail = QLabel()
        self.thumbnail.setObjectName("recentThumbnail")
        self.thumbnail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail.setMinimumHeight(RECENT_THUMBNAIL_HEIGHT)
        self.thumbnail.setPixmap(icons.icon(TASK_ICON, color=theme.ACCENT).pixmap(28, 28))
        layout.addWidget(self.thumbnail)

        self.title_label = QLabel()
        self.title_label.setObjectName("recentCardTitle")
        layout.addWidget(self.title_label)

        width, height = task.canvas_size
        size_label = QLabel(f"{width} x {height}")
        size_label.setObjectName("recentCardMeta")
        layout.addWidget(size_label)

        relative_time = _format_relative_time(task.modified_at)
        edited_label = QLabel(f"Edited {relative_time}")
        edited_label.setObjectName("recentCardMeta")
        layout.addWidget(edited_label)

        self.setToolTip(f"Last edited {task.modified_at.strftime('%b %d, %Y at %I:%M %p')}")
        self._update_title_elide()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._update_title_elide()

    def _update_title_elide(self) -> None:
        metrics = self.title_label.fontMetrics()
        elided = metrics.elidedText(self._full_title, Qt.TextElideMode.ElideRight, self.width() - 4)
        self.title_label.setText(elided)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        super().mouseDoubleClickEvent(event)
        self.activated.emit()


def _format_relative_time(when: datetime) -> str:
    """Humanize a timestamp relative to now, e.g. '5 minutes ago'."""
    seconds = max(0, (datetime.now() - when).total_seconds())

    if seconds < 60:
        return "Just now"
    minutes = int(seconds // 60)
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    hours = int(seconds // 3600)
    if hours < 24:
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    days = int(seconds // 86400)
    if days < 7:
        return f"{days} day{'s' if days != 1 else ''} ago"
    return when.strftime("%b %d, %Y")


class HomeView(QWidget):
    """The Home Screen: a left nav (Home / Projects) plus the active page."""

    open_editor = Signal(int, int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.viewmodel = HomeViewModel()
        self.current_project: Project | None = None
        self.setStyleSheet(CONTENT_STYLE)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.left_sidebar = LeftSidebar()
        self.left_sidebar.page_selected.connect(self._on_page_selected)
        layout.addWidget(self.left_sidebar)

        content_column = QWidget()
        content_layout = QVBoxLayout(content_column)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self.navbar = Navbar()
        self.navbar.toggle_clicked.connect(self.left_sidebar.set_collapsed)
        content_layout.addWidget(self.navbar)

        self.pages = QStackedWidget()
        content_layout.addWidget(self.pages, 1)

        layout.addWidget(content_column, 1)

        self.home_page = self._build_home_page()
        self.pages.addWidget(self.home_page)

        self.projects_root = QStackedWidget()
        self.projects_root.addWidget(self._build_projects_list_page())
        self.projects_root.addWidget(self._build_project_detail_page())
        self.pages.addWidget(self.projects_root)

        self.pages.setCurrentWidget(self.home_page)

    def _on_page_selected(self, page_name: str) -> None:
        if page_name == "projects":
            self._refresh_projects_page()
            self.pages.setCurrentWidget(self.projects_root)
        else:
            self._refresh_home_page()
            self.pages.setCurrentWidget(self.home_page)

    # ---- Home page ---------------------------------------------------

    def _build_home_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 32, 40, 32)
        layout.setSpacing(12)

        title = QLabel("CanixPy")
        title.setObjectName("pageTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(title)

        btn_new_design = QPushButton(icons.icon("fa5s.plus", color=theme.TEXT_ON_ACCENT), "New Design")
        btn_new_design.setProperty("accent", True)
        btn_new_design.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_new_design.setFixedWidth(200)
        btn_new_design.clicked.connect(self._on_new_design)
        layout.addWidget(btn_new_design, alignment=Qt.AlignmentFlag.AlignHCenter)

        layout.addSpacing(16)

        header_row = QVBoxLayout()
        header_row.setSpacing(2)
        self.section_header = QLabel("Recent")
        self.section_header.setObjectName("sectionHeader")
        header_row.addWidget(self.section_header)
        self.section_count = QLabel()
        self.section_count.setObjectName("sectionCount")
        header_row.addWidget(self.section_count)
        layout.addLayout(header_row)

        self.recent_list = _RecentTaskList()
        self.recent_list.setObjectName("recentList")
        self.recent_list.setCursor(Qt.CursorShape.PointingHandCursor)
        self.recent_list.setIconSize(self.recent_list.iconSize() * 1.2)
        self.recent_list.setFlow(QListWidget.Flow.LeftToRight)
        self.recent_list.setWrapping(True)
        self.recent_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.recent_list.setSpacing(RECENT_CARD_SPACING)
        self.recent_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.recent_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.recent_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.recent_list.setMinimumHeight(RECENT_CARD_HEIGHT)
        self.recent_list.resized.connect(self._update_recent_card_sizes)
        layout.addWidget(self.recent_list, 1)

        self._refresh_home_page()
        return page

    def _refresh_home_page(self) -> None:
        self.recent_list.clear()
        tasks = self.viewmodel.recent_tasks()

        count = len(tasks)
        self.section_count.setText(f"{count} design{'s' if count != 1 else ''}")

        if not tasks:
            placeholder = QListWidgetItem(
                icons.icon("fa5s.inbox", color=theme.TEXT_SECONDARY),
                "No designs yet — click “New Design” to get started.",
            )
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            placeholder.setForeground(QBrush(QColor(theme.TEXT_SECONDARY)))
            self.recent_list.addItem(placeholder)
            self._update_recent_card_sizes()
            return

        for task in tasks:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, task)
            self.recent_list.addItem(item)

            card = _RecentTaskCard(task)
            card.activated.connect(lambda task=task: self._open_recent_task(task))
            self.recent_list.setItemWidget(item, card)

        self._update_recent_card_sizes()

    def _update_recent_card_sizes(self) -> None:
        """Resize recent-task cards so a fixed column count fits per row: 4 on
        desktop-width viewports, 3 on tablet, 2 on narrower/mobile widths."""
        if self.recent_list.count() == 0:
            return

        viewport_width = max(self.recent_list.viewport().width(), 1)
        spacing = self.recent_list.spacing()

        first_item = self.recent_list.item(0)
        if first_item.flags() == Qt.ItemFlag.NoItemFlags:
            first_item.setSizeHint(QSize(max(1, viewport_width - 2 * spacing), RECENT_CARD_HEIGHT))
            return

        columns = _recent_columns_for_width(viewport_width)
        # Qt reserves `spacing` on *both* sides of every item (not just between
        # items), so each column's footprint is card_width + 2 * spacing. A small
        # buffer avoids an exact-width boundary case where Qt's flow layout wraps
        # one column early.
        usable_width = viewport_width - 2
        card_width = max(RECENT_CARD_MIN_WIDTH, usable_width // columns - 2 * spacing)
        for index in range(self.recent_list.count()):
            self.recent_list.item(index).setSizeHint(QSize(card_width, RECENT_CARD_HEIGHT))

    def _open_recent_task(self, task: Task) -> None:
        width, height = task.canvas_size
        self.open_editor.emit(width, height)

    def _on_new_design(self) -> None:
        dialog = CanvasSizeDialog(self.viewmodel, self)
        if dialog.exec() == CanvasSizeDialog.DialogCode.Accepted:
            width, height = dialog.selected_size()
            name = f"Untitled Design {len(self.viewmodel.tasks) + 1}"
            self.viewmodel.add_task(name, (width, height))
            self._refresh_home_page()
            self.open_editor.emit(width, height)

    # ---- Projects page -------------------------------------------------

    def _build_projects_list_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 32, 40, 32)
        layout.setSpacing(12)

        title = QLabel("Projects")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        self.project_count = QLabel()
        self.project_count.setObjectName("sectionCount")
        layout.addWidget(self.project_count)

        layout.addSpacing(8)

        btn_new_project = QPushButton(icons.icon("fa5s.folder-plus", color=theme.TEXT_ON_ACCENT), "New Project")
        btn_new_project.setProperty("accent", True)
        btn_new_project.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_new_project.clicked.connect(self._on_new_project)
        layout.addWidget(btn_new_project)

        hint = QLabel("Double-click a project to open it.")
        hint.setObjectName("hintText")
        layout.addWidget(hint)

        self.project_list = QListWidget()
        self.project_list.setCursor(Qt.CursorShape.PointingHandCursor)
        self.project_list.setIconSize(self.project_list.iconSize() * 1.2)
        self.project_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.project_list.itemDoubleClicked.connect(self._on_project_opened)
        layout.addWidget(self.project_list)

        return page

    def _build_project_detail_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 32, 40, 32)
        layout.setSpacing(12)

        btn_back = QPushButton(icons.icon("fa5s.arrow-left"), "Back to Projects")
        btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_back.clicked.connect(self._show_projects_list_page)
        layout.addWidget(btn_back)

        self.detail_title = QLabel()
        self.detail_title.setObjectName("pageTitle")
        layout.addWidget(self.detail_title)

        layout.addSpacing(8)
        layout.addWidget(QLabel("Tasks in this project:"))
        self.detail_task_list = QListWidget()
        self.detail_task_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.detail_task_list)

        layout.addWidget(QLabel("Unassigned tasks (select one to move here):"))
        self.unassigned_list = QListWidget()
        self.unassigned_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.unassigned_list)

        btn_move = QPushButton(icons.icon("fa5s.arrow-right"), "Move selected task here")
        btn_move.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_move.clicked.connect(self._on_move_task)
        layout.addWidget(btn_move)

        return page

    def _refresh_projects_page(self) -> None:
        self.project_list.clear()
        projects = self.viewmodel.projects

        count = len(projects)
        self.project_count.setText(f"{count} project{'s' if count != 1 else ''}")

        if not projects:
            placeholder = QListWidgetItem(
                icons.icon("fa5s.folder-open", color=theme.TEXT_SECONDARY),
                "No projects yet — click “New Project” to create one.",
            )
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            placeholder.setForeground(QBrush(QColor(theme.TEXT_SECONDARY)))
            self.project_list.addItem(placeholder)
        else:
            for project in projects:
                task_count = len(self.viewmodel.tasks_in_project(project.id))
                label = f"{project.name}   ·   {task_count} task{'s' if task_count != 1 else ''}"
                item = QListWidgetItem(icons.icon("fa5s.folder", color=theme.ACCENT), label)
                item.setData(Qt.ItemDataRole.UserRole, project)
                self.project_list.addItem(item)

        if self.current_project is not None:
            self._refresh_project_detail_page()

    def _on_new_project(self) -> None:
        name, ok = QInputDialog.getText(self, "New Project", "Project name:")
        if ok and name.strip():
            self.viewmodel.create_project(name.strip())
            self._refresh_projects_page()

    def _on_project_opened(self, item: QListWidgetItem) -> None:
        self.current_project = item.data(Qt.ItemDataRole.UserRole)
        self._refresh_project_detail_page()
        self.projects_root.setCurrentIndex(1)

    def _show_projects_list_page(self) -> None:
        self.current_project = None
        self.projects_root.setCurrentIndex(0)

    def _refresh_project_detail_page(self) -> None:
        assert self.current_project is not None
        self.detail_title.setText(self.current_project.name)

        self.detail_task_list.clear()
        tasks_in_project = self.viewmodel.tasks_in_project(self.current_project.id)
        if not tasks_in_project:
            placeholder = QListWidgetItem("No tasks in this project yet.")
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            placeholder.setForeground(QBrush(QColor(theme.TEXT_SECONDARY)))
            self.detail_task_list.addItem(placeholder)
        else:
            for task in tasks_in_project:
                width, height = task.canvas_size
                text = f"{task.name}   ·   {width} x {height}"
                self.detail_task_list.addItem(QListWidgetItem(icons.icon(TASK_ICON, color=theme.ACCENT), text))

        self.unassigned_list.clear()
        unassigned = self.viewmodel.unassigned_tasks()
        if not unassigned:
            placeholder = QListWidgetItem("Nothing to move — every task is already in a project.")
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            placeholder.setForeground(QBrush(QColor(theme.TEXT_SECONDARY)))
            self.unassigned_list.addItem(placeholder)
        else:
            for task in unassigned:
                width, height = task.canvas_size
                item = QListWidgetItem(icons.icon(TASK_ICON, color=theme.ACCENT), f"{task.name}   ·   {width} x {height}")
                item.setData(Qt.ItemDataRole.UserRole, task)
                self.unassigned_list.addItem(item)

    def _on_move_task(self) -> None:
        item = self.unassigned_list.currentItem()
        if item is None or self.current_project is None:  # pyright: ignore[reportUnnecessaryComparison]
            return
        task = item.data(Qt.ItemDataRole.UserRole)
        if task is None:
            return
        self.viewmodel.move_task_to_project(task.id, self.current_project.id)
        self._refresh_projects_page()
