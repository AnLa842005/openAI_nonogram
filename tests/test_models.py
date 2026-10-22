import json
import tempfile
import unittest
from pathlib import Path

from nonogram_visualizer.models import (
    CellState,
    Puzzle,
    PuzzleValidationError,
    SearchAction,
    SearchStep,
)


class PuzzleValidationTests(unittest.TestCase):
    def test_valid_json_and_empty_clue(self) -> None:
        data = {
            "name": "Single empty row",
            "row_clues": [[], [1]],
            "col_clues": [[1]],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "puzzle.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            puzzle = Puzzle.from_json_file(path)
        self.assertEqual(puzzle.height, 2)
        self.assertEqual(puzzle.width, 1)
        self.assertEqual(puzzle.row_clues[0], ())

    def test_rejects_non_positive_or_boolean_clues(self) -> None:
        for invalid_value in (0, -1, True, 1.5, "1"):
            with (
                self.subTest(invalid_value=invalid_value),
                self.assertRaises(PuzzleValidationError),
            ):
                Puzzle("bad", ((invalid_value,),), ((1,),))

    def test_rejects_line_that_cannot_fit(self) -> None:
        with self.assertRaisesRegex(PuzzleValidationError, "Row 1"):
            Puzzle("too wide", ((2, 2), (), ()), ((1,), (1,), (1,)))

    def test_rejects_mismatched_black_cell_totals(self) -> None:
        with self.assertRaisesRegex(PuzzleValidationError, "does not equal"):
            Puzzle("mismatch", ((1,), ()), ((1,), (1,)))

    def test_rejects_malformed_json_without_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text('{"name": ', encoding="utf-8")
            with self.assertRaisesRegex(PuzzleValidationError, "line 1"):
                Puzzle.from_json_file(path)

    def test_export_import_preserves_clues_and_safe_metadata(self) -> None:
        puzzle = Puzzle(
            "Round trip",
            ((1,), ()),
            ((1,),),
            metadata={"seed": 42, "expected_density": 0.5},
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "round_trip.json"
            puzzle.to_json_file(path)
            exported = json.loads(path.read_text(encoding="utf-8"))
            loaded = Puzzle.from_json_file(path)
        self.assertEqual(loaded.row_clues, puzzle.row_clues)
        self.assertEqual(loaded.col_clues, puzzle.col_clues)
        self.assertEqual(loaded.metadata["seed"], 42)
        self.assertNotIn("source_board", exported)


class SnapshotTests(unittest.TestCase):
    def test_search_step_takes_independent_immutable_snapshot(self) -> None:
        mutable_board = [[-1, 0], [1, -1]]
        step = SearchStep(mutable_board, SearchAction.TRY)
        mutable_board[0][0] = 1
        self.assertEqual(step.board[0][0], CellState.UNKNOWN)
        self.assertIsInstance(step.board, tuple)
        self.assertIsInstance(step.board[0], tuple)


if __name__ == "__main__":
    unittest.main()
