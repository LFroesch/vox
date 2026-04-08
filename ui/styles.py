"""Shared colours, QSS stylesheet and font helper for the vox UI."""

import os
import base64
from datetime import datetime
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

# 10x6 down-arrow PNG (transparent bg, #8f8f9a stroke) — pre-rendered, no SVG/QtSvg needed
_ARROW_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAoAAAAGCAYAAAD68A/GAAAAOklEQVQI"
    "W2NkgIL/DFgAIxMDNsCILgEDTOgSMADVCkZsEkwMWAArNgkYYMEmAQNY"
    "JZiwScAAACFxC3VgMdBYAAAAAElFTkSuQmCC"
)

def _get_arrow_path():
    p = os.path.join(os.path.expanduser("~/.vox"), "arrow_down.png")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    if not os.path.exists(p):
        with open(p, "wb") as f:
            f.write(base64.b64decode(_ARROW_PNG_B64))
    return p.replace("\\", "/")

COLORS = {
    "bg": "#09090b",
    "surface": "#111113",
    "surface_light": "#1a1a1f",
    "hover": "#252529",
    "border": "#2c2c33",
    "accent": "#e4e4e7",
    "accent_hover": "#c8c8cc",
    "success": "#34d399",
    "warning": "#fbbf24",
    "error": "#f87171",
    "text": "#ededf0",
    "text_dim": "#8f8f9a",
    "text_muted": "#55555f",
    "text_dark": "#09090b",
}

R = {"sm": 4, "md": 6, "lg": 8}

_UI_SCALE_FACTORS = {"Small": 0.85, "Medium": 1.0, "Large": 1.15}
_ui_scale_factor = 1.0

_font_cache: dict = {}


def set_ui_scale(label: str):
    global _ui_scale_factor
    _ui_scale_factor = _UI_SCALE_FACTORS.get(label, 1.0)


def font(size: int = 13, weight: str = "normal", family: str | None = None) -> QFont:
    scaled = int(size * _ui_scale_factor)
    key = (scaled, weight, family)
    if key not in _font_cache:
        f = QFont()
        if family:
            f.setFamily(family)
        f.setPixelSize(scaled)
        if weight == "bold":
            f.setBold(True)
        _font_cache[key] = f
    return _font_cache[key]


# Layout preview palette
PREVIEW_COLORS = [
    "#3b82a6", "#6d9e5b", "#a67b3b", "#8b5da6",
    "#5ba69e", "#a65b6d", "#7b8ba6", "#a6985b",
]

WIDGET_WIDTHS = {"Small": 175, "Large": 250}


def fmt_time(dt: datetime = None, seconds: bool = True) -> str:
    """Fixed-width time string for aligned columns in monospace contexts.
    seconds=True  → ' 5:08:29 PM' (11 chars)
    seconds=False → ' 5:08 PM'    ( 8 chars)
    """
    dt = dt or datetime.now()
    if seconds:
        return dt.strftime("%I:%M:%S %p").lstrip("0").rjust(11)
    return dt.strftime("%I:%M %p").lstrip("0").rjust(8)


def fix_combo_popup(combo):
    """Ensure combo popup appears above sibling widgets."""
    from PyQt6.QtCore import Qt
    original_show = combo.showPopup
    def patched_show():
        original_show()
        popup = combo.view().window()
        if popup and popup is not combo.window():
            popup.raise_()
            popup.activateWindow()
    combo.showPopup = patched_show


def build_stylesheet() -> str:
    """Return the global QSS stylesheet string."""
    c = COLORS
    r = R
    return f"""
    /* ── Global ─────────────────────────────────────── */
    QMainWindow, QDialog {{
        background: {c['bg']};
    }}
    QWidget {{
        color: {c['text']};
        font-size: {int(13 * _ui_scale_factor)}px;
    }}
    QLabel {{
        background: transparent;
    }}

    /* ── Buttons ────────────────────────────────────── */
    QPushButton {{
        background: {c['surface_light']};
        color: {c['text']};
        border: 1px solid {c['border']};
        border-radius: {r['md']}px;
        padding: 5px 12px;
    }}
    QPushButton:hover {{
        background: {c['hover']};
    }}
    QPushButton:pressed {{
        background: {c['border']};
    }}
    QPushButton[accent="true"] {{
        background: {c['accent']};
        color: {c['text_dark']};
        border: none;
        font-weight: bold;
    }}
    QPushButton[accent="true"]:hover {{
        background: {c['accent_hover']};
    }}
    QPushButton[flat="true"] {{
        background: transparent;
        border: none;
    }}
    QPushButton[flat="true"]:hover {{
        background: {c['hover']};
    }}

    /* ── Inputs ─────────────────────────────────────── */
    QLineEdit {{
        background: {c['surface']};
        color: {c['text']};
        border: 1px solid {c['border']};
        border-radius: {r['md']}px;
        padding: 4px 8px;
    }}
    QLineEdit:focus {{
        border-color: {c['accent']};
    }}
    QTextEdit, QPlainTextEdit {{
        background: {c['surface']};
        color: {c['text']};
        border: 1px solid {c['border']};
        border-radius: {r['md']}px;
        padding: 4px;
    }}

    /* ── ComboBox ───────────────────────────────────── */
    QComboBox {{
        background: {c['surface']};
        color: {c['text']};
        border: 1px solid {c['border']};
        border-radius: {r['md']}px;
        padding: 4px 28px 4px 8px;
        min-height: 22px;
    }}
    QComboBox::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: center right;
        width: 20px;
        border: none;
        background: transparent;
    }}
    QComboBox::down-arrow {{
        image: none;
        width: 0;
        height: 0;
        border-left: 5px solid transparent;
        border-right: 5px solid transparent;
        border-top: 6px solid {c['accent']};
        margin-left: -5px;
        margin-top: -3px;
    }}
    QComboBox QAbstractItemView {{
        background: {c['surface_light']};
        color: {c['text']};
        border: 1px solid {c['border']};
        selection-background-color: {c['hover']};
        outline: none;
    }}
    QComboBox QAbstractItemView::item {{
        padding: 4px 8px;
        min-height: 22px;
    }}
    QComboBox QAbstractItemView::item:hover {{
        background: {c['hover']};
    }}

    /* ── CheckBox ───────────────────────────────────── */
    QCheckBox {{
        spacing: 6px;
    }}
    QCheckBox::indicator {{
        width: 16px;
        height: 16px;
        border: 1px solid {c['border']};
        border-radius: 3px;
        background: {c['surface']};
    }}
    QCheckBox::indicator:checked {{
        background: {c['accent']};
        border-color: {c['accent']};
    }}

    /* ── ScrollArea ─────────────────────────────────── */
    QScrollArea {{
        background: transparent;
        border: none;
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 8px;
        margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: {c['surface_light']};
        border-radius: 4px;
        min-height: 20px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {c['hover']};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        background: none;
        height: 0;
    }}
    QScrollBar:horizontal {{
        height: 0;
    }}

    /* ── TabWidget ──────────────────────────────────── */
    QTabWidget::pane {{
        background: {c['surface_light']};
        border: 1px solid {c['border']};
        border-radius: {r['lg']}px;
    }}
    QTabBar::tab {{
        background: {c['surface']};
        color: {c['text_dim']};
        padding: 6px 14px;
        border: 1px solid {c['border']};
        border-bottom: none;
        border-top-left-radius: {r['md']}px;
        border-top-right-radius: {r['md']}px;
        margin-right: 2px;
    }}
    QTabBar::tab:selected {{
        background: {c['hover']};
        color: {c['text']};
    }}
    QTabBar::tab:hover {{
        background: {c['surface_light']};
    }}

    /* ── Sidebar (QListWidget) ──────────────────────── */
    QListWidget#sidebar {{
        background: {c['surface']};
        border: none;
        border-right: 1px solid {c['border']};
        outline: none;
    }}
    QListWidget#sidebar::item {{
        color: {c['text_dim']};
        padding: 10px 14px;
        border: none;
    }}
    QListWidget#sidebar::item:selected {{
        background: {c['hover']};
        color: {c['text']};
        border-left: 3px solid {c['accent']};
        padding-left: 11px;
    }}
    QListWidget#sidebar::item:hover:!selected {{
        background: {c['surface_light']};
    }}

    /* ── Frame cards ────────────────────────────────── */
    QFrame[card="true"] {{
        background: {c['surface_light']};
        border: 1px solid {c['border']};
        border-radius: {r['lg']}px;
    }}
    QFrame[section="true"] {{
        background: {c['surface']};
        border: 1px solid {c['border']};
        border-radius: {r['md']}px;
    }}

    /* ── Header bar ─────────────────────────────────── */
    QFrame#header {{
        background: {c['surface']};
        border: none;
        border-bottom: 1px solid {c['border']};
    }}

    /* ── Message boxes ──────────────────────────────── */
    QMessageBox {{
        background: {c['bg']};
    }}
    QMessageBox QLabel {{
        color: {c['text']};
    }}
    QMessageBox QPushButton {{
        min-width: 70px;
    }}
    """
