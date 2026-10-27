"""Solver contract and a bounded worker-thread adapter."""

from __future__ import annotations

import queue
import threading
from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from .models import Puzzle, SearchStep


class Solver(Protocol):
    """Common interface implemented by visualized search solvers."""

    name: str

    def steps(
        self, puzzle: Puzzle, cancel_event: threading.Event
    ) -> Iterator[SearchStep]:
        """Yield immutable search snapshots in chronological order."""
        ...


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
