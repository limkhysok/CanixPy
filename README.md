# CanixPy

An open-source, lightweight alternative to Canvas built entirely in PyQt.

---

## 🎯 Purpose of the Project

The core purpose of building **CanixPy** is to provide an ultra-fast, offline-first graphic canvas and photo editor that completely bypasses the overhead of modern web-based design platforms. 

Instead of waiting for heavy browser engines to load, managing cloud accounts, or configuring complex backends, CanixPy allows users to simply launch `CanixPy.exe` and start editing immediately. It brings the speed and simplicity of traditional desktop utilities back to creative canvas tools.

### Key Pillars
* **Zero Overhead:** No backend, no server setups, and no web-browser bloat. Just pure, native desktop execution.
* **Instant Utility:** Double-click, drop an image or layout onto the canvas, edit quickly, and export. 
* **Extremely Low Resource Footprint:** Leverages C++ under the hood via Qt/PyQt to deliver smooth rendering and precise control while keeping RAM and CPU usage exceptionally low.

---

## 🚀 Running the App

Install dependencies, then launch from the project root:

```bash
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
rendering. [`src/main.py`](src/main.py) sets `QT_API=pyside6` before any Qt import to force
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
