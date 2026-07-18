from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QFontDatabase

FONTS_DIR = Path(__file__).resolve().parents[2] / "assets" / "fonts"


def load_app_fonts() -> list[str]:
    """Registers every .ttf under assets/fonts with Qt's font database.

    Must be called after a QApplication/QGuiApplication instance exists.
    Returns the family names Qt resolved them to (League Spartan's weight
    variants all share one family name; select a weight via QFont.setWeight).
    """
    families: list[str] = []
    if not FONTS_DIR.is_dir():
        return families

    for font_path in FONTS_DIR.glob("*.ttf"):
        font_id = QFontDatabase.addApplicationFont(str(font_path))
        if font_id == -1:
            continue
        for family in QFontDatabase.applicationFontFamilies(font_id):
            if family not in families:
                families.append(family)

    return families
