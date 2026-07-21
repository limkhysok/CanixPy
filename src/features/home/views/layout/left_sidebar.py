from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEasingCurve, QSize, Signal, Qt, QVariantAnimation
from PySide6.QtWidgets import QButtonGroup, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from src.core import icons, theme

LEFT_SIDEBAR_STYLE = theme.load_qss(Path(__file__).with_name("left_sidebar.qss"))

ICON_SIZE = QSize(18, 18)
SETTINGS_BUTTON_SIZE = QSize(28, 28)
SETTINGS_ICON_SIZE = QSize(14, 14)
ROW_MARGIN_V = 10
ROW_MARGIN_H_EXPANDED = 14
ROW_MARGIN_H_COLLAPSED = 0  # tight enough to center the icon within LeftSidebar.COLLAPSED_WIDTH
PROFILE_MARGIN_V = 12


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
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self._icon_name = icon_name
        self.label_text = label

        row = QHBoxLayout(self)
        row.setContentsMargins(ROW_MARGIN_H_EXPANDED, ROW_MARGIN_V, ROW_MARGIN_H_EXPANDED, ROW_MARGIN_V)
        row.setSpacing(10)

        self.icon_label = QLabel()
        self.icon_label.setObjectName("navButtonIcon")
        self.icon_label.setFixedSize(ICON_SIZE)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignVCenter)

        self.text_label = QLabel(label)
        self.text_label.setObjectName("navButtonLabel")
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(self.text_label, 1, Qt.AlignmentFlag.AlignVCenter)

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

    def apply_collapse_fraction(self, fraction: float) -> None:
        """Drive margins and label visibility from the sidebar's width-animation
        progress (0.0 fully expanded, 1.0 fully collapsed) instead of snapping
        them the moment a toggle is requested. Margins interpolate every frame so
        the icon doesn't jump; the label is only ever visible once the sidebar is
        fully expanded, so it never gets laid out wider than a still-narrow row.
        """
        side_margin = round(ROW_MARGIN_H_EXPANDED + (ROW_MARGIN_H_COLLAPSED - ROW_MARGIN_H_EXPANDED) * fraction)
        layout = self.layout()
        assert layout is not None
        layout.setContentsMargins(side_margin, ROW_MARGIN_V, side_margin, ROW_MARGIN_V)

        expanded = fraction <= 0.0
        self.text_label.setVisible(expanded)
        self.setToolTip("" if expanded else self.label_text)


class ProfileFooter(QWidget):
    """Bottom-of-sidebar row: avatar, display name, and a settings entry point.

    Placeholder identity only -- there's no auth/user backend yet, so this
    always shows a generic "Guest User". The settings button is wired up so
    real behavior can be dropped in later without touching layout code.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("profileFooter")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        row = QHBoxLayout(self)
        row.setContentsMargins(ROW_MARGIN_H_EXPANDED, PROFILE_MARGIN_V, ROW_MARGIN_H_EXPANDED, PROFILE_MARGIN_V)
        row.setSpacing(10)

        self.avatar_label = QLabel()
        self.avatar_label.setObjectName("profileAvatar")
        self.avatar_label.setFixedSize(ICON_SIZE)
        self.avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avatar_label.setPixmap(icons.icon("fa5s.user-circle", color=theme.TEXT_SECONDARY).pixmap(ICON_SIZE))
        row.addWidget(self.avatar_label, 0, Qt.AlignmentFlag.AlignVCenter)

        self.name_label = QLabel("Guest User")
        self.name_label.setObjectName("profileName")
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(self.name_label, 1, Qt.AlignmentFlag.AlignVCenter)

        self.settings_button = QPushButton(icons.icon("fa5s.cog", color=theme.TEXT_SECONDARY), "")
        self.settings_button.setObjectName("profileSettingsButton")
        self.settings_button.setIconSize(SETTINGS_ICON_SIZE)
        self.settings_button.setFixedSize(SETTINGS_BUTTON_SIZE)
        self.settings_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.settings_button.setToolTip("Settings")
        self.settings_button.clicked.connect(self._on_settings_clicked)
        row.addWidget(self.settings_button, 0, Qt.AlignmentFlag.AlignVCenter)

    def _on_settings_clicked(self) -> None:
        pass  # placeholder until account settings/auth exist

    def apply_collapse_fraction(self, fraction: float) -> None:
        """Mirror NavButton.apply_collapse_fraction so the footer collapses to
        just the avatar in lockstep with the nav rows above it."""
        side_margin = round(ROW_MARGIN_H_EXPANDED + (ROW_MARGIN_H_COLLAPSED - ROW_MARGIN_H_EXPANDED) * fraction)
        layout = self.layout()
        assert layout is not None
        layout.setContentsMargins(side_margin, PROFILE_MARGIN_V, side_margin, PROFILE_MARGIN_V)

        expanded = fraction <= 0.0
        self.name_label.setVisible(expanded)
        self.settings_button.setVisible(expanded)
        self.setToolTip("" if expanded else "Guest User")


class LeftSidebar(QWidget):
    """Left navigation between the Home (recent work) and Projects (folders) pages."""

    page_selected = Signal(str)  # "home" | "projects"

    EXPANDED_WIDTH = 220
    COLLAPSED_WIDTH = 54
    ANIMATION_DURATION_MS = 200

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(LEFT_SIDEBAR_STYLE)
        self._collapsed = False

        self._width_animation = QVariantAnimation(self)
        self._width_animation.setDuration(self.ANIMATION_DURATION_MS)
        self._width_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._width_animation.valueChanged.connect(self._on_width_animation_value_changed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        nav_layout = QVBoxLayout()
        nav_layout.setContentsMargins(8, 8, 8, 8)
        nav_layout.setSpacing(4)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)

        self.home_button = NavButton("fa5s.home", "Home")
        self.nav_group.addButton(self.home_button, 0)
        nav_layout.addWidget(self.home_button)

        self.projects_button = NavButton("fa5.folder", "Projects")
        self.nav_group.addButton(self.projects_button, 1)
        nav_layout.addWidget(self.projects_button)

        self.nav_buttons: list[NavButton] = [self.home_button, self.projects_button]

        nav_layout.addStretch()
        layout.addLayout(nav_layout)

        self.profile_footer = ProfileFooter()
        layout.addWidget(self.profile_footer)

        self._collapsible_widgets: list[NavButton | ProfileFooter] = [*self.nav_buttons, self.profile_footer]

        self.nav_group.idClicked.connect(self._on_nav_clicked)
        self.nav_buttons[0].setChecked(True)

        self.setFixedWidth(self.EXPANDED_WIDTH)

    def set_collapsed(self, collapsed: bool) -> None:
        self._collapsed = collapsed

        self._width_animation.stop()
        self._width_animation.setStartValue(self.width())
        self._width_animation.setEndValue(self.COLLAPSED_WIDTH if collapsed else self.EXPANDED_WIDTH)
        self._width_animation.start()

    def _on_width_animation_value_changed(self, value: int) -> None:
        self.setFixedWidth(value)

        span = self.EXPANDED_WIDTH - self.COLLAPSED_WIDTH
        fraction = (self.EXPANDED_WIDTH - value) / span
        for widget in self._collapsible_widgets:
            widget.apply_collapse_fraction(fraction)

    def _on_nav_clicked(self, row: int) -> None:
        self.page_selected.emit("projects" if row == 1 else "home")
