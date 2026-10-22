"""Zoomable QPainter-based Nonograms board in a QScrollArea."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QMouseEvent, QPainter, QPen, QWheelEvent
from PySide6.QtWidgets import QScrollArea, QWidget

from ..models import BoardSnapshot, CellState, Puzzle, SearchFocus


@dataclass(frozen=True, slots=True)
class BoardMetrics:
    cell_size: int
    clue_slot: int
    grid_x: int
    grid_y: int
    grid_width: int
    grid_height: int
    total_width: int
    total_height: int


class BoardSurface(QWidget):
    stroke_started = Signal(int, int, int)
    stroke_moved = Signal(int, int)
    stroke_ended = Signal()

    BASE_CELL_SIZE = 32
    PADDING = 20

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMouseTracking(True)
        self.puzzle: Puzzle | None = None
        self.board: BoardSnapshot = ()
        self.focus: SearchFocus | None = None
        self.mismatched_rows: set[int] = set()
        self.mismatched_cols: set[int] = set()
        self.hover_cell: tuple[int, int] | None = None
        self.zoom = 1.0
        self.editable = False
        self._active_button: int | None = None
        self.metrics = BoardMetrics(32, 20, 40, 40, 0, 0, 200, 160)
        self.setMinimumSize(200, 160)

    def set_model(
        self,
        puzzle: Puzzle,
        board: BoardSnapshot,
        focus: SearchFocus | None = None,
        mismatched_rows: tuple[int, ...] = (),
        mismatched_cols: tuple[int, ...] = (),
    ) -> None:
        self.puzzle = puzzle
        self.board = board
        self.focus = focus
        self.mismatched_rows = set(mismatched_rows)
        self.mismatched_cols = set(mismatched_cols)
        self._recalculate_size()
        self.update()

    def set_zoom(self, zoom: float) -> None:
        self.zoom = min(2.0, max(0.5, float(zoom)))
        self._recalculate_size()
        self.update()

    def set_editable(self, editable: bool) -> None:
        self.editable = editable
        self.setCursor(
            Qt.CursorShape.CrossCursor if editable else Qt.CursorShape.ArrowCursor
        )
        if not editable and self._active_button is not None:
            self._active_button = None
            self.stroke_ended.emit()

    def cell_at_position(self, position: QPointF) -> tuple[int, int] | None:
        if self.puzzle is None:
            return None
        metrics = self.metrics
        col = int((position.x() - metrics.grid_x) // metrics.cell_size)
        row = int((position.y() - metrics.grid_y) // metrics.cell_size)
        if 0 <= row < self.puzzle.height and 0 <= col < self.puzzle.width:
            return row, col
        return None

    def _recalculate_size(self) -> None:
        if self.puzzle is None:
            return
        cell = max(18, round(self.BASE_CELL_SIZE * self.zoom))
        clue_slot = max(16, round(20 * self.zoom))
        max_row_groups = max(1, max(len(line) for line in self.puzzle.row_clues))
        max_col_groups = max(1, max(len(line) for line in self.puzzle.col_clues))
        left = max_row_groups * clue_slot + 14
        top = max_col_groups * clue_slot + 14
        grid_width = self.puzzle.width * cell
        grid_height = self.puzzle.height * cell
        total_width = self.PADDING * 2 + left + grid_width
        total_height = self.PADDING * 2 + top + grid_height
        self.metrics = BoardMetrics(
            cell,
            clue_slot,
            self.PADDING + left,
            self.PADDING + top,
            grid_width,
            grid_height,
            total_width,
            total_height,
        )
        self.setFixedSize(total_width, total_height)
        self.updateGeometry()

    def sizeHint(self) -> QSize:
        return QSize(self.metrics.total_width, self.metrics.total_height)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#F3F5F8"))
        if self.puzzle is None:
            return
        puzzle = self.puzzle
        m = self.metrics
        painter.fillRect(
            QRectF(self.PADDING, m.grid_y, m.grid_x - self.PADDING, m.grid_height),
            QColor("#E8ECF1"),
        )
        painter.fillRect(
            QRectF(m.grid_x, self.PADDING, m.grid_width, m.grid_y - self.PADDING),
            QColor("#E8ECF1"),
        )

        font = QFont(self.font())
        font.setPointSize(max(7, round(9 * self.zoom)))
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        for row, clues in enumerate(puzzle.row_clues):
            color = QColor("#C24141" if row in self.mismatched_rows else "#263442")
            painter.setPen(color)
            for reverse_index, clue in enumerate(reversed(clues or (0,))):
                right = m.grid_x - 10 - reverse_index * m.clue_slot
                rect = QRectF(
                    right - m.clue_slot,
                    m.grid_y + row * m.cell_size,
                    m.clue_slot,
                    m.cell_size,
                )
                painter.drawText(
                    rect,
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                    str(clue),
                )
        for col, clues in enumerate(puzzle.col_clues):
            color = QColor("#C24141" if col in self.mismatched_cols else "#263442")
            painter.setPen(color)
            for reverse_index, clue in enumerate(reversed(clues or (0,))):
                bottom = m.grid_y - 8 - reverse_index * m.clue_slot
                rect = QRectF(
                    m.grid_x + col * m.cell_size,
                    bottom - m.clue_slot,
                    m.cell_size,
                    m.clue_slot,
                )
                painter.drawText(
                    rect,
                    Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom,
                    str(clue),
                )

        for row, board_row in enumerate(self.board):
            for col, state in enumerate(board_row):
                rect = QRectF(
                    m.grid_x + col * m.cell_size,
                    m.grid_y + row * m.cell_size,
                    m.cell_size,
                    m.cell_size,
                )
                fill = QColor("#FFFFFF" if state is CellState.EMPTY else "#F8FAFC")
                if state is CellState.FILLED:
                    fill = QColor("#1F2937")
                painter.fillRect(rect, fill)
                if state is CellState.EMPTY:
                    pad = max(5, round(m.cell_size * 0.28))
                    painter.setPen(QPen(QColor("#748292"), max(1.4, 1.8 * self.zoom)))
                    painter.drawLine(
                        rect.topLeft() + QPointF(pad, pad),
                        rect.bottomRight() - QPointF(pad, pad),
                    )
                    painter.drawLine(
                        rect.topRight() + QPointF(-pad, pad),
                        rect.bottomLeft() + QPointF(pad, -pad),
                    )

        if self.hover_cell is not None:
            row, col = self.hover_cell
            painter.fillRect(
                QRectF(
                    m.grid_x, m.grid_y + row * m.cell_size, m.grid_width, m.cell_size
                ),
                QColor(79, 70, 229, 18),
            )
            painter.fillRect(
                QRectF(
                    m.grid_x + col * m.cell_size, m.grid_y, m.cell_size, m.grid_height
                ),
                QColor(79, 70, 229, 18),
            )

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        for col in range(puzzle.width + 1):
            thick = col % 5 == 0
            painter.setPen(
                QPen(
                    QColor("#334155" if thick else "#94A3B8"),
                    max(1, round((2.5 if thick else 1) * self.zoom)),
                )
            )
            x = m.grid_x + col * m.cell_size
            painter.drawLine(x, m.grid_y, x, m.grid_y + m.grid_height)
        for row in range(puzzle.height + 1):
            thick = row % 5 == 0
            painter.setPen(
                QPen(
                    QColor("#334155" if thick else "#94A3B8"),
                    max(1, round((2.5 if thick else 1) * self.zoom)),
                )
            )
            y = m.grid_y + row * m.cell_size
            painter.drawLine(m.grid_x, y, m.grid_x + m.grid_width, y)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        mismatch_pen = QPen(QColor("#DC4C4C"), max(2, round(2.5 * self.zoom)))
        painter.setPen(mismatch_pen)
        for row in self.mismatched_rows:
            painter.drawRect(
                QRectF(
                    m.grid_x, m.grid_y + row * m.cell_size, m.grid_width, m.cell_size
                )
            )
        for col in self.mismatched_cols:
            painter.drawRect(
                QRectF(
                    m.grid_x + col * m.cell_size, m.grid_y, m.cell_size, m.grid_height
                )
            )
        self._draw_focus(painter)

    def _draw_focus(self, painter: QPainter) -> None:
        if self.focus is None:
            return
        m = self.metrics
        painter.setPen(QPen(QColor("#F59E0B"), max(3, round(3.5 * self.zoom))))
        if self.focus.kind == "row" and self.focus.row is not None:
            painter.drawRect(
                QRectF(
                    m.grid_x,
                    m.grid_y + self.focus.row * m.cell_size,
                    m.grid_width,
                    m.cell_size,
                )
            )
        elif self.focus.kind == "column" and self.focus.col is not None:
            painter.drawRect(
                QRectF(
                    m.grid_x + self.focus.col * m.cell_size,
                    m.grid_y,
                    m.cell_size,
                    m.grid_height,
                )
            )
        elif self.focus.row is not None and self.focus.col is not None:
            painter.drawRect(
                QRectF(
                    m.grid_x + self.focus.col * m.cell_size,
                    m.grid_y + self.focus.row * m.cell_size,
                    m.cell_size,
                    m.cell_size,
                )
            )

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if not self.editable:
            return
        button = (
            1
            if event.button() == Qt.MouseButton.LeftButton
            else 3
            if event.button() == Qt.MouseButton.RightButton
            else None
        )
        cell = self.cell_at_position(event.position())
        if button is not None and cell is not None:
            self._active_button = button
            self.stroke_started.emit(cell[0], cell[1], button)
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        cell = self.cell_at_position(event.position())
        if cell != self.hover_cell:
            self.hover_cell = cell
            self.update()
        if self.editable and self._active_button is not None and cell is not None:
            self.stroke_moved.emit(cell[0], cell[1])

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._active_button is not None:
            self._active_button = None
            self.stroke_ended.emit()
            event.accept()

    def leaveEvent(self, event) -> None:
        self.hover_cell = None
        self.update()
        super().leaveEvent(event)


class BoardWidget(QScrollArea):
    stroke_started = Signal(int, int, int)
    stroke_moved = Signal(int, int)
    stroke_ended = Signal()
    zoom_changed = Signal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(False)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self.surface = BoardSurface()
        self.setWidget(self.surface)
        self.surface.stroke_started.connect(self.stroke_started.emit)
        self.surface.stroke_moved.connect(self.stroke_moved.emit)
        self.surface.stroke_ended.connect(self.stroke_ended.emit)

    def set_model(
        self,
        puzzle: Puzzle,
        board: BoardSnapshot,
        focus: SearchFocus | None = None,
        mismatched_rows: tuple[int, ...] = (),
        mismatched_cols: tuple[int, ...] = (),
    ) -> None:
        self.surface.set_model(puzzle, board, focus, mismatched_rows, mismatched_cols)

    def set_editable(self, editable: bool) -> None:
        self.surface.set_editable(editable)

    def set_zoom(self, zoom: float) -> None:
        old_center_x = self.horizontalScrollBar().value() + self.viewport().width() / 2
        old_center_y = self.verticalScrollBar().value() + self.viewport().height() / 2
        old_width = max(1, self.surface.width())
        old_height = max(1, self.surface.height())
        self.surface.set_zoom(zoom)
        self.horizontalScrollBar().setValue(
            round(
                old_center_x / old_width * self.surface.width()
                - self.viewport().width() / 2
            )
        )
        self.verticalScrollBar().setValue(
            round(
                old_center_y / old_height * self.surface.height()
                - self.viewport().height() / 2
            )
        )
        self.zoom_changed.emit(self.surface.zoom)

    def fit_to_view(self) -> None:
        if self.surface.puzzle is None:
            return
        self.surface.set_zoom(1.0)
        base = self.surface.metrics
        available_w = max(100, self.viewport().width() - 12)
        available_h = max(100, self.viewport().height() - 12)
        zoom = min(available_w / base.total_width, available_h / base.total_height, 1.6)
        self.set_zoom(max(0.5, zoom))

    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = 0.1 if event.angleDelta().y() > 0 else -0.1
            self.set_zoom(self.surface.zoom + delta)
            event.accept()
            return
        super().wheelEvent(event)
