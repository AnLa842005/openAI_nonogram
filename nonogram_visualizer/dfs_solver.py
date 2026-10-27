"""Deterministic row-by-row DFS solver for Nonograms.

The same search core powers the visual event stream and the headless runner.
It deliberately uses no row reordering, MRV, or external solver.
"""

from __future__ import annotations

import argparse
import threading
import time
import tracemalloc
from collections.abc import Callable, Generator, Iterator, Sequence
from dataclasses import dataclass, replace
from enum import Enum
from typing import Protocol

from .generator import clues_for_line
from .models import (
    BoardSnapshot,
    CellState,
    FinishReason,
    Puzzle,
    SearchAction,
    SearchFocus,
    SearchStats,
    SearchStep,
    freeze_board,
)

Pattern = tuple[int, ...]


class SolveStatus(str, Enum):
    """Terminal status returned by the framework-independent DFS core."""

    SOLVED = "SOLVED"
    NO_SOLUTION = "NO_SOLUTION"
    CANCELLED = "CANCELLED"
    LIMIT_REACHED = "LIMIT_REACHED"
    ERROR = "ERROR"


@dataclass(frozen=True, slots=True)
class SolveResult:
    status: SolveStatus
    board: BoardSnapshot
    stats: SearchStats
    message: str = ""


class HeadlessSolver(Protocol):
    """Solver that can also run without emitting visual trace events."""

    def solve(
        self,
        puzzle: Puzzle,
        cancel_event: threading.Event | None = None,
    ) -> SolveResult: ...


class _SearchCancelled(Exception):
    pass


class _PatternLimitReached(Exception):
    pass


@dataclass(slots=True)
class _MutableStats:
    nodes_expanded: int = 0
    nodes_generated: int = 0
    backtracks: int = 0
    max_depth: int = 0


class _ActiveTimer:
    """perf_counter timer that excludes time while a trace event is yielded."""

    def __init__(self) -> None:
        self._elapsed = 0.0
        self._started_at: float | None = time.perf_counter()

    def pause(self) -> None:
        if self._started_at is not None:
            self._elapsed += time.perf_counter() - self._started_at
            self._started_at = None

    def resume(self) -> None:
        if self._started_at is None:
            self._started_at = time.perf_counter()

    @property
    def elapsed_ms(self) -> float:
        elapsed = self._elapsed
        if self._started_at is not None:
            elapsed += time.perf_counter() - self._started_at
        return elapsed * 1000.0


def generate_patterns(
    length: int,
    clues: Sequence[int],
    cancel_event: threading.Event | None = None,
    pattern_limit: int | None = None,
) -> tuple[Pattern, ...]:
    """Generate valid line patterns by placing clue groups left to right.

    Patterns are deterministic and unique. Cancellation and an optional hard
    limit are checked while groups are placed. Exceeding the limit raises
    instead of returning a truncated set that could imply no solution.
    """

    if isinstance(length, bool) or not isinstance(length, int) or length < 0:
        raise ValueError("length must be a non-negative integer")
    normalized = tuple(clues)
    if any(
        isinstance(group, bool) or not isinstance(group, int) or group <= 0
        for group in normalized
    ):
        raise ValueError("clues must contain positive integers")
    if pattern_limit is not None and (
        isinstance(pattern_limit, bool)
        or not isinstance(pattern_limit, int)
        or pattern_limit <= 0
    ):
        raise ValueError("pattern_limit must be a positive integer or None")

    event = cancel_event or threading.Event()
    patterns: list[Pattern] = []

    def check_cancelled() -> None:
        if event.is_set():
            raise _SearchCancelled

    def append_pattern(pattern: Pattern) -> None:
        check_cancelled()
        if pattern_limit is not None and len(patterns) >= pattern_limit:
            raise _PatternLimitReached
        patterns.append(pattern)

    check_cancelled()
    required = sum(normalized) + max(0, len(normalized) - 1)
    if required > length:
        return ()
    if not normalized:
        append_pattern((0,) * length)
        return tuple(patterns)

    def place(group_index: int, minimum_start: int, cells: list[int]) -> None:
        check_cancelled()
        remaining = normalized[group_index:]
        remaining_width = sum(remaining) + len(remaining) - 1
        latest_start = length - remaining_width
        group_size = normalized[group_index]

        for start in range(minimum_start, latest_start + 1):
            check_cancelled()
            candidate = cells.copy()
            candidate[start : start + group_size] = [1] * group_size
            if group_index + 1 == len(normalized):
                append_pattern(tuple(candidate))
            else:
                place(group_index + 1, start + group_size + 1, candidate)

    place(0, 0, [0] * length)
    return tuple(patterns)


def validate_solution(puzzle: Puzzle, board: Sequence[Sequence[int]]) -> bool:
    """Strictly validate a complete 0/1 board independently of DFS pruning."""

    if len(board) != puzzle.height or any(len(row) != puzzle.width for row in board):
        return False
    try:
        snapshot = freeze_board(board)
    except ValueError:
        return False
    if any(
        cell not in (CellState.EMPTY, CellState.FILLED)
        for row in snapshot
        for cell in row
    ):
        return False
    if tuple(clues_for_line(row) for row in snapshot) != puzzle.row_clues:
        return False
    columns = (
        tuple(snapshot[row][col] for row in range(puzzle.height))
        for col in range(puzzle.width)
    )
    return tuple(clues_for_line(column) for column in columns) == puzzle.col_clues


@dataclass(slots=True)
class DFSSolver:
    """Depth-first search using fixed top-to-bottom row order."""

    name: str = "DFS"
    pattern_limit: int | None = None

    def steps(
        self,
        puzzle: Puzzle,
        cancel_event: threading.Event,
    ) -> Iterator[SearchStep]:
        """Yield immutable DFS events and finish with exactly one FINISH."""

        result = yield from self._run(puzzle, cancel_event, tracing=True)
        _ = result

    def solve(
        self,
        puzzle: Puzzle,
        cancel_event: threading.Event | None = None,
    ) -> SolveResult:
        """Run headlessly without constructing per-step snapshots or messages."""

        stream = self._run(
            puzzle,
            cancel_event or threading.Event(),
            tracing=False,
        )
        while True:
            try:
                next(stream)
            except StopIteration as stopped:
                return stopped.value

    def _run(
        self,
        puzzle: Puzzle,
        cancel_event: threading.Event,
        *,
        tracing: bool,
    ) -> Generator[SearchStep, None, SolveResult]:
        board = [
            [CellState.UNKNOWN for _ in range(puzzle.width)]
            for _ in range(puzzle.height)
        ]
        counters = _MutableStats()
        timer = _ActiveTimer()

        def current_stats() -> SearchStats:
            return SearchStats(
                nodes_expanded=counters.nodes_expanded,
                nodes_generated=counters.nodes_generated,
                backtracks=counters.backtracks,
                max_depth=counters.max_depth,
                solver_time_ms=timer.elapsed_ms,
            )

        def emit(
            action: SearchAction,
            focus: SearchFocus | None = None,
            message: str = "",
            finish_reason: FinishReason | None = None,
        ) -> Generator[SearchStep, None, None]:
            if not tracing:
                return
            timer.pause()
            yield SearchStep(
                board,
                action,
                focus=focus,
                message=message,
                stats=current_stats(),
                finish_reason=finish_reason,
            )
            timer.resume()

        if tracing:
            yield from emit(
                SearchAction.START,
                SearchFocus("state", label="root"),
                "Start DFS from an UNKNOWN board and generate line patterns.",
            )

        try:
            row_patterns = tuple(
                generate_patterns(
                    puzzle.width,
                    clues,
                    cancel_event,
                    self.pattern_limit,
                )
                for clues in puzzle.row_clues
            )
            column_patterns = tuple(
                generate_patterns(
                    puzzle.height,
                    clues,
                    cancel_event,
                    self.pattern_limit,
                )
                for clues in puzzle.col_clues
            )

            def search(
                row_index: int,
                viable_columns: tuple[tuple[Pattern, ...], ...],
            ) -> Generator[SearchStep, None, BoardSnapshot | None]:
                if cancel_event.is_set():
                    raise _SearchCancelled
                if row_index == puzzle.height:
                    if validate_solution(puzzle, board):
                        return freeze_board(board)
                    return None

                counters.nodes_expanded += 1
                for pattern in row_patterns[row_index]:
                    if cancel_event.is_set():
                        raise _SearchCancelled
                    board[row_index] = [CellState(value) for value in pattern]
                    counters.nodes_generated += 1
                    counters.max_depth = max(counters.max_depth, row_index + 1)
                    if tracing:
                        yield from emit(
                            SearchAction.TRY,
                            SearchFocus("row", row=row_index),
                            f"Try pattern {''.join(map(str, pattern))} for row {row_index + 1}.",
                        )

                    next_columns: list[tuple[Pattern, ...]] = []
                    conflict_col: int | None = None
                    for col, candidates in enumerate(viable_columns):
                        matching = tuple(
                            candidate
                            for candidate in candidates
                            if candidate[row_index] == pattern[col]
                        )
                        if not matching:
                            conflict_col = col
                            break
                        next_columns.append(matching)

                    if conflict_col is not None:
                        if tracing:
                            yield from emit(
                                SearchAction.REJECT,
                                SearchFocus("column", col=conflict_col),
                                f"Reject row {row_index + 1}: column "
                                f"{conflict_col + 1} has no matching completion.",
                            )
                        board[row_index] = [CellState.UNKNOWN] * puzzle.width
                        if tracing:
                            yield from emit(
                                SearchAction.BACKTRACK,
                                SearchFocus("row", row=row_index),
                                f"Restore row {row_index + 1} after the rejected pattern.",
                            )
                        continue

                    if tracing:
                        yield from emit(
                            SearchAction.ACCEPT,
                            SearchFocus("row", row=row_index),
                            f"Accept row {row_index + 1}; every column prefix remains feasible.",
                        )
                    solution = yield from search(row_index + 1, tuple(next_columns))
                    if solution is not None:
                        return solution

                    counters.backtracks += 1
                    board[row_index] = [CellState.UNKNOWN] * puzzle.width
                    if tracing:
                        yield from emit(
                            SearchAction.BACKTRACK,
                            SearchFocus("row", row=row_index),
                            f"Backtrack from row {row_index + 1} after its child branch failed.",
                        )

                board[row_index] = [CellState.UNKNOWN] * puzzle.width
                return None

            solution = yield from search(0, column_patterns)
            timer.pause()
            if solution is not None:
                board[:] = [list(row) for row in solution]
                if not validate_solution(puzzle, board):
                    raise RuntimeError("DFS produced a board that failed final validation")
                if tracing:
                    yield from emit(
                        SearchAction.SOLUTION,
                        SearchFocus("state", label="goal"),
                        "Found and independently validated a complete solution.",
                    )
                timer.pause()
                result = SolveResult(
                    SolveStatus.SOLVED,
                    solution,
                    current_stats(),
                    "A valid solution was found.",
                )
                if tracing:
                    yield from emit(
                        SearchAction.FINISH,
                        message="DFS finished with SOLVED status.",
                        finish_reason=FinishReason.SOLVED,
                    )
                return result

            empty_board = freeze_board(board)
            result = SolveResult(
                SolveStatus.NO_SOLUTION,
                empty_board,
                current_stats(),
                "The complete search space was exhausted.",
            )
            if tracing:
                yield from emit(
                    SearchAction.FINISH,
                    message="DFS finished with NO_SOLUTION status after exhaustive search.",
                    finish_reason=FinishReason.NO_SOLUTION,
                )
            return result

        except _SearchCancelled:
            timer.pause()
            result = SolveResult(
                SolveStatus.CANCELLED,
                freeze_board(board),
                current_stats(),
                "The DFS run was cancelled.",
            )
            if tracing:
                yield from emit(
                    SearchAction.FINISH,
                    message="DFS finished with CANCELLED status.",
                    finish_reason=FinishReason.CANCELLED,
                )
            return result
        except _PatternLimitReached:
            timer.pause()
            result = SolveResult(
                SolveStatus.LIMIT_REACHED,
                freeze_board(board),
                current_stats(),
                "The configured per-line pattern limit was reached.",
            )
            if tracing:
                yield from emit(
                    SearchAction.FINISH,
                    message=(
                        "DFS finished with LIMIT_REACHED status; "
                        "no unsatisfiability conclusion was made."
                    ),
                    finish_reason=FinishReason.LIMIT_REACHED,
                )
            return result
        except Exception as exc:  # noqa: BLE001 - expose a terminal protocol status
            timer.pause()
            message = f"{type(exc).__name__}: {exc}"
            result = SolveResult(
                SolveStatus.ERROR,
                freeze_board(board),
                current_stats(),
                message,
            )
            if tracing:
                yield from emit(
                    SearchAction.FINISH,
                    message=f"DFS finished with ERROR status: {message}",
                    finish_reason=FinishReason.ERROR,
                )
            return result


def benchmark(
    puzzle: Puzzle,
    *,
    measure_memory: bool = False,
    solver_factory: Callable[[], HeadlessSolver] = DFSSolver,
) -> SolveResult:
    """Run a cold, headless benchmark with optional separate memory run."""

    result = solver_factory().solve(puzzle)
    if not measure_memory:
        return result

    tracemalloc.start()
    try:
        memory_result = solver_factory().solve(puzzle)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    if memory_result.status is not result.status:
        return SolveResult(
            SolveStatus.ERROR,
            result.board,
            result.stats,
            "Timing and memory benchmark runs produced different statuses.",
        )
    return replace(result, stats=replace(result.stats, peak_memory_bytes=peak))


def run_cli(solver_factory: Callable[[], HeadlessSolver], description: str) -> None:
    """Shared headless entry point so every solver reports identical fields."""

    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("puzzle", help="Path to a puzzle JSON file")
    parser.add_argument(
        "--memory",
        action="store_true",
        help="measure peak Python allocations in a separate cold run",
    )
    args = parser.parse_args()
    puzzle = Puzzle.from_json_file(args.puzzle)
    result = benchmark(
        puzzle, measure_memory=args.memory, solver_factory=solver_factory
    )
    print(f"status: {result.status.value}")
    print(f"nodes_generated: {result.stats.nodes_generated}")
    print(f"nodes_expanded: {result.stats.nodes_expanded}")
    print(f"backtracks: {result.stats.backtracks}")
    print(f"max_depth: {result.stats.max_depth}")
    print(f"solver_time_ms: {result.stats.solver_time_ms:.3f}")
    memory = result.stats.peak_memory_bytes
    print(f"peak_python_allocations_bytes: {memory if memory is not None else '—'}")
    print("pattern_cache: cold (scoped to one solve)")
    if result.status is SolveStatus.SOLVED:
        for row in result.board:
            print("".join("1" if cell is CellState.FILLED else "0" for cell in row))
    raise SystemExit(0 if result.status is SolveStatus.SOLVED else 1)


def main() -> None:
    run_cli(DFSSolver, "Run the Nonograms DFS headlessly.")


if __name__ == "__main__":
    main()
