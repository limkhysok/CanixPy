from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QMouseEvent, QResizeEvent
from PySide6.QtWidgets import (
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.core import icons, theme
from src.features.home.models.models import Task
from src.features.home.viewmodels.home_viewmodel import HomeViewModel
from src.features.home.views.widgets.canvas_size_dialog import CanvasSizeDialog

RECENT_PAGE_STYLE = f"""
QListWidget#recentList {{
    padding: 0px;
    border: none;
    outline: none;
}}
QListWidget#recentList::item {{
    padding: 0px;
    border: none;
    outline: none;
}}
QListWidget#recentList::item:focus {{
    outline: none;
    border: none;
}}
QWidget#recentCard {{
    background-color: {theme.BACKGROUND};
    border: 1px solid {theme.BORDER};
    border-radius: 8px;
}}
QWidget#recentCard:hover {{
    background-color: {theme.ACCENT_LIGHT};
    border: 1px solid {theme.ACCENT};
}}
QLabel#recentThumbnail {{
    background-color: {theme.ACCENT_LIGHT};
    border-radius: 6px;
}}
QLabel#recentCardTitle {{
    background-color: transparent;
    font-size: 17px;
    font-weight: 500;
    color: {theme.TEXT_PRIMARY};
}}
QLabel#recentCardMeta {{
    background-color: transparent;
    font-size: 12px;
    color: {theme.TEXT_SECONDARY};
}}
"""

TASK_ICON = "fa5s.file-alt"

RECENT_THUMBNAIL_HEIGHT = 64
RECENT_CARD_HEIGHT = 162
RECENT_CARD_SPACING = 10
RECENT_CARD_MIN_WIDTH = 150
# (min viewport width, columns) breakpoints, widest first -- desktop/tablet/mobile.
RECENT_BREAKPOINTS = ((850, 5), (550, 4), (0, 3))


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
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._full_title = task.name

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(4)

        self.thumbnail = QLabel()
        self.thumbnail.setObjectName("recentThumbnail")
        self.thumbnail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail.setMinimumHeight(RECENT_THUMBNAIL_HEIGHT)
        self.thumbnail.setPixmap(icons.icon(TASK_ICON, color=theme.ACCENT).pixmap(28, 28))
        layout.addWidget(self.thumbnail)
        layout.addSpacing(8)

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
        elided = metrics.elidedText(self._full_title, Qt.TextElideMode.ElideRight, self.title_label.width())
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


class HomePage(QWidget):
    """The Home page: New Design button plus a grid of recent-task cards."""

    open_editor = Signal(int, int)

    def __init__(self, viewmodel: HomeViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.viewmodel = viewmodel
        self.setStyleSheet(RECENT_PAGE_STYLE)

        layout = QVBoxLayout(self)
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
        self.recent_list.setIconSize(self.recent_list.iconSize() * 1.2)
        self.recent_list.setFlow(QListWidget.Flow.LeftToRight)
        self.recent_list.setWrapping(True)
        self.recent_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.recent_list.setSpacing(RECENT_CARD_SPACING)
        # Qt's flow layout also reserves a leading/trailing `spacing` gap around
        # the first/last item in each row, not just between items -- which insets
        # the whole card row relative to the title/header text above it. Claw
        # that back so the first card lines up flush with the page content.
        self.recent_list.setViewportMargins(-RECENT_CARD_SPACING, 0, -RECENT_CARD_SPACING, 0)
        self.recent_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.recent_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.recent_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.recent_list.setMinimumHeight(RECENT_CARD_HEIGHT)
        self.recent_list.resized.connect(self._update_recent_card_sizes)
        layout.addWidget(self.recent_list, 1)

        self.refresh()

    def refresh(self) -> None:
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
            self.refresh()
            self.open_editor.emit(width, height)
