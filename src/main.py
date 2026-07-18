import os

# Must be set before any Qt-related import (including qtawesome, which relies on
# qtpy to pick a binding). Without this, qtpy may auto-detect PyQt6 instead of
# PySide6 if both are installed, which breaks icon rendering.
os.environ.setdefault("QT_API", "pyside6")

import sys
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication
from src.core.fonts import load_app_fonts
from src.core.theme import build_stylesheet
from src.features.app import App

def main() -> None:
    app = QApplication(sys.argv)
    app.setStyleSheet(build_stylesheet())

    families = load_app_fonts()
    if "League Spartan" in families:
        app.setFont(QFont("League Spartan"))

    window = App()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
