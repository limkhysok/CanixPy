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
    """
