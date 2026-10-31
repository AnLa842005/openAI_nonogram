"""Built-in puzzles."""

from .models import Puzzle

CROSS_5X5 = Puzzle(
    name="Cross 5x5",
    row_clues=((1,), (3,), (5,), (3,), (1,)),
    col_clues=((1,), (3,), (5,), (3,), (1,)),
)
