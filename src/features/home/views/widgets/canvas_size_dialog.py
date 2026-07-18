from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.features.home.home_viewmodel import CanvasPreset, HomeViewModel


class CanvasSizeDialog(QDialog):
    """Lets the user pick a preset canvas size or enter a custom one before opening the editor."""

    def __init__(self, viewmodel: HomeViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Design")
        self.setMinimumWidth(320)

        self.viewmodel = viewmodel
        self._selected_size = (800, 600)

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("<b>Choose a size</b>"))

        self.preset_list = QListWidget()
        for preset in self.viewmodel.list_presets():
            item = QListWidgetItem(f"{preset.name}  ({preset.width} x {preset.height})")
            item.setData(Qt.ItemDataRole.UserRole, preset)
            self.preset_list.addItem(item)
        self.preset_list.currentItemChanged.connect(self._on_preset_selected)
        layout.addWidget(self.preset_list)

        layout.addWidget(QLabel("Custom size (px):"))
        custom_layout = QHBoxLayout()
        self.width_box = QSpinBox()
        self.width_box.setRange(1, 10000)
        self.width_box.valueChanged.connect(self._on_custom_changed)

        self.height_box = QSpinBox()
        self.height_box.setRange(1, 10000)
        self.height_box.valueChanged.connect(self._on_custom_changed)

        custom_layout.addWidget(QLabel("W"))
        custom_layout.addWidget(self.width_box)
        custom_layout.addWidget(QLabel("H"))
        custom_layout.addWidget(self.height_box)
        layout.addLayout(custom_layout)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.preset_list.setCurrentRow(0)

    def _on_preset_selected(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        if current is None:
            return
        preset: CanvasPreset = current.data(Qt.ItemDataRole.UserRole)
        self.width_box.blockSignals(True)
        self.height_box.blockSignals(True)
        self.width_box.setValue(preset.width)
        self.height_box.setValue(preset.height)
        self.width_box.blockSignals(False)
        self.height_box.blockSignals(False)
        self._selected_size = (preset.width, preset.height)

    def _on_custom_changed(self, _value: int) -> None:
        self.preset_list.setCurrentRow(-1)
        self._selected_size = (self.width_box.value(), self.height_box.value())

    def selected_size(self) -> tuple[int, int]:
        return self._selected_size
