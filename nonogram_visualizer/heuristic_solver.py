"""Heuristic solver template.

This module intentionally contains no search implementation. Complete the TODO
inside ``HeuristicSolver.steps`` and then enable Heuristic in the UI.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from dataclasses import dataclass

from .models import Puzzle, SearchStep


@dataclass(slots=True)
class HeuristicSolver:
    """Heuristic-search adapter for the shared visualizer contract.

    Implementation checklist:
    - Keep algorithm-specific state and priority values private to this class.
    - Start from ``unknown_board(puzzle)`` and emit ``START`` for the root.
    - Use ``SearchFocus('frontier', label=...)`` for frontier information.
    - A step may focus a cell, row, column, frontier entry, or whole state.
    - Check ``cancel_event`` inside every potentially long-running loop.
    - Emit ``SOLUTION`` only after validating a complete solution.
    - End with exactly one ``FINISH`` event and the correct ``FinishReason``.
    - Use the same statistics and timing conventions as the DFS solver.
    """

    name: str = "Heuristic"

    def steps(
        self,
        puzzle: Puzzle,
        cancel_event: threading.Event,
    ) -> Iterator[SearchStep]:
        """Yield heuristic-search events in chronological order.

        ``SearchStep`` freezes each board at construction time, so the search
        engine may continue mutating its private board after yielding a step.
        Keep heuristic scores in internal states or ``SearchFocus.label``;
        never encode them into the shared board representation.
        """

        _ = puzzle, cancel_event
        raise NotImplementedError(
            "HeuristicSolver is a template. Implement steps() before enabling Heuristic."
        )
        yield  # pragma: no cover - keeps this method an explicit generator
