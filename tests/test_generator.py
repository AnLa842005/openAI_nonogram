import unittest

from nonogram_visualizer.board_logic import check_board
from nonogram_visualizer.generator import clues_for_line, generate_random_puzzle
from nonogram_visualizer.models import CellState


class ClueGenerationTests(unittest.TestCase):
    def test_white_full_and_multiple_group_lines(self) -> None:
        self.assertEqual(clues_for_line([0, 0, 0, 0]), ())
        self.assertEqual(clues_for_line([1, 1, 1, 1]), (4,))
        self.assertEqual(clues_for_line([1, 1, 0, 1, 0, 1, 1]), (2, 1, 2))

    def test_random_generation_is_reproducible(self) -> None:
        first = generate_random_puzzle(10, 7, 0.42, seed=2026)
        second = generate_random_puzzle(10, 7, 0.42, seed=2026)
        self.assertEqual(first.source_board, second.source_board)
        self.assertEqual(first.puzzle.row_clues, second.puzzle.row_clues)
        self.assertEqual(first.puzzle.col_clues, second.puzzle.col_clues)
        self.assertEqual(first.seed, 2026)

    def test_generated_source_board_satisfies_generated_clues(self) -> None:
        generated = generate_random_puzzle(15, 12, 0.5, seed=99)
        self.assertTrue(check_board(generated.puzzle, generated.source_board).solved)
        self.assertTrue(
            all(
                cell in (CellState.EMPTY, CellState.FILLED)
                for row in generated.source_board
                for cell in row
            )
        )

    def test_blank_seed_returns_reusable_actual_seed(self) -> None:
        generated = generate_random_puzzle(5, 5, 0.5)
        recreated = generate_random_puzzle(5, 5, 0.5, seed=generated.seed)
        self.assertEqual(recreated.source_board, generated.source_board)


if __name__ == "__main__":
    unittest.main()
