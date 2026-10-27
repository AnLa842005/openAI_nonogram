"""Check both solvers against official answers from puzzle-nonograms.com.

Each example keeps the site's raw ``task`` string and ``hashed_solution`` in
its metadata. The site computes that hash as md5(task + solution), where the
solution lists cells row by row as ``y`` (filled) or ``n`` (empty). A matching
hash means the solver found exactly the site's answer, not merely a board that
satisfies the clues.
"""

import hashlib
import unittest
from pathlib import Path

from nonogram_visualizer.dfs_solver import DFSSolver, SolveStatus
from nonogram_visualizer.heuristic_solver import HeuristicSolver
from nonogram_visualizer.models import BoardSnapshot, CellState, Puzzle

EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples" / "puzzle-nonograms"
# DFS needs seconds to minutes from 20x20 upwards; keep unit tests fast.
DFS_EXAMPLES = ("5x5", "10x10", "15x15")


def load_examples() -> dict[str, Puzzle]:
    return {path.stem: Puzzle.from_json_file(path) for path in EXAMPLES_DIR.glob("*.json")}


def official_hash(puzzle: Puzzle, board: BoardSnapshot) -> str:
    cells = "".join("y" if cell is CellState.FILLED else "n" for row in board for cell in row)
    return hashlib.md5((puzzle.metadata["task"] + cells).encode("ascii")).hexdigest()


class WebsiteExampleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.examples = load_examples()

    def test_every_size_is_present_and_matches_its_task(self) -> None:
        self.assertTrue(
            {"5x5", "10x10", "15x15", "20x20", "25x25", "30x30_special_weekly"}
            <= set(self.examples)
        )
        for name, puzzle in self.examples.items():
            with self.subTest(example=name):
                # The site's task lists columns first, then rows; "0" is empty.
                lines = [
                    ".".join(map(str, clues)) or "0"
                    for clues in (*puzzle.col_clues, *puzzle.row_clues)
                ]
                self.assertEqual("/".join(lines), puzzle.metadata["task"])

    def assert_official_solution(self, solver, names) -> None:
        for name in names:
            puzzle = self.examples[name]
            with self.subTest(solver=solver.name, example=name):
                result = solver.solve(puzzle)
                self.assertEqual(result.status, SolveStatus.SOLVED)
                self.assertEqual(
                    official_hash(puzzle, result.board),
                    puzzle.metadata["hashed_solution"],
                )

    def test_heuristic_finds_the_official_solution_for_every_example(self) -> None:
        self.assert_official_solution(HeuristicSolver(), sorted(self.examples))

    def test_dfs_finds_the_official_solution_for_small_examples(self) -> None:
        self.assert_official_solution(DFSSolver(), DFS_EXAMPLES)


if __name__ == "__main__":
    unittest.main()
