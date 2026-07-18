from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QSize, Signal, Qt, QVariantAnimation
from PySide6.QtWidgets import QButtonGroup, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from src.core import icons, theme

LEFT_SIDEBAR_STYLE = f"""
LeftSidebar {{
    background-color: {theme.SURFACE};
    border-right: 1px solid {theme.BORDER};
}}
QPushButton#navButton {{
    background-color: transparent;
    border: none;
    border-radius: 8px;
}}
QPushButton#navButton:hover {{
    background-color: {theme.BORDER};
}}
QPushButton#navButton:checked {{
    background-color: {theme.ACCENT_LIGHT};
}}
QLabel#navButtonLabel {{
    background: transparent;
    font-size: 17px;
}}
QLabel#navButtonIcon {{
    background: transparent;
}}
"""

NAV_ITEMS = [
    ("fa5s.home", "Home"),
    ("fa5.folder", "Projects"),
]

ICON_SIZE = QSize(18, 18)
ROW_MARGIN_V = 8
ROW_MARGIN_H_EXPANDED = 14
ROW_MARGIN_H_COLLAPSED = 0  # tight enough to center the icon within LeftSidebar.COLLAPSED_WIDTH


class NavButton(QPushButton):
    """A checkable nav row with an icon and label kept in true vertical alignment.

    QPushButton's built-in icon+text layout centers the icon's pixmap box and
    the text's font box independently -- with qtawesome glyphs (which carry
    their own internal padding) that leaves the label looking offset from the
    icon. Laying both out explicitly in a QHBoxLayout avoids that.
    """

    def __init__(self, icon_name: str, label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("navButton")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._icon_name = icon_name
        self.label_text = label

        row = QHBoxLayout(self)
        row.setContentsMargins(ROW_MARGIN_H_EXPANDED, ROW_MARGIN_V, ROW_MARGIN_H_EXPANDED, ROW_MARGIN_V)
        row.setSpacing(10)

        self.icon_label = QLabel()
        self.icon_label.setObjectName("navButtonIcon")
        self.icon_label.setFixedSize(ICON_SIZE)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(self.icon_label)

        self.text_label = QLabel(label)
        self.text_label.setObjectName("navButtonLabel")
        row.addWidget(self.text_label, 1)

        self.toggled.connect(self._restyle)
        self._restyle(False)

    def sizeHint(self) -> QSize:
        # QPushButton.sizeHint() normally derives from the button's own text/icon,
        # which are empty here -- delegate to the row layout that actually holds content.
        layout = self.layout()
        assert layout is not None
        return layout.sizeHint()

    def minimumSizeHint(self) -> QSize:
        layout = self.layout()
        assert layout is not None
        return layout.minimumSize()

    def _restyle(self, checked: bool) -> None:
        color = theme.ACCENT if checked else theme.TEXT_PRIMARY
        self.icon_label.setPixmap(icons.icon(self._icon_name, color=color).pixmap(ICON_SIZE))

        weight = 600 if checked else 500
        self.text_label.setStyleSheet(f"color: {color}; font-weight: {weight};")

    def set_collapsed(self, collapsed: bool) -> None:
        self.text_label.setVisible(not collapsed)
        self.setToolTip(self.label_text if collapsed else "")

        side_margin = ROW_MARGIN_H_COLLAPSED if collapsed else ROW_MARGIN_H_EXPANDED
        layout = self.layout()
        assert layout is not None
        layout.setContentsMargins(side_margin, ROW_MARGIN_V, side_margin, ROW_MARGIN_V)


class LeftSidebar(QWidget):
    """Left navigation between the Home (recent work) and Projects (folders) pages."""

    page_selected = Signal(str)  # "home" | "projects"

    EXPANDED_WIDTH = 220
    COLLAPSED_WIDTH = 48
    ANIMATION_DURATION_MS = 200

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(LEFT_SIDEBAR_STYLE)
        self._collapsed = False

        self._width_animation = QVariantAnimation(self)
        self._width_animation.setDuration(self.ANIMATION_DURATION_MS)
        self._width_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._width_animation.valueChanged.connect(self.setFixedWidth)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        nav_layout = QVBoxLayout()
        nav_layout.setContentsMargins(8, 8, 8, 8)
        nav_layout.setSpacing(4)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons: list[NavButton] = []

        for row, (icon_name, label) in enumerate(NAV_ITEMS):
            button = NavButton(icon_name, label)
            self.nav_group.addButton(button, row)
            self.nav_buttons.append(button)
            nav_layout.addWidget(button)

        nav_layout.addStretch()
        layout.addLayout(nav_layout)

        self.nav_group.idClicked.connect(self._on_nav_clicked)
        self.nav_buttons[0].setChecked(True)

        self.setFixedWidth(self.EXPANDED_WIDTH)

    def set_collapsed(self, collapsed: bool) -> None:
        self._collapsed = collapsed

        for button in self.nav_buttons:
            button.set_collapsed(collapsed)

        self._width_animation.stop()
        self._width_animation.setStartValue(self.width())
        self._width_animation.setEndValue(self.COLLAPSED_WIDTH if collapsed else self.EXPANDED_WIDTH)
        self._width_animation.start()

    def _on_nav_clicked(self, row: int) -> None:
        self.page_selected.emit("projects" if row == 1 else "home")
