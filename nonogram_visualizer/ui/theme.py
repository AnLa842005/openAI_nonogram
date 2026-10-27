"""Application palette, stylesheet, fonts, and small painted icons."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QIcon, QPalette
from PySide6.QtWidgets import QApplication, QStyle

COLORS = {
    "window": "#F3F5F8",
    "panel": "#FFFFFF",
    "text": "#1E293B",
    "muted": "#64748B",
    "border": "#DDE3EA",
    "primary": "#4F46E5",
    "primary_hover": "#4338CA",
    "primary_pressed": "#3730A3",
    "success": "#15803D",
    "warning": "#B45309",
    "error": "#B91C1C",
}


APP_STYLESHEET = f"""
QMainWindow, QWidget#appRoot {{
    background: {COLORS["window"]};
    color: {COLORS["text"]};
}}
QToolBar {{
    background: {COLORS["panel"]};
    border: none;
    border-bottom: 1px solid {COLORS["border"]};
    spacing: 6px;
    padding: 8px 12px;
}}
QToolBar QToolButton {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 7px;
    padding: 7px 10px;
}}
QToolBar QToolButton:hover {{ background: #EEF2FF; border-color: #C7D2FE; }}
QToolBar QToolButton:pressed {{ background: #E0E7FF; }}
QDockWidget {{
    color: {COLORS["text"]};
    font-weight: 600;
}}
QDockWidget::title {{
    background: {COLORS["panel"]};
    border-left: 1px solid {COLORS["border"]};
    padding: 8px 12px;
}}
QScrollArea, QAbstractScrollArea {{ border: none; background: {COLORS["window"]}; }}
QWidget#controlPanel, QFrame#card, QFrame#metricCard {{
    background: {COLORS["panel"]};
}}
QFrame#card {{
    border: 1px solid {COLORS["border"]};
    border-radius: 10px;
}}
QFrame#metricCard {{
    border: 1px solid #E7EAF0;
    border-radius: 8px;
}}
QLabel {{ color: {COLORS["text"]}; background: transparent; }}
QLabel#muted {{ color: {COLORS["muted"]}; }}
QLabel#sectionTitle {{ font-size: 13px; font-weight: 650; }}
QLabel#metricValue {{ font-size: 16px; font-weight: 700; }}
QLabel#statusBadge {{ border-radius: 7px; padding: 5px 9px; font-weight: 650; }}
QLabel#statusBadge[statusKind="neutral"] {{ color: #475569; background: #E9EEF3; }}
QLabel#statusBadge[statusKind="active"] {{ color: #1D4ED8; background: #DBEAFE; }}
QLabel#statusBadge[statusKind="success"] {{ color: #166534; background: #DCFCE7; }}
QLabel#statusBadge[statusKind="warning"] {{ color: #92400E; background: #FEF3C7; }}
QLabel#statusBadge[statusKind="error"] {{ color: #991B1B; background: #FEE2E2; }}
QPushButton, QToolButton {{
    background: {COLORS["panel"]};
    color: {COLORS["text"]};
    border: 1px solid #CBD5E1;
    border-radius: 7px;
    padding: 7px 11px;
    min-height: 18px;
}}
QPushButton:hover, QToolButton:hover {{ background: #F8FAFC; border-color: #94A3B8; }}
QPushButton:pressed, QToolButton:pressed {{ background: #EEF2F6; }}
QPushButton:disabled, QToolButton:disabled {{ color: #94A3B8; background: #F1F5F9; border-color: #E2E8F0; }}
QPushButton#primaryButton {{
    background: {COLORS["primary"]}; color: white; border-color: {COLORS["primary"]}; font-weight: 650;
}}
QPushButton#primaryButton:hover {{ background: {COLORS["primary_hover"]}; }}
QPushButton#primaryButton:pressed {{ background: {COLORS["primary_pressed"]}; }}
QPushButton#secondaryDanger {{ color: {COLORS["error"]}; }}
QToolButton#modeButton {{ border-radius: 7px; padding: 8px; }}
QToolButton#modeButton:checked {{ background: #E0E7FF; color: #3730A3; border-color: #A5B4FC; font-weight: 650; }}
QComboBox, QSpinBox, QLineEdit {{
    background: white; border: 1px solid #CBD5E1; border-radius: 7px; padding: 6px 8px; min-height: 20px;
}}
QComboBox:focus, QSpinBox:focus, QLineEdit:focus {{ border: 1px solid #6366F1; }}
QSlider::groove:horizontal {{ height: 4px; background: #CBD5E1; border-radius: 2px; }}
QSlider::handle:horizontal {{ width: 15px; margin: -6px 0; border-radius: 7px; background: {COLORS["primary"]}; }}
QStatusBar {{ background: {COLORS["panel"]}; border-top: 1px solid {COLORS["border"]}; color: {COLORS["muted"]}; }}
QScrollBar:vertical {{ width: 11px; background: transparent; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #C3CBD5; border-radius: 5px; min-height: 30px; }}
QScrollBar:horizontal {{ height: 11px; background: transparent; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: #C3CBD5; border-radius: 5px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QDialog, QMessageBox {{ background: {COLORS["panel"]}; color: {COLORS["text"]}; }}
QComboBox, QSpinBox, QLineEdit {{
    color: {COLORS["text"]}; selection-background-color: #E0E7FF; selection-color: #3730A3;
}}
QComboBox:disabled, QSpinBox:disabled, QLineEdit:disabled {{ color: #94A3B8; background: #F1F5F9; }}
QComboBox QAbstractItemView {{
    background: {COLORS["panel"]}; color: {COLORS["text"]};
    border: 1px solid {COLORS["border"]}; outline: none; padding: 4px;
    selection-background-color: #EEF2FF; selection-color: #3730A3;
}}
QMenu {{
    background: {COLORS["panel"]}; color: {COLORS["text"]};
    border: 1px solid {COLORS["border"]}; border-radius: 8px; padding: 5px;
}}
QMenu::item {{ padding: 7px 22px 7px 12px; border-radius: 6px; background: transparent; }}
QMenu::item:selected {{ background: #EEF2FF; color: #3730A3; }}
QMenu::item:disabled {{ color: #94A3B8; }}
QMenu::separator {{ height: 1px; background: {COLORS["border"]}; margin: 5px 8px; }}
QToolTip {{
    background: {COLORS["text"]}; color: white; border: none; border-radius: 6px; padding: 5px 8px;
}}
"""


def _light_palette() -> QPalette:
    """Light palette for anything the stylesheet does not cover."""

    palette = QPalette()
    roles = {
        QPalette.ColorRole.Window: COLORS["window"],
        QPalette.ColorRole.WindowText: COLORS["text"],
        QPalette.ColorRole.Base: COLORS["panel"],
        QPalette.ColorRole.AlternateBase: "#F8FAFC",
        QPalette.ColorRole.Text: COLORS["text"],
        QPalette.ColorRole.PlaceholderText: COLORS["muted"],
        QPalette.ColorRole.Button: COLORS["panel"],
        QPalette.ColorRole.ButtonText: COLORS["text"],
        QPalette.ColorRole.BrightText: "#FFFFFF",
        QPalette.ColorRole.Highlight: "#E0E7FF",
        QPalette.ColorRole.HighlightedText: "#3730A3",
        QPalette.ColorRole.ToolTipBase: COLORS["text"],
        QPalette.ColorRole.ToolTipText: "#FFFFFF",
        QPalette.ColorRole.Link: COLORS["primary"],
    }
    for role, color in roles.items():
        palette.setColor(role, QColor(color))
    for role in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
    ):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor("#94A3B8"))
    return palette


def apply_theme(app: QApplication) -> None:
    # The theme is light-only. Without this, Windows dark mode hands Qt a dark
    # palette and popups render light text on the stylesheet's white backgrounds.
    hints = app.styleHints()
    if hasattr(hints, "setColorScheme"):
        hints.setColorScheme(Qt.ColorScheme.Light)
    app.setPalette(_light_palette())
    families = set(QFontDatabase.families())
    family = "Segoe UI" if "Segoe UI" in families else QFont().defaultFamily()
    app.setFont(QFont(family, 10))
    app.setStyleSheet(APP_STYLESHEET)


def standard_icon(widget, standard_pixmap: QStyle.StandardPixmap) -> QIcon:
    return widget.style().standardIcon(standard_pixmap)
