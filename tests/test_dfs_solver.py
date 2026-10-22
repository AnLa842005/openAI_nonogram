import itertools
import random
import threading
import unittest

from nonogram_visualizer.dfs_solver import (
    DFSSolver,
    SolveStatus,
    generate_patterns,
    validate_solution,
)
from nonogram_visualizer.generator import clues_for_board, clues_for_line
from nonogram_visualizer.models import (
    CellState,
    FinishReason,
    Puzzle,
    SearchAction,
)
from nonogram_visualizer.samples import CROSS_5X5


class PatternGenerationTests(unittest.TestCase):
    def test_examples_and_edge_cases(self) -> None:
        self.assertEqual(
            generate_patterns(4, (1,)),
            ((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1)),
        )
        self.assertEqual(generate_patterns(4, (2, 1)), ((1, 1, 0, 1),))
        self.assertEqual(generate_patterns(4, ()), ((0, 0, 0, 0),))
        self.assertEqual(generate_patterns(4, (4,)), ((1, 1, 1, 1),))
        self.assertEqual(generate_patterns(3, (2, 2)), ())

    def test_matches_independent_brute_force_for_small_lines(self) -> None:
        for length in range(1, 7):
            all_clues = {clues_for_line(bits) for bits in itertools.product((0, 1), repeat=length)}
            for clues in all_clues:
                with self.subTest(length=length, clues=clues):
                    expected = tuple(
                        bits
                        for bits in itertools.product((0, 1), repeat=length)
                        if clues_for_line(bits) == clues
                    )
                    actual = generate_patterns(length, clues)
                    self.assertEqual(set(actual), set(expected))
                    self.assertEqual(len(actual), len(set(actual)))


class DFSSolverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.backtracking = Puzzle(
            "Backtracking 4x4",
            ((1,), (1,), (2, 1), (1,)),
            ((2,), (1,), (), (3,)),
        )

    def test_required_backtracking_puzzle_and_event_order(self) -> None:
        steps = list(DFSSolver().steps(self.backtracking, threading.Event()))
        self.assertEqual(steps[0].action, SearchAction.START)
        first_try = next(step for step in steps if step.action is SearchAction.TRY)
        self.assertEqual(first_try.board[0], tuple(map(CellState, (1, 0, 0, 0))))
        self.assertIn(SearchAction.REJECT, (step.action for step in steps))
        self.assertIn(SearchAction.BACKTRACK, (step.action for step in steps))
        solution = next(step.board for step in steps if step.action is SearchAction.SOLUTION)
        self.assertEqual(
            solution,
            tuple(
                tuple(map(CellState, row))
                for row in ((0, 0, 0, 1), (0, 0, 0, 1), (1, 1, 0, 1), (1, 0, 0, 0))
            ),
        )
        self.assertTrue(validate_solution(self.backtracking, solution))
        self.assertEqual(steps[-1].action, SearchAction.FINISH)
        self.assertEqual(steps[-1].finish_reason, FinishReason.SOLVED)
        self.assertGreater(steps[-1].stats.backtracks, 0)

    def test_cross_empty_rectangular_and_ambiguous_puzzles(self) -> None:
        boards = (
            CROSS_5X5,
            Puzzle("Empty lines", ((), (2,), ()), ((1,), (1,), ())),
            Puzzle("Rectangular", ((2,), (1,), (1,)), ((1,), (2,), (1,), ())),
            Puzzle("Ambiguous", ((1,), (1,)), ((1,), (1,))),
        )
        for puzzle in boards:
            with self.subTest(puzzle=puzzle.name):
                result = DFSSolver().solve(puzzle)
                self.assertEqual(result.status, SolveStatus.SOLVED)
                self.assertTrue(validate_solution(puzzle, result.board))

    def test_exhaustive_no_solution_is_distinct(self) -> None:
        puzzle = Puzzle("No solution", ((2,), ()), ((2,), ()))
        result = DFSSolver().solve(puzzle)
        self.assertEqual(result.status, SolveStatus.NO_SOLUTION)
        steps = list(DFSSolver().steps(puzzle, threading.Event()))
        self.assertNotIn(SearchAction.SOLUTION, (step.action for step in steps))
        self.assertEqual(steps[-1].finish_reason, FinishReason.NO_SOLUTION)
        self.assertTrue(
            all(cell is CellState.UNKNOWN for row in result.board for cell in row)
        )

    def test_fixed_seed_generated_puzzles_are_validated_by_clues(self) -> None:
        rng = random.Random(261)
        for index in range(12):
            height = rng.randint(2, 6)
            width = rng.randint(2, 7)
            source = tuple(
                tuple(rng.randint(0, 1) for _ in range(width))
                for _ in range(height)
            )
            rows, cols = clues_for_board(source)
            puzzle = Puzzle(f"Random {index}", rows, cols)
            result = DFSSolver().solve(puzzle)
            self.assertEqual(result.status, SolveStatus.SOLVED)
            self.assertTrue(validate_solution(puzzle, result.board))

    def test_cancel_limit_snapshots_and_trace_counters(self) -> None:
        cancelled = threading.Event()
        stream = DFSSolver().steps(CROSS_5X5, cancelled)
        start = next(stream)
        cancelled.set()
        remaining = list(stream)
        self.assertEqual(remaining[-1].finish_reason, FinishReason.CANCELLED)
        self.assertTrue(all(cell is CellState.UNKNOWN for row in start.board for cell in row))

        limited = DFSSolver(pattern_limit=1).solve(CROSS_5X5)
        self.assertEqual(limited.status, SolveStatus.LIMIT_REACHED)

        traced = list(DFSSolver().steps(self.backtracking, threading.Event()))[-1].stats
        headless = DFSSolver().solve(self.backtracking).stats
        self.assertEqual(
            (
                traced.nodes_generated,
                traced.nodes_expanded,
                traced.backtracks,
                traced.max_depth,
            ),
            (
                headless.nodes_generated,
                headless.nodes_expanded,
                headless.backtracks,
                headless.max_depth,
            ),
        )


if __name__ == "__main__":
    unittest.main()
