"""Main PySide6 window coordinating UI with framework-independent logic."""

from __future__ import annotations

import queue
import sys
import time
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QDialog,
    QDockWidget,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QStatusBar,
    QStyle,
    QTextEdit,
    QToolBar,
    QToolButton,
    QWidget,
)

from ..board_logic import PlaySession, PlayTool, check_board
from ..dfs_solver import DFSSolver
from ..heuristic_solver import HeuristicSolver
from ..models import (
    FinishReason,
    Puzzle,
    PuzzleValidationError,
    SearchAction,
    SearchStats,
    SearchStep,
    unknown_board,
)
from ..samples import CROSS_5X5
from ..solvers import SolverWorker, WorkerEvent, WorkerEventKind
from .board_widget import BoardWidget
from .control_panel import ControlPanel
from .dialogs import RandomPuzzleDialog
from .theme import apply_theme, standard_icon

EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "examples" / "puzzle-nonograms"


class MainWindow(QMainWindow):
    POLL_INTERVAL_MS = 25

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Nonograms Studio")
        self.resize(1180, 800)
        self.setMinimumSize(900, 650)

        self.puzzle = CROSS_5X5
        self.play_session = PlaySession(self.puzzle)
        self.visual_board = unknown_board(self.puzzle)
        self.mode = "Play"
        self.worker: SolverWorker | None = None
        self.retired_workers: list[SolverWorker] = []
        self.session_id = 0
        self.visual_state = "idle"
        self.seen_solution = False
        self.step_number = 0
        self.next_due = 0.0
        self.single_step_requested = False
        self.play_started_at: float | None = None
        self.play_elapsed = 0.0
        self.play_completed = False
        self.stroke_changed = False

        self._build_ui()
        self._connect_signals()
        self._update_puzzle_header()
        self._show_play_board()
        self._update_play_controls()
        self._update_visual_controls()
        QTimer.singleShot(0, self.board_widget.fit_to_view)

        self.timer = QTimer(self)
        self.timer.setInterval(self.POLL_INTERVAL_MS)
        self.timer.timeout.connect(self._tick)
        self.timer.start()

    def _build_ui(self) -> None:
        self.board_widget = BoardWidget()
        self.setCentralWidget(self.board_widget)

        self.toolbar = QToolBar("Main toolbar")
        self.toolbar.setMovable(False)
        self.toolbar.setFloatable(False)
        self.toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.toolbar)

        title = QLabel("Nonograms Studio")
        title.setStyleSheet(
            "font-size: 18px; font-weight: 700; color: #18232D; padding-right: 8px;"
        )
        self.toolbar.addWidget(title)
        self.toolbar.addSeparator()
        puzzle_box = QWidget()
        puzzle_layout = QHBoxLayout(puzzle_box)
        puzzle_layout.setContentsMargins(6, 0, 6, 0)
        puzzle_layout.setSpacing(8)
        self.puzzle_label = QLabel()
        self.puzzle_label.setStyleSheet("font-weight: 650;")
        self.puzzle_meta = QLabel()
        self.puzzle_meta.setObjectName("muted")
        puzzle_layout.addWidget(self.puzzle_label)
        puzzle_layout.addWidget(self.puzzle_meta)
        self.toolbar.addWidget(puzzle_box)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.toolbar.addWidget(spacer)

        self.new_action = QAction("New Puzzle", self)
        self.new_action.setToolTip("Create a random puzzle")
        self.new_action.triggered.connect(self._new_random_puzzle)
        new_button = QToolButton()
        new_button.setDefaultAction(self.new_action)
        new_button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        new_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        new_menu = QMenu(new_button)
        random_action = new_menu.addAction("Random Puzzle…")
        random_action.triggered.connect(self._new_random_puzzle)
        new_menu.addSeparator()
        sample_action = new_menu.addAction("Cross 5×5 sample")
        sample_action.triggered.connect(self._load_cross_sample)
        example_paths = sorted(
            EXAMPLES_DIR.glob("*.json"),
            key=lambda path: tuple(int(n) for n in path.stem.split("_")[0].split("x")),
        )
        if example_paths:
            examples_menu = new_menu.addMenu("Examples · puzzle-nonograms.com")
            for path in example_paths:
                label = path.stem.replace("_special_", " · Special ").replace("x", "×")
                action = examples_menu.addAction(label)
                action.triggered.connect(
                    lambda _checked=False, path=path: self._load_example(path)
                )
        new_button.setMenu(new_menu)
        self.toolbar.addWidget(new_button)

        self.open_action = QAction("Open", self)
        self.open_action.setToolTip("Open a puzzle from JSON")
        self.open_action.triggered.connect(self._open_json)
        self.toolbar.addAction(self.open_action)
        self.save_action = QAction("Save", self)
        self.save_action.setToolTip(
            "Export clues and metadata to JSON without the source solution"
        )
        self.save_action.triggered.connect(self._save_json)
        self.toolbar.addAction(self.save_action)

        self.panel = ControlPanel()
        panel_scroll = QScrollArea()
        panel_scroll.setWidgetResizable(True)
        panel_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        panel_scroll.setWidget(self.panel)
        self.control_dock = QDockWidget("Controls", self)
        self.control_dock.setObjectName("controlsDock")
        self.control_dock.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)
        self.control_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetClosable
            | QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        self.control_dock.setWidget(panel_scroll)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.control_dock)
        self.resizeDocks([self.control_dock], [292], Qt.Orientation.Horizontal)
        toggle_panel = self.control_dock.toggleViewAction()
        toggle_panel.setText("Controls")
        toggle_panel.setToolTip("Show or hide the control panel")
        self.toolbar.addAction(toggle_panel)

        status = QStatusBar()
        self.setStatusBar(status)
        self.status_message = QLabel("Ready to play.")
        self.status_message.setObjectName("muted")
        status.addWidget(self.status_message, 1)
        zoom_bar = QWidget()
        zoom_layout = QHBoxLayout(zoom_bar)
        zoom_layout.setContentsMargins(4, 0, 4, 0)
        zoom_layout.setSpacing(5)
        self.zoom_out_button = QToolButton()
        self.zoom_out_button.setText("−")
        self.zoom_out_button.setToolTip("Zoom out")
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(50, 200)
        self.zoom_slider.setValue(100)
        self.zoom_slider.setFixedWidth(115)
        self.zoom_slider.setToolTip(
            "Zoom the board; Ctrl + mouse wheel also changes zoom"
        )
        self.zoom_value = QLabel("100%")
        self.zoom_value.setMinimumWidth(42)
        self.zoom_in_button = QToolButton()
        self.zoom_in_button.setText("+")
        self.zoom_in_button.setToolTip("Zoom in")
        self.fit_button = QToolButton()
        self.fit_button.setText("Fit")
        self.fit_button.setToolTip("Fit the board to the viewport")
        for widget in (
            self.zoom_out_button,
            self.zoom_slider,
            self.zoom_value,
            self.zoom_in_button,
            self.fit_button,
        ):
            zoom_layout.addWidget(widget)
        status.addPermanentWidget(zoom_bar)

        self.panel.run_button.setIcon(
            standard_icon(self, QStyle.StandardPixmap.SP_MediaPlay)
        )
        self.panel.pause_button.setIcon(
            standard_icon(self, QStyle.StandardPixmap.SP_MediaPause)
        )
        self.panel.next_button.setIcon(
            standard_icon(self, QStyle.StandardPixmap.SP_MediaSkipForward)
        )
        self.panel.reset_button.setIcon(
            standard_icon(self, QStyle.StandardPixmap.SP_BrowserReload)
        )

        self.undo_shortcut = QShortcut(QKeySequence.StandardKey.Undo, self)
        self.undo_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.redo_shortcut = QShortcut(QKeySequence.StandardKey.Redo, self)
        self.redo_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)

    def _connect_signals(self) -> None:
        self.panel.mode_changed.connect(self._change_mode)
        self.board_widget.stroke_started.connect(self._start_play_stroke)
        self.board_widget.stroke_moved.connect(self._move_play_stroke)
        self.board_widget.stroke_ended.connect(self._end_play_stroke)
        self.panel.undo_button.clicked.connect(self._undo)
        self.panel.redo_button.clicked.connect(self._redo)
        self.panel.check_button.clicked.connect(self._check_play_board)
        self.panel.clear_button.clicked.connect(self._clear_play_board)
        self.panel.solver_combo.currentTextChanged.connect(self._solver_selected)
        self.panel.run_button.clicked.connect(self._run_visualizer)
        self.panel.pause_button.clicked.connect(self._pause_visualizer)
        self.panel.next_button.clicked.connect(self._next_visual_step)
        self.panel.reset_button.clicked.connect(self._reset_visualizer)
        self.zoom_slider.valueChanged.connect(
            lambda value: self.board_widget.set_zoom(value / 100.0)
        )
        self.zoom_out_button.clicked.connect(
            lambda: self.zoom_slider.setValue(self.zoom_slider.value() - 10)
        )
        self.zoom_in_button.clicked.connect(
            lambda: self.zoom_slider.setValue(self.zoom_slider.value() + 10)
        )
        self.fit_button.clicked.connect(self.board_widget.fit_to_view)
        self.board_widget.zoom_changed.connect(self._sync_zoom)
        self.undo_shortcut.activated.connect(self._shortcut_undo)
        self.redo_shortcut.activated.connect(self._shortcut_redo)

    def _update_puzzle_header(self) -> None:
        self.puzzle_label.setText(
            f"{self.puzzle.name}  ·  {self.puzzle.height} × {self.puzzle.width}"
        )
        details = []
        seed = self.puzzle.metadata.get("seed")
        density = self.puzzle.metadata.get("expected_density")
        if seed is not None:
            details.append(f"seed {seed}")
        if isinstance(density, (int, float)):
            details.append(f"density {float(density):.0%}")
        self.puzzle_meta.setText(" · ".join(details))

    def _new_random_puzzle(self) -> None:
        dialog = RandomPuzzleDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted or dialog.result is None:
            return
        if not self._confirm_replace_puzzle():
            return
        generated = dialog.result
        self._replace_puzzle(generated.puzzle)
        self._set_play_message(
            f"Generated a puzzle with seed {generated.seed}. It has at least one solution; uniqueness was not checked."
        )

    def _load_cross_sample(self) -> None:
        if self._confirm_replace_puzzle():
            self._replace_puzzle(CROSS_5X5)

    def _load_example(self, path: Path) -> None:
        self._load_puzzle_file(str(path))

    def _open_json(self) -> None:
        path, _selected = QFileDialog.getOpenFileName(
            self,
            "Open Nonograms Puzzle",
            str(EXAMPLES_DIR) if EXAMPLES_DIR.is_dir() else "",
            "JSON files (*.json);;All files (*)",
        )
        if path:
            self._load_puzzle_file(path)

    def _load_puzzle_file(self, path: str) -> None:
        try:
            puzzle = Puzzle.from_json_file(path)
        except PuzzleValidationError as exc:
            QMessageBox.critical(self, "Invalid Input", str(exc))
            return
        if self._confirm_replace_puzzle():
            self._replace_puzzle(puzzle)

    def _save_json(self) -> None:
        safe_name = "".join(
            char if char.isalnum() or char in "-_" else "_" for char in self.puzzle.name
        )
        path, _selected = QFileDialog.getSaveFileName(
            self,
            "Save Nonograms Puzzle",
            f"{safe_name}.json",
            "JSON files (*.json)",
        )
        if not path:
            return
        if not path.lower().endswith(".json"):
            path += ".json"
        try:
            self.puzzle.to_json_file(path)
        except PuzzleValidationError as exc:
            QMessageBox.critical(self, "Could Not Save File", str(exc))
            return
        QMessageBox.information(
            self,
            "Puzzle Saved",
            f"Clues were saved to:\n{path}\n\nThe file does not contain the source solution.",
        )

    def _confirm_replace_puzzle(self) -> bool:
        if not self.play_session.has_progress:
            return True
        answer = QMessageBox.question(
            self,
            "Replace Puzzle?",
            "Play progress, the timer, and Undo/Redo history will be cleared. Continue?",
        )
        return answer == QMessageBox.StandardButton.Yes

    def _replace_puzzle(self, puzzle: Puzzle) -> None:
        self._cancel_visual_session(increment=True)
        self._pause_play_timer()
        self.puzzle = puzzle
        self.play_session = PlaySession(puzzle)
        self.visual_board = unknown_board(puzzle)
        self.play_elapsed = 0.0
        self.play_started_at = None
        self.play_completed = False
        self.panel.time_metric.value_label.setText("00:00")
        self._set_play_status("Ready", "neutral")
        self._set_play_message("The new puzzle is ready. Check uses clues only.")
        self._reset_visual_values(
            "The new puzzle is loaded; the visualizer starts from UNKNOWN."
        )
        self._update_puzzle_header()
        if self.mode == "Play":
            self._show_play_board()
        else:
            self._show_visual_board()
        self._update_play_controls()
        self._update_visual_controls()
        QTimer.singleShot(0, self.board_widget.fit_to_view)
        if not self._visual_solver_available():
            self._solver_selected(self.panel.solver_combo.currentText())

    def _change_mode(self, target: str) -> None:
        if target == self.mode:
            return
        if self.mode == "Visualize":
            was_active = self.visual_state in {"running", "paused"}
            self._cancel_visual_session(increment=True)
            self.visual_state = "idle"
            if was_active:
                self._set_visual_status("Cancelled", "warning")
                self._set_visual_message(
                    "The visualization session was cancelled when switching to Play."
                )
        else:
            self._pause_play_timer()
        self.mode = target
        self.panel.set_mode(target)
        if target == "Play":
            self.board_widget.set_editable(True)
            self._resume_play_timer()
            self._show_play_board()
            self.status_message.setText(self.panel.play_message.text())
        else:
            self.board_widget.set_editable(False)
            self._reset_visualizer(show_message=False)
            self._set_visual_message(
                "The visualizer starts from UNKNOWN and ignores cells entered in Play mode."
            )
            self._show_visual_board()
            if not self._visual_solver_available():
                self._solver_selected(self.panel.solver_combo.currentText())
        self._update_play_controls()
        self._update_visual_controls()

    def _show_play_board(
        self, rows: tuple[int, ...] = (), cols: tuple[int, ...] = ()
    ) -> None:
        self.board_widget.set_editable(True)
        self.board_widget.set_model(
            self.puzzle,
            self.play_session.board,
            mismatched_rows=rows,
            mismatched_cols=cols,
        )

    def _show_visual_board(self, step: SearchStep | None = None) -> None:
        self.board_widget.set_editable(False)
        self.board_widget.set_model(
            self.puzzle, self.visual_board, focus=step.focus if step else None
        )

    def _start_play_stroke(self, row: int, col: int, button: int) -> None:
        if self.mode != "Play":
            return
        self.stroke_changed = self.play_session.begin_stroke(
            row, col, button, PlayTool.FILL
        )
        if self.stroke_changed:
            self._after_play_edit(live=True)

    def _move_play_stroke(self, row: int, col: int) -> None:
        if self.mode == "Play" and self.play_session.paint_cell(row, col):
            self.stroke_changed = True
            self._after_play_edit(live=True)

    def _end_play_stroke(self) -> None:
        if self.mode != "Play":
            return
        changed = self.play_session.end_stroke()
        if changed or self.stroke_changed:
            self._after_play_edit(live=False)
        self.stroke_changed = False

    def _after_play_edit(self, live: bool) -> None:
        if self.play_started_at is None:
            self.play_started_at = time.monotonic()
        self.play_completed = False
        self._set_play_status("Playing", "active")
        self._set_play_message(
            "Updating the board…" if live else "The action was added to history."
        )
        self._show_play_board()
        self._update_play_controls()

    def _undo(self) -> None:
        if self.mode == "Play" and self.play_session.undo():
            self.play_completed = False
            self._set_play_status("Playing", "active")
            self._set_play_message("Undid the last action.")
            self._show_play_board()
            self._update_play_controls()

    def _redo(self) -> None:
        if self.mode == "Play" and self.play_session.redo():
            self.play_completed = False
            self._set_play_status("Playing", "active")
            self._set_play_message("Redid the last undone action.")
            self._show_play_board()
            self._update_play_controls()

    def _shortcut_undo(self) -> None:
        if self.mode == "Play" and not self._focus_is_text_input():
            self._undo()

    def _shortcut_redo(self) -> None:
        if self.mode == "Play" and not self._focus_is_text_input():
            self._redo()

    @staticmethod
    def _focus_is_text_input() -> bool:
        widget = QApplication.focusWidget()
        return isinstance(widget, (QLineEdit, QTextEdit, QAbstractSpinBox, QComboBox))

    def _check_play_board(self) -> None:
        result = check_board(self.puzzle, self.play_session.board)
        if result.solved:
            self.play_completed = True
            self._pause_play_timer()
            self._set_play_status("Completed", "success")
            self._set_play_message("Completed: the board satisfies every clue.")
            self._show_play_board()
        else:
            self._set_play_status("Not complete", "warning")
            self._set_play_message(
                "Not complete, or one or more rows or columns do not match."
            )
            self._show_play_board(result.mismatched_rows, result.mismatched_cols)

    def _clear_play_board(self) -> None:
        if not self.play_session.has_progress:
            return
        answer = QMessageBox.question(
            self,
            "Clear Board?",
            "Clear all play progress, the timer, and Undo/Redo history?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.play_session = PlaySession(self.puzzle)
        self.play_elapsed = 0.0
        self.play_started_at = None
        self.play_completed = False
        self.panel.time_metric.value_label.setText("00:00")
        self._set_play_status("Ready", "neutral")
        self._set_play_message("The board was cleared.")
        self._show_play_board()
        self._update_play_controls()

    def _pause_play_timer(self) -> None:
        if self.play_started_at is not None:
            self.play_elapsed += time.monotonic() - self.play_started_at
            self.play_started_at = None

    def _resume_play_timer(self) -> None:
        if (
            self.play_session.has_progress
            and not self.play_completed
            and self.play_started_at is None
        ):
            self.play_started_at = time.monotonic()

    def _update_play_controls(self) -> None:
        active = self.mode == "Play"
        self.panel.undo_button.setEnabled(active and self.play_session.can_undo)
        self.panel.redo_button.setEnabled(active and self.play_session.can_redo)
        self.panel.clear_button.setEnabled(active and self.play_session.has_progress)
        self.panel.check_button.setEnabled(active)
        count = self.play_session.marked_count
        total = self.puzzle.height * self.puzzle.width
        self.panel.marked_metric.value_label.setText(f"{count} / {total}")

    def _solver_selected(self, selected: str) -> None:
        if self.visual_state == "idle":
            self._set_visual_status("Ready", "neutral")
            if selected == ControlPanel.SOLVER_DFS:
                self._set_visual_message(
                    "DFS is ready to search from a fresh UNKNOWN board."
                )
            else:
                self._set_visual_message(
                    "The heuristic solver is ready to propagate from a fresh UNKNOWN board."
                )
        self._update_visual_controls()

    def _visual_solver_available(self) -> bool:
        selected = self.panel.solver_combo.currentText()
        return selected in (ControlPanel.SOLVER_DFS, ControlPanel.SOLVER_HEURISTIC)

    def _run_visualizer(self) -> None:
        if self.mode != "Visualize" or not self._visual_solver_available():
            return
        if self.visual_state == "paused" and self.worker is not None:
            self.visual_state = "running"
            self._set_visual_status("Running", "active")
            self._set_visual_message("Resuming solver event playback.")
            self.next_due = time.monotonic()
            self._update_visual_controls()
            return
        self._cancel_visual_session(increment=True)
        selected = self.panel.solver_combo.currentText()
        if selected == ControlPanel.SOLVER_DFS:
            solver = DFSSolver()
        else:
            solver = HeuristicSolver()
        self.worker = SolverWorker(solver, self.puzzle, self.session_id)
        self.visual_board = unknown_board(self.puzzle)
        self.step_number = 0
        self.seen_solution = False
        self.visual_state = "running"
        self.single_step_requested = False
        self.panel.step_value.setText("0")
        self.panel.action_value.setText("—")
        self._show_stats(SearchStats())
        self._set_visual_status("Running", "active")
        self._set_visual_message(f"Waiting for the first event from {solver.name}…")
        self._show_visual_board()
        self.next_due = time.monotonic()
        self.worker.start()
        self._update_visual_controls()

    def _pause_visualizer(self) -> None:
        if self.visual_state == "running":
            self.visual_state = "paused"
            self._set_visual_status("Paused", "warning")
            self._set_visual_message(
                "Animation is paused; the worker is waiting on the bounded queue."
            )
            self._update_visual_controls()

    def _next_visual_step(self) -> None:
        if self.visual_state == "paused":
            self.single_step_requested = True
            self._consume_one_event()

    def _reset_visualizer(
        self, _checked: bool = False, show_message: bool = True
    ) -> None:
        self._cancel_visual_session(increment=True)
        self.visual_board = unknown_board(self.puzzle)
        message = (
            "The previous session was cancelled and reset. The visualizer is ready from an UNKNOWN board."
            if show_message
            else "The visualizer is ready from an UNKNOWN board."
        )
        self._reset_visual_values(message)
        if self.mode == "Visualize":
            self._show_visual_board()
        self._update_visual_controls()

    def _reset_visual_values(self, message: str) -> None:
        self.visual_state = "idle"
        self.single_step_requested = False
        self.seen_solution = False
        self.step_number = 0
        self.panel.step_value.setText("0")
        self.panel.action_value.setText("—")
        self._set_visual_status("Ready", "neutral")
        self._set_visual_message(message)
        self._show_stats(SearchStats())

    def _cancel_visual_session(self, increment: bool) -> None:
        if self.worker is not None:
            self.worker.cancel()
            self.retired_workers.append(self.worker)
        self.worker = None
        if increment:
            self.session_id += 1

    def _update_visual_controls(self) -> None:
        active = self.mode == "Visualize"
        available = active and self._visual_solver_available()
        self.panel.run_button.setText(
            "Resume" if self.visual_state == "paused" else "Run"
        )
        self.panel.run_button.setEnabled(available and self.visual_state != "running")
        self.panel.pause_button.setEnabled(active and self.visual_state == "running")
        self.panel.next_button.setEnabled(active and self.visual_state == "paused")
        self.panel.reset_button.setEnabled(
            active
            and (
                self.visual_state != "idle"
                or self.visual_board != unknown_board(self.puzzle)
            )
        )
        self.panel.solver_combo.setEnabled(
            not (active and self.visual_state in {"running", "paused"})
        )

    def _tick(self) -> None:
        if self.play_started_at is not None:
            self._update_elapsed_display()
        if self.visual_state == "running" and time.monotonic() >= self.next_due:
            if self._consume_one_event():
                self.next_due = (
                    time.monotonic() + self.panel.speed_slider.value() / 1000.0
                )
        elif self.visual_state == "paused" and self.single_step_requested:
            self._consume_one_event()
        self.retired_workers = [
            worker for worker in self.retired_workers if worker.is_alive
        ]

    def _update_elapsed_display(self) -> None:
        total = self.play_elapsed
        if self.play_started_at is not None:
            total += time.monotonic() - self.play_started_at
        seconds = int(total)
        self.panel.time_metric.value_label.setText(
            f"{seconds // 60:02d}:{seconds % 60:02d}"
        )

    def _consume_one_event(self) -> bool:
        worker = self.worker
        if worker is None:
            self.single_step_requested = False
            return False
        try:
            event = worker.events.get_nowait()
        except queue.Empty:
            return False
        if event.session_id != self.session_id:
            return False
        self._handle_worker_event(event)
        if event.kind is WorkerEventKind.STEP:
            self.single_step_requested = False
        return True

    def _handle_worker_event(self, event: WorkerEvent) -> None:
        if event.kind is WorkerEventKind.ERROR:
            self.visual_state = "finished"
            self._set_visual_status("Error", "error")
            self._set_visual_message(f"Solver error: {event.error}")
            self._update_visual_controls()
            return
        if event.kind is WorkerEventKind.ENDED:
            if self.visual_state not in {"finished", "idle"}:
                self.visual_state = "finished"
                self._set_visual_status("Error", "error")
                self._set_visual_message(
                    "The solver ended without emitting a FINISH event."
                )
                self._update_visual_controls()
            return
        if event.step is not None:
            self._apply_visual_step(event.step)

    def _apply_visual_step(self, step: SearchStep) -> None:
        self.step_number += 1
        self.visual_board = step.board
        self.panel.step_value.setText(str(self.step_number))
        self.panel.action_value.setText(step.action.value)
        self._set_visual_message(step.message or "—")
        self._show_stats(step.stats)
        if self.mode == "Visualize":
            self._show_visual_board(step)
        if step.action is SearchAction.SOLUTION:
            self.seen_solution = True
            self._set_visual_status("Solved", "success")
        elif step.action is SearchAction.FINISH:
            self.visual_state = "finished"
            if step.finish_reason is FinishReason.CANCELLED:
                self._set_visual_status("Cancelled", "warning")
            elif step.finish_reason is FinishReason.NO_SOLUTION:
                self._set_visual_status("No solution", "warning")
            elif step.finish_reason is FinishReason.LIMIT_REACHED:
                self._set_visual_status("Limit reached", "warning")
            elif step.finish_reason is FinishReason.ERROR:
                self._set_visual_status("Error", "error")
            elif self.seen_solution:
                self._set_visual_status("Solved", "success")
            else:
                self._set_visual_status("Error", "error")
                self._set_visual_message(
                    "FINISH reported completion without a preceding SOLUTION event."
                )
        elif self.visual_state == "running":
            self._set_visual_status("Running", "active")
        else:
            self._set_visual_status("Paused", "warning")
        self._update_visual_controls()

    def _set_play_status(self, text: str, kind: str) -> None:
        ControlPanel.set_status(self.panel.play_status, text, kind)

    def _set_visual_status(self, text: str, kind: str) -> None:
        ControlPanel.set_status(self.panel.visual_status, text, kind)

    def _set_play_message(self, text: str) -> None:
        self.panel.play_message.setText(text)
        if self.mode == "Play":
            self.status_message.setText(text)

    def _set_visual_message(self, text: str) -> None:
        self.panel.visual_message.setText(text)
        if self.mode == "Visualize":
            self.status_message.setText(text)

    def _show_stats(self, stats: SearchStats) -> None:
        for key, label in self.panel.stats_labels.items():
            value = getattr(stats, key)
            if value is None:
                label.setText("—")
            elif key == "solver_time_ms":
                label.setText(f"{value:.3f}")
            else:
                label.setText(f"{value:,}")

    def _sync_zoom(self, zoom: float) -> None:
        value = round(zoom * 100)
        self.zoom_slider.blockSignals(True)
        self.zoom_slider.setValue(value)
        self.zoom_slider.blockSignals(False)
        self.zoom_value.setText(f"{value}%")

    def closeEvent(self, event: QCloseEvent) -> None:
        self.timer.stop()
        self._cancel_visual_session(increment=True)
        deadline = time.monotonic() + 1.0
        for worker in self.retired_workers:
            remaining = max(0.0, deadline - time.monotonic())
            worker.wait(remaining)
        event.accept()


def main() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Nonograms Studio")
    apply_theme(app)
    window = MainWindow()
    window.show()
    raise_code = app.exec()
    if raise_code:
        raise SystemExit(raise_code)
