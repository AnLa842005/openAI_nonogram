import threading
import unittest

from nonogram_visualizer.models import CellState, FinishReason, SearchAction
from nonogram_visualizer.samples import CROSS_5X5
from nonogram_visualizer.solvers import MockSolver


def clues_for_line(line: tuple[CellState, ...]) -> tuple[int, ...]:
    groups: list[int] = []
    run = 0
    for cell in line:
        if cell is CellState.FILLED:
            run += 1
        elif run:
            groups.append(run)
            run = 0
    if run:
        groups.append(run)
    return tuple(groups)


class MockSolverTests(unittest.TestCase):
    def test_demo_contains_branching_and_ends_after_a_valid_solution(self) -> None:
        steps = list(MockSolver().steps(CROSS_5X5, threading.Event()))
        actions = [step.action for step in steps]
        self.assertIn(SearchAction.TRY, actions)
        self.assertIn(SearchAction.REJECT, actions)
        self.assertIn(SearchAction.BACKTRACK, actions)
        self.assertEqual(actions.count(SearchAction.SOLUTION), 1)
        self.assertEqual(steps[-1].action, SearchAction.FINISH)
        self.assertEqual(steps[-1].finish_reason, FinishReason.COMPLETED_AFTER_SOLUTION)

        solution = next(
            step.board for step in steps if step.action is SearchAction.SOLUTION
        )
        self.assertTrue(
            all(cell is not CellState.UNKNOWN for row in solution for cell in row)
        )
        self.assertEqual(
            tuple(clues_for_line(row) for row in solution),
            CROSS_5X5.row_clues,
        )
        columns = tuple(
            tuple(solution[r][c] for r in range(CROSS_5X5.height))
            for c in range(CROSS_5X5.width)
        )
        self.assertEqual(
            tuple(clues_for_line(column) for column in columns),
            CROSS_5X5.col_clues,
        )

    def test_every_demo_step_has_valid_dimensions_and_independent_board(self) -> None:
        steps = list(MockSolver().steps(CROSS_5X5, threading.Event()))
        for step in steps:
            step.validate_dimensions(CROSS_5X5)
        self.assertIsNot(steps[0].board, steps[1].board)


if __name__ == "__main__":
    unittest.main()
