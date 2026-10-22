import inspect
import threading
import unittest

from nonogram_visualizer.heuristic_solver import HeuristicSolver
from nonogram_visualizer.samples import CROSS_5X5


class SolverTemplateTests(unittest.TestCase):
    def test_templates_expose_generator_contract_without_fake_results(self) -> None:
        for solver, expected_name in ((HeuristicSolver(), "Heuristic"),):
            with self.subTest(solver=expected_name):
                self.assertEqual(solver.name, expected_name)
                stream = solver.steps(CROSS_5X5, threading.Event())
                self.assertTrue(inspect.isgenerator(stream))
                with self.assertRaisesRegex(NotImplementedError, "template"):
                    next(stream)


if __name__ == "__main__":
    unittest.main()
