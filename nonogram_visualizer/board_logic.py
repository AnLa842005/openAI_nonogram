"""Pure play-mode board operations, history, and clue checking."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum

from .generator import clues_for_line
from .models import BoardSnapshot, CellState, Puzzle, freeze_board, unknown_board


class PlayTool(str, Enum):
    FILL = "fill"
    MARK_X = "mark_x"
    ERASE = "erase"


@dataclass(frozen=True, slots=True)
class BoardCheckResult:
    solved: bool
    mismatched_rows: tuple[int, ...]
    mismatched_cols: tuple[int, ...]


def check_board(
    puzzle: Puzzle, board: Iterable[Iterable[int | CellState]]
) -> BoardCheckResult:
    """Compare FILLED groups with clues; UNKNOWN and EMPTY both count as white."""

    snapshot = freeze_board(board)
    if len(snapshot) != puzzle.height or any(
        len(row) != puzzle.width for row in snapshot
    ):
        raise ValueError("Board dimensions do not match the puzzle.")
    mismatched_rows = tuple(
        row
        for row in range(puzzle.height)
        if clues_for_line(snapshot[row]) != puzzle.row_clues[row]
    )
    mismatched_cols = tuple(
        col
        for col in range(puzzle.width)
        if clues_for_line(snapshot[row][col] for row in range(puzzle.height))
        != puzzle.col_clues[col]
    )
    return BoardCheckResult(
        solved=not mismatched_rows and not mismatched_cols,
        mismatched_rows=mismatched_rows,
        mismatched_cols=mismatched_cols,
    )


def stroke_target(current: CellState, button: int, tool: PlayTool) -> CellState:
    """Choose one target for an entire stroke from its first cell."""

    if button == 3:
        return CellState.UNKNOWN if current is CellState.EMPTY else CellState.EMPTY
    if tool is PlayTool.ERASE:
        return CellState.UNKNOWN
    if tool is PlayTool.MARK_X:
        return CellState.UNKNOWN if current is CellState.EMPTY else CellState.EMPTY
    return CellState.UNKNOWN if current is CellState.FILLED else CellState.FILLED


class PlaySession:
    """Mutable play board with snapshot-based undo/redo and stroke grouping."""

    def __init__(self, puzzle: Puzzle) -> None:
        self.puzzle = puzzle
        self._board = [list(row) for row in unknown_board(puzzle)]
        self._undo: list[BoardSnapshot] = []
        self._redo: list[BoardSnapshot] = []
        self._stroke_before: BoardSnapshot | None = None
        self._stroke_target: CellState | None = None
        self._stroke_cells: set[tuple[int, int]] = set()
        self._stroke_changed = False

    @property
    def board(self) -> BoardSnapshot:
        return freeze_board(self._board)

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    @property
    def marked_count(self) -> int:
        return sum(cell is not CellState.UNKNOWN for row in self._board for cell in row)

    @property
    def has_progress(self) -> bool:
        return self.marked_count > 0

    def begin_stroke(self, row: int, col: int, button: int, tool: PlayTool) -> bool:
        self._check_cell(row, col)
        if self._stroke_before is not None:
            self.end_stroke()
        self._stroke_before = self.board
        self._stroke_target = stroke_target(self._board[row][col], button, tool)
        self._stroke_cells = set()
        self._stroke_changed = False
        return self.paint_cell(row, col)

    def paint_cell(self, row: int, col: int) -> bool:
        self._check_cell(row, col)
        cell = (row, col)
        if (
            self._stroke_before is None
            or self._stroke_target is None
            or cell in self._stroke_cells
        ):
            return False
        self._stroke_cells.add(cell)
        if self._board[row][col] is self._stroke_target:
            return False
        self._board[row][col] = self._stroke_target
        self._stroke_changed = True
        return True

    def end_stroke(self) -> bool:
        changed = self._stroke_changed
        if changed and self._stroke_before is not None:
            self._undo.append(self._stroke_before)
            self._redo.clear()
        self._stroke_before = None
        self._stroke_target = None
        self._stroke_cells.clear()
        self._stroke_changed = False
        return changed

    def click(
        self, row: int, col: int, button: int = 1, tool: PlayTool = PlayTool.FILL
    ) -> bool:
        self.begin_stroke(row, col, button, tool)
        return self.end_stroke()

    def undo(self) -> bool:
        self.end_stroke()
        if not self._undo:
            return False
        self._redo.append(self.board)
        self._restore(self._undo.pop())
        return True

    def redo(self) -> bool:
        self.end_stroke()
        if not self._redo:
            return False
        self._undo.append(self.board)
        self._restore(self._redo.pop())
        return True

    def clear(self) -> bool:
        self.end_stroke()
        if not self.has_progress:
            return False
        self._undo.append(self.board)
        self._redo.clear()
        self._restore(unknown_board(self.puzzle))
        return True

    def _restore(self, snapshot: BoardSnapshot) -> None:
        self._board = [list(row) for row in snapshot]

    def _check_cell(self, row: int, col: int) -> None:
        if not (0 <= row < self.puzzle.height and 0 <= col < self.puzzle.width):
            raise IndexError("Cell is outside the board.")
