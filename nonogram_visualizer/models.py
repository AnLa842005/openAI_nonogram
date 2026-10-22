"""Shared, solver-agnostic data models for the Nonograms visualizer."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from pathlib import Path
from types import MappingProxyType
from typing import Any, TypeAlias


class PuzzleValidationError(ValueError):
    """Raised when a puzzle does not satisfy the shared input contract."""


class CellState(IntEnum):
    UNKNOWN = -1
    EMPTY = 0
    FILLED = 1


class SearchAction(str, Enum):
    START = "START"
    TRY = "TRY"
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    BACKTRACK = "BACKTRACK"
    SOLUTION = "SOLUTION"
    FINISH = "FINISH"


class FinishReason(str, Enum):
    """Why a FINISH event was emitted.

    A solution is announced by SOLUTION only. SOLVED merely closes a stream
    which has already emitted SOLUTION. Legacy mock adapters may still use the
    original completion reasons.
    """

    SOLVED = "solved"
    NO_SOLUTION = "no_solution"
    CANCELLED = "cancelled"
    LIMIT_REACHED = "limit_reached"
    ERROR = "error"

    # Backward-compatible reasons used by the original mock solver.
    COMPLETED_AFTER_SOLUTION = "completed_after_solution"
    EXHAUSTED = "exhausted"


Clues: TypeAlias = tuple[tuple[int, ...], ...]
BoardSnapshot: TypeAlias = tuple[tuple[CellState, ...], ...]


def _normalise_clues(raw: Any, field_name: str) -> Clues:
    if not isinstance(raw, (list, tuple)):
        raise PuzzleValidationError(
            f"'{field_name}' must be an array of integer arrays."
        )

    result: list[tuple[int, ...]] = []
    for line_index, line in enumerate(raw, start=1):
        if not isinstance(line, (list, tuple)):
            raise PuzzleValidationError(
                f"{field_name}[{line_index - 1}] must be an array of integers."
            )
        groups: list[int] = []
        for group_index, value in enumerate(line):
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise PuzzleValidationError(
                    f"{field_name}[{line_index - 1}][{group_index}] must be a positive integer."
                )
            groups.append(value)
        result.append(tuple(groups))
    return tuple(result)


@dataclass(frozen=True, slots=True)
class Puzzle:
    name: str
    row_clues: Clues
    col_clues: Clues
    metadata: Mapping[str, Any] = field(default_factory=dict, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise PuzzleValidationError("'name' must be a non-empty string.")

        rows = _normalise_clues(self.row_clues, "row_clues")
        cols = _normalise_clues(self.col_clues, "col_clues")
        if not rows or not cols:
            raise PuzzleValidationError(
                "A puzzle must have at least one row and one column."
            )

        object.__setattr__(self, "name", self.name.strip())
        object.__setattr__(self, "row_clues", rows)
        object.__setattr__(self, "col_clues", cols)
        if not isinstance(self.metadata, Mapping):
            raise PuzzleValidationError("'metadata' must be an object when provided.")
        try:
            metadata = deepcopy(dict(self.metadata))
            json.dumps(metadata)
        except (TypeError, ValueError) as exc:
            raise PuzzleValidationError(
                "'metadata' must contain JSON-serializable data."
            ) from exc
        object.__setattr__(self, "metadata", MappingProxyType(metadata))

        for index, clues in enumerate(rows):
            required = sum(clues) + max(0, len(clues) - 1)
            if required > len(cols):
                raise PuzzleValidationError(
                    f"Row {index + 1} clues require at least {required} cells, "
                    f"but the board is only {len(cols)} cells wide."
                )

        for index, clues in enumerate(cols):
            required = sum(clues) + max(0, len(clues) - 1)
            if required > len(rows):
                raise PuzzleValidationError(
                    f"Column {index + 1} clues require at least {required} cells, "
                    f"but the board is only {len(rows)} cells high."
                )

        row_total = sum(sum(line) for line in rows)
        col_total = sum(sum(line) for line in cols)
        if row_total != col_total:
            raise PuzzleValidationError(
                "The total filled cells in row clues "
                f"({row_total}) does not equal the total in column clues ({col_total})."
            )

    @property
    def height(self) -> int:
        return len(self.row_clues)

    @property
    def width(self) -> int:
        return len(self.col_clues)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> Puzzle:
        if not isinstance(data, Mapping):
            raise PuzzleValidationError("The JSON root must be an object.")
        missing = [key for key in ("name", "row_clues", "col_clues") if key not in data]
        if missing:
            raise PuzzleValidationError(
                f"Missing required fields: {', '.join(missing)}."
            )
        return cls(
            name=data["name"],
            row_clues=data["row_clues"],
            col_clues=data["col_clues"],
            metadata=data.get("metadata", {}),
        )

    def to_mapping(self, include_metadata: bool = True) -> dict[str, Any]:
        data: dict[str, Any] = {
            "name": self.name,
            "row_clues": [list(line) for line in self.row_clues],
            "col_clues": [list(line) for line in self.col_clues],
        }
        if include_metadata and self.metadata:
            data["metadata"] = deepcopy(dict(self.metadata))
        return data

    @classmethod
    def from_json_file(cls, path: str | Path) -> Puzzle:
        try:
            with Path(path).open("r", encoding="utf-8") as source:
                data = json.load(source)
        except json.JSONDecodeError as exc:
            raise PuzzleValidationError(
                f"Invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}."
            ) from exc
        except OSError as exc:
            raise PuzzleValidationError(f"Could not read the file: {exc}.") from exc
        return cls.from_mapping(data)

    def to_json_file(self, path: str | Path, include_metadata: bool = True) -> None:
        try:
            Path(path).write_text(
                json.dumps(
                    self.to_mapping(include_metadata=include_metadata),
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            raise PuzzleValidationError(f"Could not write the file: {exc}.") from exc


@dataclass(frozen=True, slots=True)
class SearchStats:
    nodes_expanded: int | None = None
    nodes_generated: int | None = None
    backtracks: int | None = None
    solver_time_ms: float | None = None
    peak_memory_bytes: int | None = None
    max_depth: int | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "nodes_expanded",
            "nodes_generated",
            "backtracks",
            "max_depth",
            "peak_memory_bytes",
        ):
            value = getattr(self, field_name)
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or value < 0
            ):
                raise ValueError(
                    f"{field_name} must be a non-negative integer or None."
                )
        if self.solver_time_ms is not None:
            if isinstance(self.solver_time_ms, bool) or not isinstance(
                self.solver_time_ms, (int, float)
            ):
                raise ValueError(
                    "solver_time_ms must be a non-negative number or None."
                )
            if self.solver_time_ms < 0:
                raise ValueError(
                    "solver_time_ms must be a non-negative number or None."
                )


@dataclass(frozen=True, slots=True)
class SearchFocus:
    """Optional focus that works for row, column, cell, or frontier states."""

    kind: str
    row: int | None = None
    col: int | None = None
    label: str = ""

    def __post_init__(self) -> None:
        if self.kind not in {"row", "column", "cell", "frontier", "state"}:
            raise ValueError(
                "focus.kind must be row, column, cell, frontier, or state."
            )
        if self.row is not None and self.row < 0:
            raise ValueError("focus.row cannot be negative.")
        if self.col is not None and self.col < 0:
            raise ValueError("focus.col cannot be negative.")


def freeze_board(board: Iterable[Iterable[int | CellState]]) -> BoardSnapshot:
    """Copy a board into an immutable snapshot, rejecting unknown cell values."""

    frozen_rows: list[tuple[CellState, ...]] = []
    for row in board:
        frozen_row: list[CellState] = []
        for value in row:
            try:
                frozen_row.append(CellState(value))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Invalid cell state: {value!r}.") from exc
        frozen_rows.append(tuple(frozen_row))
    return tuple(frozen_rows)


def unknown_board(puzzle: Puzzle) -> BoardSnapshot:
    return tuple(
        tuple(CellState.UNKNOWN for _ in range(puzzle.width))
        for _ in range(puzzle.height)
    )


@dataclass(frozen=True, slots=True)
class SearchStep:
    board: BoardSnapshot
    action: SearchAction
    focus: SearchFocus | None = None
    message: str = ""
    stats: SearchStats = field(default_factory=SearchStats)
    finish_reason: FinishReason | None = None

    def __post_init__(self) -> None:
        # Always copy at the boundary, even if a solver passes mutable lists.
        object.__setattr__(self, "board", freeze_board(self.board))
        object.__setattr__(self, "action", SearchAction(self.action))
        if self.finish_reason is not None:
            object.__setattr__(self, "finish_reason", FinishReason(self.finish_reason))
        if self.action is SearchAction.FINISH and self.finish_reason is None:
            raise ValueError("A FINISH event must include finish_reason.")
        if self.action is not SearchAction.FINISH and self.finish_reason is not None:
            raise ValueError("finish_reason can only be used with a FINISH event.")

    def validate_dimensions(self, puzzle: Puzzle) -> None:
        if len(self.board) != puzzle.height:
            raise ValueError(
                f"Snapshot has {len(self.board)} rows; the puzzle requires {puzzle.height}."
            )
        if any(len(row) != puzzle.width for row in self.board):
            raise ValueError(
                f"Every snapshot row must contain exactly {puzzle.width} cells."
            )
        if self.focus is not None:
            if self.focus.row is not None and self.focus.row >= puzzle.height:
                raise ValueError("focus.row is outside the board.")
            if self.focus.col is not None and self.focus.col >= puzzle.width:
                raise ValueError("focus.col is outside the board.")
