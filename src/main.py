import os
import sys

# Must be set before any Qt-related import (including qtawesome, which relies on
# qtpy to pick a binding). Without this, qtpy may auto-detect PyQt6 instead of
# PySide6 if both are installed, which breaks icon rendering.
os.environ.setdefault("QT_API", "pyside6")
# Use FreeType instead of DirectWrite for font rendering on Windows. DirectWrite
# fails to build font faces for legacy bitmap-only fonts (e.g. "Fixedsys") that
# are still registered on the system, logging spurious errors during Qt's font
# enumeration at startup.
if sys.platform == "win32":
    os.environ.setdefault("QT_QPA_PLATFORM", "windows:fontengine=freetype")
# Silences harmless "QWindowsWindow::setGeometry: Unable to set geometry"
# spam -- Windows clamps the window to the screen's usable area whenever the
# editor's minimum layout size is a touch taller than it (e.g. during an
# item/page drag, which repeatedly re-triggers the layout's size negotiation),
# which is expected and not something the app can/should avoid.
os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.window=false")

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from src.core.fonts import BUNDLED_FONT_FAMILY, load_app_fonts
from src.core.theme import build_stylesheet
from src.features.app import App


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyleSheet(build_stylesheet())

    families = load_app_fonts()
    if BUNDLED_FONT_FAMILY in families:
        app.setFont(QFont(BUNDLED_FONT_FAMILY))

    window = App()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
