from src.features.editor.editor_view import CoreDesignApp


def main() -> None:
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    window = CoreDesignApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
