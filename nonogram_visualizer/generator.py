"""Random puzzle generation from a known source board."""

from __future__ import annotations

import random
import secrets
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from .models import BoardSnapshot, CellState, Clues, Puzzle, freeze_board

MIN_SIZE = 2
MAX_SIZE = 30


def clues_for_line(line: Iterable[int | CellState]) -> tuple[int, ...]:
    """Return consecutive FILLED group lengths; an empty line becomes ()."""

    groups: list[int] = []
    run = 0
    for value in line:
        state = CellState(value)
        if state is CellState.FILLED:
            run += 1
        elif run:
            groups.append(run)
            run = 0
    if run:
        groups.append(run)
    return tuple(groups)


def clues_for_board(
    board: Sequence[Sequence[int | CellState]],
) -> tuple[Clues, Clues]:
    snapshot = freeze_board(board)
    if not snapshot or not snapshot[0]:
        raise ValueError("The board must have at least one row and one column.")
    width = len(snapshot[0])
    if any(len(row) != width for row in snapshot):
        raise ValueError("The board must be rectangular.")
    row_clues = tuple(clues_for_line(row) for row in snapshot)
    col_clues = tuple(
        clues_for_line(snapshot[row][col] for row in range(len(snapshot)))
        for col in range(width)
    )
    return row_clues, col_clues


@dataclass(frozen=True, slots=True)
class GeneratedPuzzle:
    puzzle: Puzzle
    source_board: BoardSnapshot
    seed: int
    density: float


def generate_random_puzzle(
    rows: int,
    cols: int,
    density: float = 0.5,
    seed: int | None = None,
    name: str | None = None,
) -> GeneratedPuzzle:
    """Generate clues from a random board, guaranteeing at least that solution.

    The function does not test uniqueness and does not estimate difficulty.
    """

    for field_name, value in (("rows", rows), ("cols", cols)):
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"{field_name} must be an integer.")
        if not MIN_SIZE <= value <= MAX_SIZE:
            raise ValueError(f"{field_name} must be between {MIN_SIZE} and {MAX_SIZE}.")
    if isinstance(density, bool) or not isinstance(density, (int, float)):
        raise TypeError("density must be a number between 0 and 1.")
    density = float(density)
    if not 0.0 <= density <= 1.0:
        raise ValueError("density must be a number between 0 and 1.")
    if seed is not None and (isinstance(seed, bool) or not isinstance(seed, int)):
        raise ValueError("seed must be an integer or None.")

    actual_seed = secrets.randbits(64) if seed is None else seed
    rng = random.Random(actual_seed)
    source_board = tuple(
        tuple(
            CellState.FILLED if rng.random() < density else CellState.EMPTY
            for _ in range(cols)
        )
        for _ in range(rows)
    )
    row_clues, col_clues = clues_for_board(source_board)
    puzzle = Puzzle(
        name=name or f"Random {rows}x{cols}",
        row_clues=row_clues,
        col_clues=col_clues,
        metadata={
            "generator": "random-board-v1",
            "seed": actual_seed,
            "expected_density": density,
        },
    )
    return GeneratedPuzzle(puzzle, source_board, actual_seed, density)
