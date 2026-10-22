"""Built-in puzzles. Mock search data is kept separately in solvers.py."""

from .models import Puzzle

CROSS_5X5 = Puzzle(
    name="Cross 5x5",
    row_clues=((1,), (3,), (5,), (3,), (1,)),
    col_clues=((1,), (3,), (5,), (3,), (1,)),
)

SAMPLES: dict[str, Puzzle] = {CROSS_5X5.name: CROSS_5X5}
