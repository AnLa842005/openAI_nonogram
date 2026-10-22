import threading
import unittest

from nonogram_visualizer.models import Puzzle, SearchAction, SearchStep, unknown_board
from nonogram_visualizer.solvers import SolverWorker


class EndlessSolver:
    name = "Endless test solver"

    def steps(self, puzzle: Puzzle, cancel_event: threading.Event):
        board = unknown_board(puzzle)
        while not cancel_event.is_set():
            yield SearchStep(board, SearchAction.TRY, message="test")


class SolverWorkerTests(unittest.TestCase):
    def test_cancel_unblocks_worker_when_bounded_queue_is_full(self) -> None:
        puzzle = Puzzle("2x2", ((1,), (1,)), ((1,), (1,)))
        worker = SolverWorker(EndlessSolver(), puzzle, session_id=7, max_queue_size=1)
        worker.start()
        deadline = threading.Event()
        for _ in range(100):
            if worker.events.full():
                break
            deadline.wait(0.005)
        self.assertTrue(worker.events.full())
        worker.cancel()
        self.assertTrue(worker.wait(1.0))
        self.assertFalse(worker.is_alive)


if __name__ == "__main__":
    unittest.main()
