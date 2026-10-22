"""Minimal example of adapting heuristic-engine events to SearchStep.

This file is integration documentation, not a heuristic implementation.
"""

from __future__ import annotations

import threading
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass

from nonogram_visualizer.models import (
    FinishReason,
    Puzzle,
    SearchAction,
    SearchFocus,
    SearchStats,
    SearchStep,
)


@dataclass(frozen=True)
class HeuristicEngineEvent:
    """Example internal event owned by the heuristic implementation."""

    board: Sequence[Sequence[int]]
    action: SearchAction
    message: str
    row: int | None = None
    col: int | None = None
    nodes_expanded: int | None = None
    nodes_generated: int | None = None


class HeuristicSolverAdapter:
    """Wrap a heuristic event iterable in the shared Solver protocol."""

    name = "Heuristic"

    def __init__(self, engine_events: Iterable[HeuristicEngineEvent]) -> None:
        self._engine_events = engine_events

    def steps(
        self, puzzle: Puzzle, cancel_event: threading.Event
    ) -> Iterator[SearchStep]:
        latest_board: Sequence[Sequence[int]] = [
            [-1 for _ in range(puzzle.width)] for _ in range(puzzle.height)
        ]
        yielded_solution = False

        for event in self._engine_events:
            if cancel_event.is_set():
                yield SearchStep(
                    latest_board,
                    SearchAction.FINISH,
                    message="The heuristic solver was cancelled.",
                    finish_reason=FinishReason.CANCELLED,
                )
                return

            latest_board = event.board
            focus = None
            if event.row is not None and event.col is not None:
                focus = SearchFocus("cell", row=event.row, col=event.col)
            elif event.row is not None:
                focus = SearchFocus("row", row=event.row)
            elif event.col is not None:
                focus = SearchFocus("column", col=event.col)
            step = SearchStep(
                board=event.board,  # SearchStep copies this into an immutable snapshot.
                action=event.action,
                focus=focus,
                message=event.message,
                stats=SearchStats(
                    nodes_expanded=event.nodes_expanded,
                    nodes_generated=event.nodes_generated,
                ),
            )
            yielded_solution = yielded_solution or step.action is SearchAction.SOLUTION
            yield step

        yield SearchStep(
            latest_board,
            SearchAction.FINISH,
            message="The heuristic solver has finished.",
            finish_reason=(
                FinishReason.COMPLETED_AFTER_SOLUTION
                if yielded_solution
                else FinishReason.EXHAUSTED
            ),
        )
