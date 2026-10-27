import random
import threading
import unittest

from nonogram_visualizer.dfs_solver import SolveStatus, validate_solution
from nonogram_visualizer.generator import clues_for_board
from nonogram_visualizer.heuristic_solver import HeuristicSolver, pattern_to_mask
from nonogram_visualizer.models import (
    CellState,
    FinishReason,
    Puzzle,
    SearchAction,
)
from nonogram_visualizer.samples import CROSS_5X5


def random_puzzles(seed: int, count: int) -> list[Puzzle]:
    rng = random.Random(seed)
    puzzles = []
    for index in range(count):
        height = rng.randint(4, 9)
        width = rng.randint(4, 9)
        source = tuple(
            tuple(rng.randint(0, 1) for _ in range(width)) for _ in range(height)
        )
        puzzles.append(Puzzle(f"Random {index}", *clues_for_board(source)))
    return puzzles


class PatternMaskTests(unittest.TestCase):
    def test_bit_i_is_cell_i(self) -> None:
        self.assertEqual(pattern_to_mask((1, 0, 0, 0)), 0b0001)
        self.assertEqual(pattern_to_mask((0, 1, 1, 0)), 0b0110)
        self.assertEqual(pattern_to_mask((0, 0, 0)), 0)


class HeuristicSolverTests(unittest.TestCase):
    def test_cross_is_solved_by_propagation_alone(self) -> None:
        steps = list(HeuristicSolver().steps(CROSS_5X5, threading.Event()))
        self.assertEqual(steps[0].action, SearchAction.START)
        self.assertNotIn(SearchAction.TRY, (step.action for step in steps))
        self.assertIn(SearchAction.ACCEPT, (step.action for step in steps))
        self.assertEqual(steps[-2].action, SearchAction.SOLUTION)
        self.assertTrue(validate_solution(CROSS_5X5, steps[-2].board))
        self.assertEqual(steps[-1].finish_reason, FinishReason.SOLVED)
        self.assertEqual(steps[-1].stats.nodes_generated, 0)

    def test_ambiguous_puzzle_requires_a_guess(self) -> None:
        puzzle = Puzzle("Ambiguous", ((1,), (1,)), ((1,), (1,)))
        steps = list(HeuristicSolver().steps(puzzle, threading.Event()))
        first_try = next(step for step in steps if step.action is SearchAction.TRY)
        self.assertEqual(first_try.focus.kind, "cell")
        self.assertEqual(steps[-1].finish_reason, FinishReason.SOLVED)
        self.assertEqual(steps[-1].stats.nodes_expanded, 1)

    def test_edge_case_and_random_puzzles_are_validated_by_clues(self) -> None:
        boards = [
            CROSS_5X5,
            Puzzle("Empty lines", ((), (2,), ()), ((1,), (1,), ())),
            Puzzle("Rectangular", ((2,), (1,), (1,)), ((1,), (2,), (1,), ())),
            *random_puzzles(261, 40),
        ]
        for puzzle in boards:
            with self.subTest(puzzle=puzzle.name):
                result = HeuristicSolver().solve(puzzle)
                self.assertEqual(result.status, SolveStatus.SOLVED)
                self.assertTrue(validate_solution(puzzle, result.board))

    def test_backtrack_restores_the_board_from_before_the_guess(self) -> None:
        backtracks_seen = 0
        for puzzle in random_puzzles(261, 40):
            steps = list(HeuristicSolver().steps(puzzle, threading.Event()))
            before_guess = []
            for previous, step in zip(steps, steps[1:]):
                if step.action is SearchAction.TRY:
                    before_guess.append(previous.board)
                elif step.action is SearchAction.BACKTRACK:
                    backtracks_seen += 1
                    self.assertEqual(step.board, before_guess.pop())
        self.assertGreater(backtracks_seen, 0)

    def test_contradictory_clues_are_no_solution(self) -> None:
        puzzle = Puzzle("No solution", ((2,), ()), ((2,), ()))
        result = HeuristicSolver().solve(puzzle)
        self.assertEqual(result.status, SolveStatus.NO_SOLUTION)
        self.assertTrue(
            all(cell is CellState.UNKNOWN for row in result.board for cell in row)
        )
        steps = list(HeuristicSolver().steps(puzzle, threading.Event()))
        self.assertNotIn(SearchAction.SOLUTION, (step.action for step in steps))
        self.assertEqual(steps[-1].finish_reason, FinishReason.NO_SOLUTION)

    def test_cancel_limit_and_trace_counters(self) -> None:
        cancelled = threading.Event()
        stream = HeuristicSolver().steps(CROSS_5X5, cancelled)
        next(stream)
        cancelled.set()
        self.assertEqual(list(stream)[-1].finish_reason, FinishReason.CANCELLED)

        limited = HeuristicSolver(pattern_limit=1).solve(CROSS_5X5)
        self.assertEqual(limited.status, SolveStatus.LIMIT_REACHED)

        for puzzle in random_puzzles(7, 10):
            with self.subTest(puzzle=puzzle.name):
                traced = list(HeuristicSolver().steps(puzzle, threading.Event()))[-1].stats
                headless = HeuristicSolver().solve(puzzle).stats
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
