# Nonograms Studio

A Python 3 desktop application built with **PySide6 Widgets** for generating Nonograms puzzles, playing them manually, and visualizing solver search events.

The UI uses `QMainWindow`, `QPainter`, `QScrollArea`, Qt stylesheets, and `QTimer`. It does not use QML, a webview, or JavaScript.

The project includes a real deterministic DFS solver. `MockSolver` remains a
separate simulated demo for the built-in `Cross 5x5` sample. BFS and the
heuristic solver are not implemented.

## Install and run on Windows

Python 3.10 or newer is required.

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m nonogram_visualizer.app
```

Run all tests:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
python -m unittest discover -s tests -v
Remove-Item Env:QT_QPA_PLATFORM
```

`QT_QPA_PLATFORM=offscreen` is only for automated tests or environments without a display. Do not set it for normal Windows use.

## Interface

- The top toolbar contains puzzle information, New Puzzle, Open, Save, and the Controls panel toggle.
- The board occupies the main area of the window.
- The right panel can be closed, moved, or detached. Its contents scroll when vertical space is limited.
- The status bar provides messages, 50–200% zoom, and Fit to View.
- The light gray and white theme uses indigo accents, Segoe UI on Windows, and the system font elsewhere.
- Buttons provide hover, pressed, disabled states, and tooltips.

`BoardWidget` draws the clues and cells on one `QPainter` surface instead of creating a widget per cell. Qt handles device scaling, while pointer mapping uses local surface coordinates so input remains accurate after zooming and scrolling.

## Play mode

- Left-click: `UNKNOWN/EMPTY → FILLED`, `FILLED → UNKNOWN`.
- Right-click: `UNKNOWN/FILLED → EMPTY`, `EMPTY → UNKNOWN`.
- A drag stroke uses one target state. Revisiting a cell does not toggle it again, and the entire stroke creates one Undo entry.
- Undo/Redo is available through buttons or `Ctrl+Z`/`Ctrl+Y`. Shortcuts do not intercept input while a line edit, spin box, combo box, or text edit has focus.
- **Check** recalculates clues from the current board. `UNKNOWN` counts as white, so players do not have to mark every empty cell with X.
- Any board satisfying the clues is accepted, even if it differs from the source board used for generation.
- Mismatched rows and columns are highlighted without claiming that a specific cell is wrong.
- Clear Board asks for confirmation, then clears the board, timer, and Undo/Redo history.

Play and Visualize boards are stored separately. Switching modes preserves Play progress, and the Play timer pauses while Visualize mode is active.

## Random puzzle generation

The **New Puzzle** menu provides the random-puzzle dialog and the `Cross 5x5` sample:

- 5×5, 10×10, and 15×15 presets;
- custom dimensions from 2 to 30 in each direction;
- expected filled-cell density, default 50%; this is not a difficulty setting;
- an optional integer seed.

The generator uses `random.Random(seed)` to create a source board, derives its clues, and initializes the playable board with `UNKNOWN`. The same seed, dimensions, and density produce the same puzzle. If the seed is blank, the generated 64-bit seed appears in the toolbar.

The puzzle has at least the source board as a solution, but the generator does not verify uniqueness, count solutions, or estimate difficulty. The main window stores only a `Puzzle` containing clues and metadata. It does not pass the source board to a solver or use it when checking the player board.

A completely white row or column is stored as `[]` and displayed as `0`.

## JSON format

The basic schema remains compatible with the original format:

```json
{
  "name": "Cross 5x5",
  "row_clues": [[1], [3], [5], [3], [1]],
  "col_clues": [[1], [3], [5], [3], [1]]
}
```

Generated puzzles may include backward-compatible metadata:

```json
{
  "name": "Random 10x10",
  "row_clues": [[2], [], [1, 3]],
  "col_clues": [[1], [2], []],
  "metadata": {
    "generator": "random-board-v1",
    "seed": 12345,
    "expected_density": 0.5
  }
}
```

Exported files do not contain the source solution. Validation checks data types, positive clue values, the minimum line length required by each clue, and equal filled-cell totals across row and column clues. These checks do **not** guarantee that an imported puzzle has a solution.

## Visualize mode and worker behavior

- Visualize always starts from an `UNKNOWN` board; continuing from the Play board is not supported.
- The demo is enabled only for the built-in `Cross 5x5` sample. It cannot run on generated or imported puzzles.
- DFS is available for every valid puzzle. Heuristic remains disabled.
- Run/Pause, Next Step, and Reset are enabled according to the current session state.
- Pause stops event playback; each Next Step action consumes exactly one event.
- Animation uses `QTimer` on the Qt main thread. The application does not call `time.sleep()` or run a `processEvents()` loop.
- The solver runs on a Python worker thread and sends events through `queue.Queue(maxsize=64)` for backpressure.
- Reset, mode changes, puzzle changes, and application shutdown cooperatively cancel the worker. A session ID rejects late events from older runs.
- A worker blocked by a full queue checks cancellation with a timeout and exits without `QThread.terminate()`.
- The UI never treats animation time as `solver_time_ms`. Missing solver statistics display `—`.

## Solver contract

Shared models are defined in `nonogram_visualizer/models.py`:

- `Puzzle`: name, row clues, column clues, and optional JSON metadata.
- `CellState`: `UNKNOWN = -1`, `EMPTY = 0`, `FILLED = 1`.
- `SearchStep`: immutable board snapshot, action, optional focus, message, statistics, and optional finish reason.
- `SearchStats`: nodes expanded/generated, backtracks, maximum depth, solver time, and peak memory; every field may be `None`.
- `SearchFocus`: row, column, cell, frontier, or state.

Minimum actions: `START`, `TRY`, `ACCEPT`, `REJECT`, `BACKTRACK`, `SOLUTION`, and `FINISH`.

- Only `SOLUTION` announces that a solution was found.
- `FINISH` distinguishes `SOLVED`, `NO_SOLUTION`, `CANCELLED`,
  `LIMIT_REACHED`, and `ERROR`. The original `COMPLETED_AFTER_SOLUTION` and
  `EXHAUSTED` reasons remain available for legacy adapters such as the demo.
- A solver must check `cancel_event` frequently and must never call QWidget or QPainter APIs from its worker thread.
- `SearchStep` freezes the board at the event boundary, preventing later mutation from changing older snapshots.

See [`examples/heuristic_adapter_example.py`](examples/heuristic_adapter_example.py) for a minimal heuristic adapter.

The solver implementations are available at:

- [`nonogram_visualizer/dfs_solver.py`](nonogram_visualizer/dfs_solver.py) — implemented DFS and headless benchmark
- [`nonogram_visualizer/heuristic_solver.py`](nonogram_visualizer/heuristic_solver.py)

The heuristic template deliberately raises `NotImplementedError` and remains
disabled in the UI.

## DFS model and traversal

DFS starts from a completely `UNKNOWN` board and does not read cells entered
in Play mode or any source board used by the random generator. It generates
all valid row and column patterns directly by placing clue groups from left to
right; it never enumerates all `2^length` bit strings. An empty clue has one
all-white pattern.

The search assigns complete rows in fixed top-to-bottom order. Row patterns
are tried in deterministic leftmost-group-first order. After assigning row
`r`, each column candidate set is filtered against its prefix through `r`.
The branch is rejected as soon as one column has no possible completion.
Accepted branches recurse to the next row and restore the row to `UNKNOWN`
when they fail. The first complete solution is checked again by an independent,
strict 0/1 clue validator before `SOLUTION` is emitted.

This is **DFS with constraint checking and pruning**. Pattern counts and the
search tree can still grow very quickly, so it does not claim consistently low
time or memory usage. Pattern storage is scoped to one solve; there is no
cross-run warm cache. An optional pattern limit produces `LIMIT_REACHED`, never
a false `NO_SOLUTION` result.

To use it in the UI, switch to **Visualize**, select **DFS**, then use Run,
Pause, Next Step, and Reset. Event snapshots are immutable and flow through the
existing bounded worker queue; the UI does not retain the complete search
history.

## Headless DFS and benchmark

The headless path uses the same DFS core with tracing disabled, so it does not
construct a board snapshot or message for every search step:

```powershell
python -m nonogram_visualizer.dfs_solver examples/cross_5x5.json
python -m nonogram_visualizer.dfs_solver examples/cross_5x5.json --memory
```

`solver_time_ms` uses `perf_counter` and includes pattern generation plus DFS,
but excludes JSON loading, UI work, and animation. `--memory` performs a
separate cold run under `tracemalloc`; the reported peak is Python allocations,
not whole-process RSS. Without `--memory`, unavailable peak memory is shown as
`—`. Tracing is disabled in both benchmark runs.

## Statistics conventions

| Field | Meaning and unit |
| --- | --- |
| `nodes_expanded` | Valid incomplete states whose next-row patterns DFS begins to visit, including the root. |
| `nodes_generated` | Every attempted row-pattern assignment, including immediately rejected patterns; the root is not generated. |
| `backtracks` | Accepted choices abandoned because their child branch failed; immediate `REJECT` patterns are not counted. |
| `max_depth` | Greatest number of simultaneously assigned rows reached. |
| `solver_time_ms` | Solver computation time in milliseconds, excluding animation, Pause time, queue waiting, and UI work. |
| `peak_memory_bytes` | Peak Python allocations in bytes from a separate headless `tracemalloc` run. |

Use `None` for any unavailable statistic. The UI displays it as `—` and never invents a value.

A `BACKTRACK` event is also emitted after restoring an immediately rejected
row so the animation shows the actual board state. Consequently, the number of
displayed `BACKTRACK` events can exceed the `backtracks` counter above.

## Project structure

```text
nonogram_visualizer/
  app.py                 # Stable entry point
  models.py              # Shared puzzle and search-event contract
  generator.py           # Random generation and clue calculation
  board_logic.py         # Play operations, history, and validation
  samples.py             # Built-in puzzles
  solvers.py             # Solver protocol, mock stream, and worker adapter
  dfs_solver.py          # DFS core, event adapter, and headless benchmark
  heuristic_solver.py    # Heuristic implementation template
  ui/
    board_widget.py      # Scalable QPainter board
    control_panel.py     # Play and Visualize controls
    dialogs.py           # Random-puzzle dialog
    main_window.py       # QMainWindow and session coordination
    theme.py             # Stylesheet and generated icons
examples/
  cross_5x5.json
  heuristic_adapter_example.py
tests/
```
