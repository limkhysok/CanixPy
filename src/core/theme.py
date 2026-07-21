"""Central design tokens for CanixPy's light theme.

Concept: white background, Sage Green as the single accent color -- a
muted, earthy gray-green inspired by the silvery-green leaves of the
Mediterranean sage plant. Buttons that should get the accent treatment
opt in via the Qt dynamic property `accent`, e.g.
`button.setProperty("accent", True)`.
"""
from __future__ import annotations

# Backgrounds
BACKGROUND = "#FFFFFF"
SURFACE = "#FFFFFF"  # used for side panels/hover states
BORDER = "#E8E1DC"
CANVAS_SURROUND = "#EAE6E0"  # editor viewport backdrop the white page floats on

# Brand / accent -- Sage Green
ACCENT = "#8A9A76"
ACCENT_HOVER = "#748563"
ACCENT_PRESSED = "#5F7050"
ACCENT_LIGHT = "#E6EBDD"  # light tint for subtle selected/hover backgrounds

# Text
TEXT_PRIMARY = "#2B2320"
TEXT_SECONDARY = "#7A6F68"
TEXT_ON_ACCENT = "#FFFFFF"


def build_stylesheet() -> str:
    """App-wide QSS: white surfaces, neutral buttons by default, Burnt
    Orange/Rust for anything opted in via the `accent` dynamic property."""
    return f"""
    QWidget {{
        background-color: {BACKGROUND};
        color: {TEXT_PRIMARY};
    }}

    QPushButton {{
        background-color: {BACKGROUND};
        border: 1px solid {BORDER};
        border-radius: 6px;
        padding: 6px 14px;
    }}
    QPushButton:hover {{
        background-color: {SURFACE};
    }}
    QPushButton:pressed {{
        background-color: {BORDER};
    }}

    QPushButton[accent="true"] {{
        background-color: {ACCENT};
        border: 1px solid {ACCENT};
        color: {TEXT_ON_ACCENT};
        font-weight: 600;
    }}
    QPushButton[accent="true"]:hover {{
        background-color: {ACCENT_HOVER};
        border-color: {ACCENT_HOVER};
    }}
    QPushButton[accent="true"]:pressed {{
        background-color: {ACCENT_PRESSED};
        border-color: {ACCENT_PRESSED};
    }}

    QListWidget {{
        background-color: {BACKGROUND};
        border: 1px solid {BORDER};
        border-radius: 6px;
    }}
    QListWidget::item {{
        padding: 6px 4px;
    }}
    QListWidget::item:selected {{
        background-color: {ACCENT_LIGHT};
        color: {TEXT_PRIMARY};
    }}
    QListWidget::item:hover {{
        background-color: {SURFACE};
    }}

    QLineEdit, QSpinBox, QComboBox, QFontComboBox {{
        background-color: {BACKGROUND};
        border: 1px solid {BORDER};
        border-radius: 4px;
        padding: 4px 6px;
    }}

    QSlider::groove:horizontal {{
        height: 4px;
        background: {BORDER};
        border-radius: 2px;
    }}
    QSlider::sub-page:horizontal {{
        background: {ACCENT};
        border-radius: 2px;
    }}
    QSlider::add-page:horizontal {{
        background: {BORDER};
        border-radius: 2px;
    }}
    QSlider::handle:horizontal {{
        width: 14px;
        height: 14px;
        margin: -5px 0;
        background: {ACCENT};
        border: 2px solid {BACKGROUND};
        border-radius: 7px;
    }}
    QSlider::handle:horizontal:hover {{
        background: {ACCENT_HOVER};
    }}

    QCheckBox {{
        spacing: 8px;
    }}
    QCheckBox::indicator {{
        width: 15px;
        height: 15px;
        border: 1px solid {BORDER};
        border-radius: 4px;
        background: {BACKGROUND};
    }}
    QCheckBox::indicator:hover {{
        border-color: {ACCENT};
    }}
    QCheckBox::indicator:checked {{
        background: {ACCENT};
        border-color: {ACCENT};
    }}

    QMenu {{
        background-color: {BACKGROUND};
        border: 1px solid {BORDER};
        border-radius: 8px;
        padding: 4px;
    }}
    QMenu::item {{
        padding: 6px 24px 6px 12px;
        border-radius: 6px;
        color: {TEXT_PRIMARY};
    }}
    QMenu::item:selected {{
        background-color: {ACCENT_LIGHT};
    }}
    QMenu::separator {{
        height: 1px;
        background: {BORDER};
        margin: 4px 8px;
    }}

    QScrollBar:vertical {{
        background: transparent;
        width: 10px;
        margin: 0px;
    }}
    QScrollBar::handle:vertical {{
        background: {BORDER};
        border-radius: 4px;
        min-height: 24px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {TEXT_SECONDARY};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        background: transparent;
    }}
    """
