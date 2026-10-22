import os
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication

from nonogram_visualizer.generator import generate_random_puzzle
from nonogram_visualizer.models import unknown_board
from nonogram_visualizer.samples import CROSS_5X5
from nonogram_visualizer.ui.board_widget import BoardSurface
from nonogram_visualizer.ui.control_panel import ControlPanel
from nonogram_visualizer.ui.main_window import MainWindow


class BoardCoordinateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_cell_mapping_remains_correct_after_zoom(self) -> None:
        surface = BoardSurface()
        surface.set_model(CROSS_5X5, unknown_board(CROSS_5X5))
        for zoom in (0.6, 1.0, 1.75, 2.0):
            surface.set_zoom(zoom)
            metrics = surface.metrics
            position = QPointF(
                metrics.grid_x + 3.5 * metrics.cell_size,
                metrics.grid_y + 2.5 * metrics.cell_size,
            )
            self.assertEqual(surface.cell_at_position(position), (2, 3))
            self.assertIsNone(
                surface.cell_at_position(QPointF(metrics.grid_x - 1, metrics.grid_y))
            )


class MainWindowSessionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_toolbar_actions_are_text_only(self) -> None:
        window = MainWindow()
        self.assertEqual(window.new_action.text(), "New Puzzle")
        self.assertEqual(window.open_action.text(), "Open")
        self.assertEqual(window.save_action.text(), "Save")
        self.assertTrue(window.new_action.icon().isNull())
        self.assertTrue(window.open_action.icon().isNull())
        self.assertTrue(window.save_action.icon().isNull())
        window.close()

    def test_play_panel_uses_direct_mouse_controls_without_tool_picker(self) -> None:
        window = MainWindow()
        self.assertFalse(hasattr(window.panel, "tool_buttons"))
        self.assertEqual(
            window.panel.play_message.text(),
            "Left-click to fill; right-click to mark X.",
        )
        window.close()

    def test_puzzle_replacement_invalidates_visual_session_and_keeps_play_separate(
        self,
    ) -> None:
        window = MainWindow()
        window.play_session.click(0, 2)
        play_snapshot = window.play_session.board
        window._change_mode("Visualize")
        self.assertEqual(window.visual_board, unknown_board(CROSS_5X5))
        window._run_visualizer()
        old_session = window.session_id
        generated = generate_random_puzzle(6, 7, 0.4, seed=77)
        window._replace_puzzle(generated.puzzle, demo_compatible=False)
        self.assertGreater(window.session_id, old_session)
        self.assertIsNone(window.worker)
        self.assertEqual(window.visual_board, unknown_board(generated.puzzle))
        self.assertEqual(window.panel.step_value.text(), "0")
        self.assertFalse(window.panel.run_button.isEnabled())
        self.assertNotEqual(play_snapshot, window.play_session.board)
        window.close()

    def test_window_can_close_while_worker_is_active(self) -> None:
        window = MainWindow()
        window._change_mode("Visualize")
        window._run_visualizer()
        self.assertIsNotNone(window.worker)
        window.close()
        self.assertTrue(all(not worker.is_alive for worker in window.retired_workers))

    def test_dfs_is_available_and_finishes_through_ui_worker(self) -> None:
        window = MainWindow()
        window._change_mode("Visualize")
        window.panel.solver_combo.setCurrentText(ControlPanel.SOLVER_DFS)
        self.assertTrue(window._visual_solver_available())
        self.assertTrue(window.panel.run_button.isEnabled())

        window._run_visualizer()
        deadline = time.monotonic() + 3.0
        while window.visual_state != "finished" and time.monotonic() < deadline:
            window.next_due = 0.0
            window._tick()
            self.app.processEvents()
            time.sleep(0.001)

        self.assertEqual(window.visual_state, "finished")
        self.assertEqual(window.panel.visual_status.text(), "Solved")
        self.assertEqual(window.panel.action_value.text(), "FINISH")
        window.close()


if __name__ == "__main__":
    unittest.main()
