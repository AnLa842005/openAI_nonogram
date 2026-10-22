"""Nonograms Visualizer package."""

from .board_logic import BoardCheckResult, PlaySession, PlayTool, check_board
from .generator import (
    GeneratedPuzzle,
    clues_for_board,
    clues_for_line,
    generate_random_puzzle,
)
from .models import (
    BoardSnapshot,
    CellState,
    FinishReason,
    Puzzle,
    PuzzleValidationError,
    SearchAction,
    SearchFocus,
    SearchStats,
    SearchStep,
    freeze_board,
)

__all__ = [
    "BoardCheckResult",
    "BoardSnapshot",
    "CellState",
    "FinishReason",
    "GeneratedPuzzle",
    "PlaySession",
    "PlayTool",
    "Puzzle",
    "PuzzleValidationError",
    "SearchAction",
    "SearchFocus",
    "SearchStats",
    "SearchStep",
    "check_board",
    "clues_for_board",
    "clues_for_line",
    "freeze_board",
    "generate_random_puzzle",
]
