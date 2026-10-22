import unittest

from nonogram_visualizer.board_logic import PlaySession, PlayTool, check_board
from nonogram_visualizer.models import CellState, Puzzle


class BoardCheckingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ambiguous = Puzzle(
            "Ambiguous 2x2",
            ((1,), (1,)),
            ((1,), (1,)),
        )

    def test_accepts_solution_different_from_possible_source(self) -> None:
        source_diagonal = ((1, 0), (0, 1))
        alternate_diagonal = ((0, 1), (1, 0))
        self.assertTrue(check_board(self.ambiguous, source_diagonal).solved)
        self.assertTrue(check_board(self.ambiguous, alternate_diagonal).solved)

    def test_unknown_is_treated_as_white(self) -> None:
        board = (
            (CellState.FILLED, CellState.UNKNOWN),
            (CellState.UNKNOWN, CellState.FILLED),
        )
        self.assertTrue(check_board(self.ambiguous, board).solved)

    def test_reports_mismatched_rows_and_columns(self) -> None:
        result = check_board(self.ambiguous, ((1, 1), (-1, -1)))
        self.assertFalse(result.solved)
        self.assertEqual(result.mismatched_rows, (0, 1))
        self.assertEqual(result.mismatched_cols, ())


class PlayHistoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.session = PlaySession(Puzzle("2x2", ((1,), (1,)), ((1,), (1,))))

    def test_click_undo_redo(self) -> None:
        self.assertTrue(self.session.click(0, 0, button=1, tool=PlayTool.FILL))
        self.assertEqual(self.session.board[0][0], CellState.FILLED)
        self.assertTrue(self.session.undo())
        self.assertEqual(self.session.board[0][0], CellState.UNKNOWN)
        self.assertTrue(self.session.redo())
        self.assertEqual(self.session.board[0][0], CellState.FILLED)

    def test_drag_is_one_operation_and_does_not_toggle_revisited_cell(self) -> None:
        self.session.begin_stroke(0, 0, button=1, tool=PlayTool.FILL)
        self.session.paint_cell(0, 1)
        self.session.paint_cell(0, 0)
        self.session.end_stroke()
        self.assertEqual(self.session.board[0], (CellState.FILLED, CellState.FILLED))
        self.assertTrue(self.session.undo())
        self.assertEqual(self.session.board[0], (CellState.UNKNOWN, CellState.UNKNOWN))
        self.assertFalse(self.session.can_undo)
        self.assertTrue(self.session.redo())
        self.assertEqual(self.session.board[0], (CellState.FILLED, CellState.FILLED))

    def test_right_click_toggles_empty(self) -> None:
        self.session.click(1, 1, button=3)
        self.assertEqual(self.session.board[1][1], CellState.EMPTY)
        self.session.click(1, 1, button=3)
        self.assertEqual(self.session.board[1][1], CellState.UNKNOWN)

    def test_mark_x_and_erase_tools(self) -> None:
        self.session.click(0, 1, tool=PlayTool.MARK_X)
        self.assertEqual(self.session.board[0][1], CellState.EMPTY)
        self.session.click(0, 1, tool=PlayTool.MARK_X)
        self.assertEqual(self.session.board[0][1], CellState.UNKNOWN)
        self.session.click(0, 1, tool=PlayTool.FILL)
        self.session.click(0, 1, tool=PlayTool.ERASE)
        self.assertEqual(self.session.board[0][1], CellState.UNKNOWN)


if __name__ == "__main__":
    unittest.main()
