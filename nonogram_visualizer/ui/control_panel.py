"""Compact scrollable Play/Visualize controls for the main window."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QStackedWidget,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


class CollapsibleSection(QWidget):
    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.toggle = QToolButton()
        self.toggle.setText(title)
        self.toggle.setCheckable(True)
        self.toggle.setChecked(True)
        self.toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toggle.setArrowType(Qt.ArrowType.DownArrow)
        self.toggle.clicked.connect(self._toggle)
        layout.addWidget(self.toggle)
        self.content = QFrame()
        self.content.setObjectName("card")
        layout.addWidget(self.content)

    def _toggle(self, checked: bool) -> None:
        self.content.setVisible(checked)
        self.toggle.setArrowType(
            Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow
        )


class MetricCard(QFrame):
    def __init__(self, title: str, value: str = "—") -> None:
        super().__init__()
        self.setObjectName("metricCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(9, 6, 9, 6)
        layout.setSpacing(2)
        label = QLabel(title)
        label.setObjectName("muted")
        self.value_label = QLabel(value)
        self.value_label.setObjectName("metricValue")
        layout.addWidget(label)
        layout.addWidget(self.value_label)


class ControlPanel(QWidget):
    mode_changed = Signal(str)

    SOLVER_DFS = "DFS"
    SOLVER_HEURISTIC = "Heuristic (MRV + propagation)"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("controlPanel")
        self.setMinimumWidth(270)
        self.setMaximumWidth(320)
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 12)
        root.setSpacing(10)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(6)
        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        self.play_mode_button = self._mode_button("Play", True)
        self.visual_mode_button = self._mode_button("Visualize", False)
        self.mode_group.addButton(self.play_mode_button)
        self.mode_group.addButton(self.visual_mode_button)
        mode_row.addWidget(self.play_mode_button)
        mode_row.addWidget(self.visual_mode_button)
        root.addLayout(mode_row)

        self.stack = QStackedWidget()
        self.play_page = self._build_play_page()
        self.visual_page = self._build_visual_page()
        self.stack.addWidget(self.play_page)
        self.stack.addWidget(self.visual_page)
        root.addWidget(self.stack)
        root.addStretch(1)

    def _mode_button(self, text: str, checked: bool) -> QToolButton:
        button = QToolButton()
        button.setObjectName("modeButton")
        button.setText(text)
        button.setCheckable(True)
        button.setChecked(checked)
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        button.clicked.connect(
            lambda _checked, value=text: self.set_mode(value, emit_signal=True)
        )
        return button

    def set_mode(self, mode: str, emit_signal: bool = False) -> None:
        play = mode == "Play"
        self.play_mode_button.setChecked(play)
        self.visual_mode_button.setChecked(not play)
        self.stack.setCurrentIndex(0 if play else 1)
        if emit_signal:
            self.mode_changed.emit(mode)

    def _build_play_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        actions = self._card("Actions")
        history = QHBoxLayout()
        self.undo_button = QPushButton("Undo")
        self.undo_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowBack)
        )
        self.undo_button.setToolTip("Undo the last action (Ctrl+Z)")
        self.redo_button = QPushButton("Redo")
        self.redo_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowForward)
        )
        self.redo_button.setToolTip("Redo the last undone action (Ctrl+Y)")
        history.addWidget(self.undo_button)
        history.addWidget(self.redo_button)
        actions.layout().addLayout(history)
        self.check_button = QPushButton("Check")
        self.check_button.setObjectName("primaryButton")
        self.check_button.setToolTip("Check the current board against the clues")
        actions.layout().addWidget(self.check_button)
        self.clear_button = QPushButton("Clear Board")
        self.clear_button.setObjectName("secondaryDanger")
        self.clear_button.setToolTip(
            "Clear the board, timer, and history after confirmation"
        )
        actions.layout().addWidget(self.clear_button)
        layout.addWidget(actions)

        progress = self._card("Progress")
        self.play_status = self._status_label("Ready", "neutral")
        progress.layout().addWidget(
            self.play_status, alignment=Qt.AlignmentFlag.AlignLeft
        )
        metric_row = QHBoxLayout()
        self.time_metric = MetricCard("Time", "00:00")
        self.marked_metric = MetricCard("Marked", "0 / 0")
        metric_row.addWidget(self.time_metric)
        metric_row.addWidget(self.marked_metric)
        progress.layout().addLayout(metric_row)
        self.play_message = QLabel("Left-click to fill; right-click to mark X.")
        self.play_message.setWordWrap(True)
        self.play_message.setObjectName("muted")
        progress.layout().addWidget(self.play_message)
        layout.addWidget(progress)
        layout.addStretch(1)
        return page

    def _build_visual_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        solver_card = self._card("Solver")
        self.solver_combo = QComboBox()
        self.solver_combo.addItems((self.SOLVER_DFS, self.SOLVER_HEURISTIC))
        self.solver_combo.setToolTip(
            "DFS assigns rows top to bottom; Heuristic propagates line "
            "constraints and guesses cells in MRV order"
        )
        solver_card.layout().addWidget(self.solver_combo)
        note = QLabel(
            "The visualizer starts from UNKNOWN; continuing from the Play board is not supported."
        )
        note.setObjectName("muted")
        note.setWordWrap(True)
        solver_card.layout().addWidget(note)
        layout.addWidget(solver_card)

        animation = self._card("Animation")
        run_row = QHBoxLayout()
        self.run_button = QPushButton("Run")
        self.run_button.setObjectName("primaryButton")
        self.pause_button = QPushButton("Pause")
        run_row.addWidget(self.run_button, 2)
        run_row.addWidget(self.pause_button, 1)
        animation.layout().addLayout(run_row)
        step_row = QHBoxLayout()
        self.next_button = QPushButton("Next Step")
        self.reset_button = QPushButton("Reset")
        step_row.addWidget(self.next_button)
        step_row.addWidget(self.reset_button)
        animation.layout().addLayout(step_row)
        speed_row = QHBoxLayout()
        speed_row.addWidget(QLabel("Speed"))
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(80, 1400)
        self.speed_slider.setValue(650)
        self.speed_slider.setInvertedAppearance(True)
        self.speed_slider.setToolTip("Drag right for faster animation")
        speed_row.addWidget(self.speed_slider, 1)
        animation.layout().addLayout(speed_row)
        layout.addWidget(animation)

        event_card = self._card("Current Event")
        self.visual_status = self._status_label("Ready", "neutral")
        event_card.layout().addWidget(
            self.visual_status, alignment=Qt.AlignmentFlag.AlignLeft
        )
        event_grid = QGridLayout()
        event_grid.addWidget(QLabel("Step"), 0, 0)
        self.step_value = QLabel("0")
        self.step_value.setObjectName("metricValue")
        event_grid.addWidget(
            self.step_value, 0, 1, alignment=Qt.AlignmentFlag.AlignRight
        )
        event_grid.addWidget(QLabel("Action"), 1, 0)
        self.action_value = QLabel("—")
        self.action_value.setObjectName("metricValue")
        event_grid.addWidget(
            self.action_value, 1, 1, alignment=Qt.AlignmentFlag.AlignRight
        )
        event_card.layout().addLayout(event_grid)
        self.visual_message = QLabel("DFS is ready to search from a fresh UNKNOWN board.")
        self.visual_message.setWordWrap(True)
        self.visual_message.setObjectName("muted")
        event_card.layout().addWidget(self.visual_message)
        layout.addWidget(event_card)

        self.stats_section = CollapsibleSection("Solver Statistics")
        stats = QGridLayout(self.stats_section.content)
        stats.setContentsMargins(10, 8, 10, 8)
        self.stats_labels: dict[str, QLabel] = {}
        for row, (key, text) in enumerate(
            (
                ("nodes_expanded", "Nodes expanded"),
                ("nodes_generated", "Nodes generated"),
                ("backtracks", "Backtracks"),
                ("max_depth", "Maximum depth"),
                ("solver_time_ms", "Solver time (ms)"),
                ("peak_memory_bytes", "Peak memory (bytes)"),
            )
        ):
            stats.addWidget(QLabel(text), row, 0)
            value = QLabel("—")
            value.setAlignment(Qt.AlignmentFlag.AlignRight)
            self.stats_labels[key] = value
            stats.addWidget(value, row, 1)
        layout.addWidget(self.stats_section)
        layout.addStretch(1)
        return page

    @staticmethod
    def _card(title: str) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 9, 10, 10)
        layout.setSpacing(7)
        label = QLabel(title)
        label.setObjectName("sectionTitle")
        layout.addWidget(label)
        return card

    @staticmethod
    def _status_label(text: str, kind: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("statusBadge")
        label.setProperty("statusKind", kind)
        return label

    @staticmethod
    def set_status(label: QLabel, text: str, kind: str) -> None:
        label.setText(text)
        label.setProperty("statusKind", kind)
        label.style().unpolish(label)
        label.style().polish(label)
