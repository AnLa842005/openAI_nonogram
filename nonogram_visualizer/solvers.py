"""Solver contract, mock data, and a bounded worker-thread adapter."""

from __future__ import annotations

import queue
import threading
from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from .models import (
    CellState,
    FinishReason,
    Puzzle,
    SearchAction,
    SearchFocus,
    SearchStats,
    SearchStep,
    unknown_board,
)


class Solver(Protocol):
    """Common interface implemented by visualized search solvers."""

    name: str

    def steps(
        self, puzzle: Puzzle, cancel_event: threading.Event
    ) -> Iterator[SearchStep]:
        """Yield immutable search snapshots in chronological order."""
        ...


def _board(*rows: str) -> tuple[tuple[CellState, ...], ...]:
    legend = {
        "?": CellState.UNKNOWN,
        ".": CellState.EMPTY,
        "#": CellState.FILLED,
    }
    return tuple(tuple(legend[cell] for cell in row) for row in rows)


@dataclass(slots=True)
class MockSolver:
    """Scripted UI demo. This is deliberately not a search algorithm."""

    name: str = "Demo (MockSolver)"

    @staticmethod
    def supports(puzzle: Puzzle) -> bool:
        return (
            puzzle.name == "Cross 5x5"
            and puzzle.row_clues == ((1,), (3,), (5,), (3,), (1,))
            and puzzle.col_clues == ((1,), (3,), (5,), (3,), (1,))
        )

    def steps(
        self, puzzle: Puzzle, cancel_event: threading.Event
    ) -> Iterator[SearchStep]:
        if not self.supports(puzzle):
            raise ValueError(
                "The demo is only available for the built-in Cross 5x5 puzzle."
            )

        scripted = [
            SearchStep(
                unknown_board(puzzle),
                SearchAction.START,
                message="Initialize the 5×5 demo board.",
                stats=SearchStats(nodes_expanded=0, nodes_generated=1, backtracks=0),
            ),
            SearchStep(
                _board("?#???", "?????", "?????", "?????", "?????"),
                SearchAction.TRY,
                SearchFocus("cell", row=0, col=1),
                "Try a filled cell at row 1, column 2.",
                SearchStats(nodes_expanded=1, nodes_generated=2, backtracks=0),
            ),
            SearchStep(
                _board("?#???", ".###.", "?????", "?????", "?????"),
                SearchAction.ACCEPT,
                SearchFocus("row", row=1),
                "Temporarily accept the configuration for row 2.",
                SearchStats(nodes_expanded=2, nodes_generated=3, backtracks=0),
            ),
            SearchStep(
                _board("?#???", ".###.", "#####", "?????", "?????"),
                SearchAction.REJECT,
                SearchFocus("column", col=1),
                "Reject the branch: the first choice conflicts with column 2 clues.",
                SearchStats(nodes_expanded=3, nodes_generated=3, backtracks=0),
            ),
            SearchStep(
                _board("?????", ".###.", "#####", "?????", "?????"),
                SearchAction.BACKTRACK,
                SearchFocus("cell", row=0, col=1),
                "Backtrack and undo the incorrect choice in row 1.",
                SearchStats(nodes_expanded=3, nodes_generated=3, backtracks=1),
            ),
            SearchStep(
                _board("..#..", ".###.", "#####", "?????", "?????"),
                SearchAction.TRY,
                SearchFocus("row", row=0),
                "Try the correct configuration for row 1.",
                SearchStats(nodes_expanded=4, nodes_generated=4, backtracks=1),
            ),
            SearchStep(
                _board("..#..", ".###.", "#####", ".###.", "?????"),
                SearchAction.ACCEPT,
                SearchFocus("row", row=3),
                "Accept row 4 after checking the column constraints.",
                SearchStats(nodes_expanded=5, nodes_generated=5, backtracks=1),
            ),
            SearchStep(
                _board("..#..", ".###.", "#####", ".###.", "..#.."),
                SearchAction.SOLUTION,
                SearchFocus("state", label="goal"),
                "A valid solution was found in the simulated demo data.",
                SearchStats(nodes_expanded=6, nodes_generated=6, backtracks=1),
            ),
            SearchStep(
                _board("..#..", ".###.", "#####", ".###.", "..#.."),
                SearchAction.FINISH,
                message="The demo stream finished after the SOLUTION event.",
                stats=SearchStats(nodes_expanded=6, nodes_generated=6, backtracks=1),
                finish_reason=FinishReason.COMPLETED_AFTER_SOLUTION,
            ),
        ]

        for step in scripted:
            if cancel_event.is_set():
                yield SearchStep(
                    step.board,
                    SearchAction.FINISH,
                    message="The solver session was cancelled.",
                    stats=step.stats,
                    finish_reason=FinishReason.CANCELLED,
                )
                return
            yield step


class WorkerEventKind(str, Enum):
    STEP = "step"
    ERROR = "error"
    ENDED = "ended"


@dataclass(frozen=True, slots=True)
class WorkerEvent:
    session_id: int
    kind: WorkerEventKind
    step: SearchStep | None = None
    error: str = ""


class SolverWorker:
    """Runs a solver away from Qt's main thread with bounded buffering."""

    def __init__(
        self,
        solver: Solver,
        puzzle: Puzzle,
        session_id: int,
        max_queue_size: int = 64,
    ) -> None:
        self.events: queue.Queue[WorkerEvent] = queue.Queue(maxsize=max_queue_size)
        self._solver = solver
        self._puzzle = puzzle
        self._session_id = session_id
        self._cancel_event = threading.Event()
        self._thread = threading.Thread(
            target=self._produce,
            name=f"solver-session-{session_id}",
            daemon=True,
        )

    def start(self) -> None:
        self._thread.start()

    def cancel(self) -> None:
        self._cancel_event.set()

    def wait(self, timeout: float | None = None) -> bool:
        """Wait for cooperative shutdown and report whether the worker stopped."""

        self._thread.join(timeout)
        return not self._thread.is_alive()

    @property
    def is_alive(self) -> bool:
        return self._thread.is_alive()

    def _put(self, event: WorkerEvent) -> bool:
        while not self._cancel_event.is_set():
            try:
                self.events.put(event, timeout=0.1)
                return True
            except queue.Full:
                continue
        return False

    def _produce(self) -> None:
        try:
            for step in self._solver.steps(self._puzzle, self._cancel_event):
                step.validate_dimensions(self._puzzle)
                if not self._put(
                    WorkerEvent(self._session_id, WorkerEventKind.STEP, step=step)
                ):
                    return
            self._put(WorkerEvent(self._session_id, WorkerEventKind.ENDED))
        except Exception as exc:  # noqa: BLE001 - isolate third-party solver failures
            self._put(
                WorkerEvent(
                    self._session_id,
                    WorkerEventKind.ERROR,
                    error=f"{type(exc).__name__}: {exc}",
                )
            )
