"""Heuristic Nonograms solver: MRV-guided DFS with constraint propagation."""

from __future__ import annotations

import threading
from collections import deque
from collections.abc import Generator, Iterable, Iterator, Sequence
from dataclasses import dataclass

from .dfs_solver import (
    SolveResult,
    SolveStatus,
    _ActiveTimer,
    _MutableStats,
    _PatternLimitReached,
    _SearchCancelled,
    generate_patterns,
    run_cli,
    validate_solution,
)
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
    unknown_board,
)

ROW = 0
COLUMN = 1
Line = tuple[int, int]  # (axis, index)
Domain = tuple[int, ...]


def pattern_to_mask(pattern: Sequence[int]) -> int:
    """Encode a 0/1 line pattern as an int whose bit ``i`` is cell ``i``."""

    mask = 0
    for index, value in enumerate(pattern):
        if value:
            mask |= 1 << index
    return mask


def _bit_positions(mask: int) -> Iterator[int]:
    while mask:
        lowest = mask & -mask
        yield lowest.bit_length() - 1
        mask ^= lowest


@dataclass(slots=True)
class HeuristicSolver:
    """DFS over cell guesses, ordered by MRV and pruned by propagation."""

    name: str = "Heuristic"
    pattern_limit: int | None = None

    def steps(
        self,
        puzzle: Puzzle,
        cancel_event: threading.Event,
    ) -> Iterator[SearchStep]:
        """Yield immutable search events and finish with exactly one FINISH."""

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
        height, width = puzzle.height, puzzle.width
        full = ((1 << width) - 1, (1 << height) - 1)
        board = [[CellState.UNKNOWN for _ in range(width)] for _ in range(height)]
        # Per-line bitmasks of decided cells and of filled cells.
        known = ([0] * height, [0] * width)
        filled = ([0] * height, [0] * width)
        domains: tuple[list[Domain], list[Domain]] = ([], [])
        trail: list[tuple] = []
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

        def finish(
            status: SolveStatus,
            reason: FinishReason,
            snapshot: BoardSnapshot,
            message: str,
        ) -> Generator[SearchStep, None, SolveResult]:
            timer.pause()
            result = SolveResult(status, snapshot, current_stats(), message)
            yield from emit(
                SearchAction.FINISH,
                message=f"Heuristic search finished with {status.value} status. {message}",
                finish_reason=reason,
            )
            return result

        def describe(line: Line) -> str:
            axis, index = line
            return f"{'row' if axis == ROW else 'column'} {index + 1}"

        def focus_on(line: Line) -> SearchFocus:
            axis, index = line
            if axis == ROW:
                return SearchFocus("row", row=index)
            return SearchFocus("column", col=index)

        def set_cell(row: int, col: int, value: int) -> None:
            board[row][col] = CellState(value)
            known[ROW][row] |= 1 << col
            known[COLUMN][col] |= 1 << row
            if value:
                filled[ROW][row] |= 1 << col
                filled[COLUMN][col] |= 1 << row
            trail.append(("cell", row, col))

        def set_domain(line: Line, domain: Domain) -> None:
            axis, index = line
            trail.append(("domain", axis, index, domains[axis][index]))
            domains[axis][index] = domain

        def undo(mark: int) -> None:
            while len(trail) > mark:
                entry = trail.pop()
                if entry[0] == "cell":
                    _, row, col = entry
                    board[row][col] = CellState.UNKNOWN
                    known[ROW][row] &= ~(1 << col)
                    known[COLUMN][col] &= ~(1 << row)
                    filled[ROW][row] &= ~(1 << col)
                    filled[COLUMN][col] &= ~(1 << row)
                else:
                    _, axis, index, previous = entry
                    domains[axis][index] = previous

        def fix_cells(line: Line, positions: int, value: int) -> list[Line]:
            """Decide cells of ``line`` and return the crossing lines touched."""

            axis, index = line
            crossings: list[Line] = []
            for position in _bit_positions(positions):
                if axis == ROW:
                    set_cell(index, position, value)
                else:
                    set_cell(position, index, value)
                crossings.append((1 - axis, position))
            return crossings

        def propagate(
            pending: Iterable[Line],
        ) -> Generator[SearchStep, None, Line | None]:
            """Run line solving to a fixed point; return a conflicting line."""

            queue = deque(pending)
            queued = set(queue)
            while queue:
                if cancel_event.is_set():
                    raise _SearchCancelled
                line = queue.popleft()
                queued.discard(line)
                axis, index = line
                line_known = known[axis][index]
                line_filled = filled[axis][index]
                domain = domains[axis][index]
                matching = tuple(
                    pattern
                    for pattern in domain
                    if (pattern ^ line_filled) & line_known == 0
                )
                if len(matching) != len(domain):
                    set_domain(line, matching)
                if not matching:
                    return line

                always = full[axis]
                ever = 0
                for pattern in matching:
                    always &= pattern
                    ever |= pattern
                undecided = full[axis] & ~line_known
                forced_filled = always & undecided
                forced_empty = ~ever & undecided
                if not forced_filled | forced_empty:
                    continue

                crossings = fix_cells(line, forced_filled, 1) + fix_cells(
                    line, forced_empty, 0
                )
                for crossing in crossings:
                    if crossing not in queued:
                        queued.add(crossing)
                        queue.append(crossing)
                if tracing:
                    yield from emit(
                        SearchAction.ACCEPT,
                        focus_on(line),
                        f"Propagate {describe(line)}: {forced_filled.bit_count()} "
                        f"filled, {forced_empty.bit_count()} empty; "
                        f"{len(matching)} candidate(s) remain.",
                    )
            return None

        def choose_line() -> Line | None:
            """MRV: the undecided line with the fewest remaining candidates."""

            best: Line | None = None
            best_size = 0
            for axis in (ROW, COLUMN):
                for index, domain in enumerate(domains[axis]):
                    size = len(domain)
                    if size > 1 and (best is None or size < best_size):
                        best, best_size = (axis, index), size
                        if size == 2:
                            return best
            return best

        def choose_cell(line: Line) -> tuple[int, int, int]:
            """Pick the undecided cell of ``line`` whose value is most certain.

            Returns ``(position, ones, size)``: how many of the ``size``
            remaining candidates fill that position. The most skewed cell is
            the one a guess is most likely to get right.
            """

            axis, index = line
            domain = domains[axis][index]
            undecided = full[axis] & ~known[axis][index]
            best_position, best_ones, best_skew = -1, 0, -1
            for position in _bit_positions(undecided):
                bit = 1 << position
                ones = sum(1 for pattern in domain if pattern & bit)
                skew = abs(2 * ones - len(domain))
                if skew > best_skew:
                    best_position, best_ones, best_skew = position, ones, skew
            return best_position, best_ones, len(domain)

        def search(depth: int) -> Generator[SearchStep, None, BoardSnapshot | None]:
            if cancel_event.is_set():
                raise _SearchCancelled
            line = choose_line()
            if line is None:
                # Every domain is a single pattern, so every cell is decided.
                if validate_solution(puzzle, board):
                    return freeze_board(board)
                return None

            counters.nodes_expanded += 1
            axis, index = line
            position, ones, size = choose_cell(line)
            row, col = (index, position) if axis == ROW else (position, index)
            # Value ordering: try the value most remaining candidates agree on.
            values = (1, 0) if 2 * ones >= size else (0, 1)
            for value in values:
                if cancel_event.is_set():
                    raise _SearchCancelled
                mark = len(trail)
                counters.nodes_generated += 1
                counters.max_depth = max(counters.max_depth, depth + 1)
                crossings = fix_cells(line, 1 << position, value)
                if tracing:
                    share = ones if value else size - ones
                    yield from emit(
                        SearchAction.TRY,
                        SearchFocus("cell", row=row, col=col),
                        f"MRV picks {describe(line)} ({size} candidates); guess cell "
                        f"({row + 1}, {col + 1}) = {'filled' if value else 'empty'} "
                        f"({share}/{size} candidates agree).",
                    )

                conflict = yield from propagate([line, *crossings])
                if conflict is not None:
                    if tracing:
                        yield from emit(
                            SearchAction.REJECT,
                            focus_on(conflict),
                            f"Reject: {describe(conflict)} has no candidate "
                            "consistent with the known cells.",
                        )
                    undo(mark)
                    if tracing:
                        yield from emit(
                            SearchAction.BACKTRACK,
                            SearchFocus("cell", row=row, col=col),
                            f"Undo the guess at ({row + 1}, {col + 1}) and its deductions.",
                        )
                    continue

                if tracing:
                    yield from emit(
                        SearchAction.ACCEPT,
                        SearchFocus("cell", row=row, col=col),
                        f"Accept the guess at ({row + 1}, {col + 1}); propagation "
                        "reached a fixed point.",
                    )
                solution = yield from search(depth + 1)
                if solution is not None:
                    return solution

                counters.backtracks += 1
                undo(mark)
                if tracing:
                    yield from emit(
                        SearchAction.BACKTRACK,
                        SearchFocus("cell", row=row, col=col),
                        f"Backtrack from ({row + 1}, {col + 1}) after its child "
                        "branch failed.",
                    )
            return None

        if tracing:
            yield from emit(
                SearchAction.START,
                SearchFocus("state", label="root"),
                "Start from an UNKNOWN board and generate line patterns as bitmasks.",
            )

        try:
            for axis, all_clues, length in (
                (ROW, puzzle.row_clues, width),
                (COLUMN, puzzle.col_clues, height),
            ):
                for clues in all_clues:
                    patterns = generate_patterns(
                        length, clues, cancel_event, self.pattern_limit
                    )
                    domains[axis].append(tuple(map(pattern_to_mask, patterns)))

            every_line = [(ROW, row) for row in range(height)] + [
                (COLUMN, col) for col in range(width)
            ]
            conflict = yield from propagate(every_line)
            if conflict is not None:
                if tracing:
                    yield from emit(
                        SearchAction.REJECT,
                        focus_on(conflict),
                        f"The clues contradict each other at {describe(conflict)}.",
                    )
                return (
                    yield from finish(
                        SolveStatus.NO_SOLUTION,
                        FinishReason.NO_SOLUTION,
                        unknown_board(puzzle),
                        "Root propagation found a contradiction.",
                    )
                )

            solution = yield from search(0)
            if solution is None:
                return (
                    yield from finish(
                        SolveStatus.NO_SOLUTION,
                        FinishReason.NO_SOLUTION,
                        unknown_board(puzzle),
                        "The complete search space was exhausted.",
                    )
                )

            timer.pause()
            if tracing:
                yield from emit(
                    SearchAction.SOLUTION,
                    SearchFocus("state", label="goal"),
                    "Found and independently validated a complete solution.",
                )
            return (
                yield from finish(
                    SolveStatus.SOLVED,
                    FinishReason.SOLVED,
                    solution,
                    "A valid solution was found.",
                )
            )

        except _SearchCancelled:
            return (
                yield from finish(
                    SolveStatus.CANCELLED,
                    FinishReason.CANCELLED,
                    freeze_board(board),
                    "The run was cancelled.",
                )
            )
        except _PatternLimitReached:
            return (
                yield from finish(
                    SolveStatus.LIMIT_REACHED,
                    FinishReason.LIMIT_REACHED,
                    freeze_board(board),
                    "The per-line pattern limit was reached; "
                    "no unsatisfiability conclusion was made.",
                )
            )
        except Exception as exc:  # noqa: BLE001 - expose a terminal protocol status
            return (
                yield from finish(
                    SolveStatus.ERROR,
                    FinishReason.ERROR,
                    freeze_board(board),
                    f"{type(exc).__name__}: {exc}",
                )
            )


def main() -> None:
    run_cli(HeuristicSolver, "Run the Nonograms heuristic solver headlessly.")


if __name__ == "__main__":
    main()
