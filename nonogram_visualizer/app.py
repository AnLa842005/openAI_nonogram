"""Application entry point kept stable for ``python -m nonogram_visualizer``."""

from .ui.main_window import MainWindow, main

__all__ = ["MainWindow", "main"]


if __name__ == "__main__":
    main()
