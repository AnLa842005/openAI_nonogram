"""PySide6 dialogs used by the application."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSlider,
    QSpinBox,
    QVBoxLayout,
)

from ..generator import MAX_SIZE, MIN_SIZE, GeneratedPuzzle, generate_random_puzzle


class RandomPuzzleDialog(QDialog):
    """Collect random generation parameters and return a GeneratedPuzzle."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Random Puzzle")
        self.setModal(True)
        self.setMinimumWidth(420)
        self.result: GeneratedPuzzle | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(14)
        title = QLabel("Create a Random Puzzle")
        title.setObjectName("sectionTitle")
        subtitle = QLabel(
            "Clues are generated from a source board, so the puzzle has at least one solution."
        )
        subtitle.setObjectName("muted")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        form = QFormLayout()
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(12)
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(("5 × 5", "10 × 10", "15 × 15", "Custom"))
        self.preset_combo.setCurrentText("10 × 10")
        self.preset_combo.currentTextChanged.connect(self._apply_preset)
        form.addRow("Quick size", self.preset_combo)

        size_row = QHBoxLayout()
        self.rows_spin = QSpinBox()
        self.rows_spin.setRange(MIN_SIZE, MAX_SIZE)
        self.rows_spin.setValue(10)
        self.rows_spin.setSuffix(" rows")
        self.cols_spin = QSpinBox()
        self.cols_spin.setRange(MIN_SIZE, MAX_SIZE)
        self.cols_spin.setValue(10)
        self.cols_spin.setSuffix(" columns")
        size_row.addWidget(self.rows_spin)
        size_row.addWidget(self.cols_spin)
        form.addRow("Dimensions", size_row)

        density_row = QHBoxLayout()
        self.density_slider = QSlider(Qt.Orientation.Horizontal)
        self.density_slider.setRange(0, 100)
        self.density_slider.setValue(50)
        self.density_label = QLabel("50%")
        self.density_label.setMinimumWidth(40)
        self.density_slider.valueChanged.connect(
            lambda value: self.density_label.setText(f"{value}%")
        )
        density_row.addWidget(self.density_slider, 1)
        density_row.addWidget(self.density_label)
        form.addRow("Expected density", density_row)

        self.seed_edit = QLineEdit()
        self.seed_edit.setPlaceholderText("Leave blank to generate a seed")
        form.addRow("Seed (optional)", self.seed_edit)
        layout.addLayout(form)

        note = QLabel(
            "Density is the probability of a filled cell, not difficulty. Uniqueness is not checked."
        )
        note.setObjectName("muted")
        note.setWordWrap(True)
        layout.addWidget(note)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Create Puzzle")
        buttons.button(QDialogButtonBox.StandardButton.Ok).setObjectName(
            "primaryButton"
        )
        buttons.accepted.connect(self._create)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _apply_preset(self, value: str) -> None:
        if value != "Custom":
            size = int(value.split()[0])
            self.rows_spin.setValue(size)
            self.cols_spin.setValue(size)

    def _create(self) -> None:
        try:
            seed_text = self.seed_edit.text().strip()
            self.result = generate_random_puzzle(
                rows=self.rows_spin.value(),
                cols=self.cols_spin.value(),
                density=self.density_slider.value() / 100.0,
                seed=int(seed_text) if seed_text else None,
            )
        except (TypeError, ValueError) as exc:
            QMessageBox.critical(self, "Invalid Parameters", str(exc))
            return
        self.accept()
