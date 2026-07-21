# CanixPy

An open-source, lightweight alternative to Canvas, built around a native desktop editor with an optional web/backend layer.

---

## 🎯 Purpose of the Project

The core of **CanixPy** is `desktop_app/`: an ultra-fast, offline-first graphic canvas and photo editor that bypasses the overhead of browser-based design platforms. Double-click, drop an image or layout onto the canvas, edit quickly, and export — no account, no server required to use it.

`backend/` (FastAPI) and `frontend/` (Next.js) are an in-progress, optional web layer for things the desktop app alone can't do (e.g. sync/sharing) — the desktop app does not depend on them.

### Key Pillars (desktop_app)
* **Zero Overhead:** No backend or web-browser bloat required for local editing. Just pure, native desktop execution.
* **Instant Utility:** Double-click, drop an image or layout onto the canvas, edit quickly, and export.
* **Extremely Low Resource Footprint:** Leverages C++ under the hood via Qt/PyQt to deliver smooth rendering and precise control while keeping RAM and CPU usage exceptionally low.

---

## 📁 Project Layout

```
CanixPy/
├── desktop_app/   # PySide6 desktop editor (the core product)
├── backend/       # FastAPI web API — data models in place, routes not yet implemented
└── frontend/      # Next.js web frontend (placeholder, not yet implemented)
```

---

## 🚀 Running the App

Install dependencies, then launch from `desktop_app/`:

```bash
cd desktop_app
pip install -r requirements.txt
python -m src.main
```

---

## 🎨 Icons

Icons are provided by [`qtawesome`](https://github.com/spyder-ide/qtawesome), which bundles
FontAwesome, Material Design Icons, and a few other icon fonts as native `QIcon`/`QPixmap`
objects — no image assets to manage.

**Important:** `qtawesome` resolves its Qt binding through `qtpy`. If both PySide6 and PyQt
are installed in the same environment, `qtpy` may auto-detect the wrong one and break icon
rendering. [`desktop_app/src/main.py`](desktop_app/src/main.py) sets `QT_API=pyside6` before any Qt import to force
the correct binding — keep that line if you touch the entrypoint, and don't import
`qtawesome` anywhere that could run before it (e.g. module-level in a file imported by
`main.py` above that line).

Usage:

```python
import qtawesome as qta
from PySide6.QtWidgets import QPushButton

btn = QPushButton("Home")
btn.setIcon(qta.icon("fa5s.home", color="#333333"))
```

Browse available icon names with the bundled icon browser:

```bash
qta-browser
```

---

## ⚖️ License

This project is licensed under the **GNU General Public License v3.0** (GPL-3.0) to align with the open-source PyQt ecosystem while keeping this tool free and accessible for everyone.
