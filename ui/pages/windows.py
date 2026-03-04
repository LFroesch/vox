"""Windows page — Saved Layouts (dropdown + QPainter preview) + Save New Layout."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QLineEdit, QCheckBox, QScrollArea, QMessageBox,
    QGridLayout,
)
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QColor, QFont as QF, QPen

from ui.styles import COLORS, font, R, PREVIEW_COLORS

from PyQt6.QtWidgets import QComboBox


class LayoutPreview(QWidget):
    """QPainter-based layout preview."""

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(180)
        self._windows = []
        self._app_display = None

    def set_layout_data(self, windows: list, app_display_func=None):
        self._windows = windows
        self._app_display = app_display_func
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        cw, ch = self.width(), self.height()
        painter.fillRect(0, 0, cw, ch, QColor(COLORS["bg"]))

        if not self._windows:
            painter.setPen(QColor(COLORS["text_muted"]))
            painter.drawText(QRectF(0, 0, cw, ch), Qt.AlignmentFlag.AlignCenter, "Empty layout")
            painter.end()
            return

        # Bounding box
        min_x = min(w['x'] for w in self._windows)
        min_y = min(w['y'] for w in self._windows)
        max_x = max(w['x'] + w['w'] for w in self._windows)
        max_y = max(w['y'] + w['h'] for w in self._windows)
        bb_w = max(max_x - min_x, 1)
        bb_h = max(max_y - min_y, 1)

        pad = 12
        scale = min((cw - pad * 2) / bb_w, (ch - pad * 2) / bb_h)
        scaled_w = bb_w * scale
        scaled_h = bb_h * scale
        ox = (cw - scaled_w) / 2
        oy = (ch - scaled_h) / 2

        # Desktop bg
        painter.setPen(QPen(QColor(COLORS["border"]), 1))
        painter.setBrush(QColor("#141418"))
        painter.drawRect(QRectF(ox - 2, oy - 2, scaled_w + 4, scaled_h + 4))

        # Draw windows
        app_color_map = {}
        color_idx = 0
        for w in self._windows:
            app = w.get('app', 'unknown')
            if app not in app_color_map:
                app_color_map[app] = PREVIEW_COLORS[color_idx % len(PREVIEW_COLORS)]
                color_idx += 1

            rx = ox + (w['x'] - min_x) * scale
            ry = oy + (w['y'] - min_y) * scale
            rw = w['w'] * scale
            rh = w['h'] * scale

            color = app_color_map[app]
            painter.setPen(QPen(QColor("#333333"), 1))
            painter.setBrush(QColor(color))
            painter.drawRect(QRectF(rx + 1, ry + 1, rw - 2, rh - 2))

            # Label
            display = self._app_display(app) if self._app_display else app
            if rw > 16 and rh > 10:
                font_size = max(7, min(12, int(min(rh / 2, rw / 5))))
                max_chars = max(1, int(rw / (font_size * 0.55)))
                label = display[:max_chars]
                f = QF()
                f.setPixelSize(font_size)
                painter.setFont(f)
                painter.setPen(QColor("#dddddd"))
                painter.drawText(QRectF(rx, ry, rw, rh), Qt.AlignmentFlag.AlignCenter, label)

        painter.end()


class WindowsPage(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.windows = []
        self.selected_windows = []
        self.window_checkboxes = {}
        self.auto_launch_vars = {}
        self._collapsed_groups = set()
        self._windows_initialized = False
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # == Section A: Saved Layouts ==
        section_a = QFrame()
        section_a.setProperty("card", True)
        sa_layout = QVBoxLayout(section_a)
        sa_layout.setContentsMargins(10, 8, 10, 8)

        # Row: dropdown + buttons
        row = QHBoxLayout()
        lbl = QLabel("LAYOUT")
        lbl.setFont(font(11, "bold"))
        lbl.setStyleSheet(f"color: {COLORS['text_muted']};")
        row.addWidget(lbl)

        self._layout_dropdown = QComboBox()
        self._layout_dropdown.setMinimumWidth(180)
        self._layout_dropdown.currentTextChanged.connect(self._on_layout_selected)
        row.addWidget(self._layout_dropdown)

        self._load_btn = QPushButton("Load")
        self._load_btn.setFixedSize(55, 30)
        self._load_btn.setProperty("accent", True)
        self._load_btn.clicked.connect(self._load_selected_layout)
        row.addWidget(self._load_btn)

        edit_btn = QPushButton("Edit")
        edit_btn.setFixedSize(45, 30)
        edit_btn.clicked.connect(self._edit_selected_layout)
        row.addWidget(edit_btn)

        del_btn = QPushButton("Del")
        del_btn.setFixedSize(40, 30)
        del_btn.clicked.connect(self._delete_selected_layout)
        row.addWidget(del_btn)

        self._fav_btn = QPushButton("♡")
        self._fav_btn.setFixedSize(30, 30)
        self._fav_btn.setFont(font(15))
        self._fav_btn.setProperty("flat", True)
        self._fav_btn.clicked.connect(self._toggle_fav_layout)
        row.addWidget(self._fav_btn)

        row.addStretch()
        sa_layout.addLayout(row)

        # Preview
        self._preview = LayoutPreview()
        sa_layout.addWidget(self._preview)

        # Info label
        self._layout_info = QLabel("")
        self._layout_info.setFont(font(12))
        self._layout_info.setStyleSheet(f"color: {COLORS['text_dim']};")
        sa_layout.addWidget(self._layout_info)

        layout.addWidget(section_a)

        # == Section B: Save New Layout ==
        section_b = QFrame()
        section_b.setProperty("card", True)
        sb_layout = QVBoxLayout(section_b)
        sb_layout.setContentsMargins(10, 8, 10, 8)

        # Header: Save Layout + name + button
        save_row = QHBoxLayout()
        save_lbl = QLabel("Save Layout")
        save_lbl.setFont(font(13, "bold"))
        save_lbl.setStyleSheet(f"color: {COLORS['text_dim']};")
        save_row.addWidget(save_lbl)
        save_row.addStretch()

        self.layout_name_entry = QLineEdit()
        self.layout_name_entry.setPlaceholderText("Layout name...")
        self.layout_name_entry.setFixedWidth(160)
        self.layout_name_entry.setFixedHeight(30)
        save_row.addWidget(self.layout_name_entry)

        save_btn = QPushButton("Save")
        save_btn.setFixedSize(70, 30)
        save_btn.setProperty("accent", True)
        save_btn.clicked.connect(self._save_layout)
        save_row.addWidget(save_btn)
        sb_layout.addLayout(save_row)

        # Button row
        btn_row = QHBoxLayout()
        for text, cb in [("Select All", self._select_all), ("Deselect All", self._deselect_all)]:
            b = QPushButton(text)
            b.setFixedHeight(28)
            b.clicked.connect(cb)
            btn_row.addWidget(b)
        btn_row.addStretch()

        self._selection_label = QLabel("")
        self._selection_label.setFont(font(12))
        self._selection_label.setStyleSheet(f"color: {COLORS['text_dim']};")
        btn_row.addWidget(self._selection_label)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setFixedHeight(28)
        refresh_btn.clicked.connect(self.refresh_windows)
        btn_row.addWidget(refresh_btn)
        sb_layout.addLayout(btn_row)

        # Window list scroll
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._window_list_widget = QWidget()
        self._window_list_layout = QVBoxLayout(self._window_list_widget)
        self._window_list_layout.setContentsMargins(2, 2, 2, 2)
        self._window_list_layout.setSpacing(2)
        scroll.setWidget(self._window_list_widget)
        sb_layout.addWidget(scroll, stretch=1)

        layout.addWidget(section_b, stretch=1)

        self._refresh_layout_dropdown()
        self.refresh_windows()

    # -- Layout dropdown --
    def _refresh_layout_dropdown(self):
        layouts = self.app.layout_manager.get_layout_names()
        self._layout_dropdown.blockSignals(True)
        self._layout_dropdown.clear()
        if layouts:
            self._layout_dropdown.addItems(layouts)
        else:
            self._layout_dropdown.addItem("(none)")
        self._layout_dropdown.blockSignals(False)
        self._on_layout_selected(self._layout_dropdown.currentText())

    def _on_layout_selected(self, name: str = ""):
        if not name:
            name = self._layout_dropdown.currentText()
        if not name or name == "(none)":
            self._preview.set_layout_data([])
            self._layout_info.setText("No layouts saved")
            return

        # Build preview data
        if name in self.app.layout_manager.layouts:
            layout_data = self.app.layout_manager.layouts[name]
            windows = []
            for wd in layout_data.values():
                pos = wd.get('position', {})
                ident = wd.get('identifier', {})
                if pos and ident:
                    x, y = pos.get('x', 0), pos.get('y', 0)
                    w, h = pos.get('width', 400), pos.get('height', 300)
                    if w > 0 and h > 0:
                        windows.append({'x': x, 'y': y, 'w': w, 'h': h,
                                        'app': ident.get('app_type', 'unknown')})
            self._preview.set_layout_data(windows, self.app.window_manager.get_app_display_name)

        # Info label
        info = self.app.layout_manager.get_layout_info(name)
        layout_data = self.app.layout_manager.layouts.get(name, {})
        apps = []
        for wd in layout_data.values():
            if 'identifier' in wd:
                app = wd['identifier'].get('app_type', 'unknown')
                apps.append(self.app.window_manager.get_app_display_name(app))
        matches = info.get('matches', 0) if info else 0
        total = info.get('window_count', 0) if info else 0
        if matches == total:
            color = COLORS["success"]
        elif matches > 0:
            color = COLORS["warning"]
        else:
            color = COLORS["text_dim"]
        preview = ", ".join(apps[:4])
        if len(apps) > 4:
            preview += f" +{len(apps) - 4}"
        text = f"{matches}/{total} matched"
        if preview:
            text += f"  ·  {preview}"
        self._layout_info.setText(text)
        self._layout_info.setStyleSheet(f"color: {color};")
        self._update_fav_btn()

    def _update_fav_btn(self):
        name = self._layout_dropdown.currentText()
        if name and name != "(none)" and self.app.is_favorite('layouts', name):
            self._fav_btn.setText("♥")
            self._fav_btn.setStyleSheet(f"color: {COLORS['accent']};")
        else:
            self._fav_btn.setText("♡")
            self._fav_btn.setStyleSheet(f"color: {COLORS['text_dim']};")

    def _load_selected_layout(self):
        name = self._layout_dropdown.currentText()
        if name and name != "(none)":
            self.app.quick_load_layout(name)

    def _edit_selected_layout(self):
        name = self._layout_dropdown.currentText()
        if name and name != "(none)":
            self.app.edit_layout(name)

    def _delete_selected_layout(self):
        name = self._layout_dropdown.currentText()
        if name and name != "(none)":
            self.app.delete_layout(name)
            self._refresh_layout_dropdown()

    def _toggle_fav_layout(self):
        name = self._layout_dropdown.currentText()
        if name and name != "(none)":
            self.app.toggle_favorite('layouts', name)
            self._update_fav_btn()

    # -- Window list for save --
    def refresh_windows(self):
        self.windows = self.app.window_manager.get_all_windows()
        current_hwnds = {w.hwnd for w in self.windows}

        if not self._windows_initialized:
            self.selected_windows = list(current_hwnds)
            self._windows_initialized = True
        else:
            self.selected_windows = [h for h in self.selected_windows if h in current_hwnds]

        _clear(self._window_list_layout)
        self.window_checkboxes = {}
        self.auto_launch_vars = {}

        if not self.windows:
            lbl = QLabel("No windows found")
            lbl.setStyleSheet(f"color: {COLORS['text_dim']};")
            lbl.setFont(font(13))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._window_list_layout.addWidget(lbl)
            self._update_save_bar()
            return

        for window in self.windows:
            self._create_window_entry(window)

        self._window_list_layout.addStretch()
        self._update_save_bar()

    def _create_window_entry(self, window):
        is_selected = window.hwnd in self.selected_windows
        app_type = self.app.window_manager.get_app_type(window)
        display_name = self.app.window_manager.get_app_display_name(app_type)

        entry = QFrame()
        bg = COLORS["hover"] if is_selected else COLORS["surface_light"]
        entry.setStyleSheet(
            f"QFrame {{ background: {bg}; border-radius: {R['md']}px; }}"
        )
        entry.setFixedHeight(38)
        row = QHBoxLayout(entry)
        row.setContentsMargins(8, 0, 4, 0)

        cb = QCheckBox()
        cb.setChecked(is_selected)
        cb.stateChanged.connect(lambda state, h=window.hwnd: self._toggle_window_select(h))
        row.addWidget(cb)
        self.window_checkboxes[window.hwnd] = cb

        app_lbl = QLabel(display_name)
        app_lbl.setFont(font(13, "bold"))
        row.addWidget(app_lbl)

        title = window.title[:40] + "..." if len(window.title) > 40 else window.title
        title_lbl = QLabel(title)
        title_lbl.setFont(font(12))
        title_lbl.setStyleSheet(f"color: {COLORS['text_dim']};")
        row.addWidget(title_lbl, stretch=1)

        dim_lbl = QLabel(f"{window.width}×{window.height}")
        dim_lbl.setFont(font(11))
        dim_lbl.setStyleSheet(f"color: {COLORS['text_muted']};")
        row.addWidget(dim_lbl)

        auto_cb = QCheckBox("Auto")
        auto_cb.setFont(font(11))
        auto_cb.setStyleSheet(f"color: {COLORS['text_muted']};")
        row.addWidget(auto_cb)
        self.auto_launch_vars[window.hwnd] = auto_cb

        self._window_list_layout.addWidget(entry)

    def _toggle_window_select(self, hwnd: int):
        if hwnd in self.selected_windows:
            self.selected_windows.remove(hwnd)
        else:
            self.selected_windows.append(hwnd)
        # Update checkbox and bg
        if hwnd in self.window_checkboxes:
            cb = self.window_checkboxes[hwnd]
            cb.blockSignals(True)
            cb.setChecked(hwnd in self.selected_windows)
            cb.blockSignals(False)
            entry = cb.parentWidget()
            if entry:
                bg = COLORS["hover"] if hwnd in self.selected_windows else COLORS["surface_light"]
                entry.setStyleSheet(
                    f"QFrame {{ background: {bg}; border-radius: {R['md']}px; }}"
                )
        self._update_save_bar()

    def _select_all(self):
        self.selected_windows = [w.hwnd for w in self.windows]
        self.refresh_windows()

    def _deselect_all(self):
        self.selected_windows.clear()
        self.refresh_windows()

    def _update_save_bar(self):
        count = len(self.selected_windows)
        self._selection_label.setText(
            f"{count} window{'s' if count != 1 else ''} selected" if count else ""
        )

    def _save_layout(self):
        name = self.layout_name_entry.text().strip()
        if not name:
            QMessageBox.warning(self, "No Name", "Enter a layout name")
            return
        if not self.selected_windows:
            QMessageBox.warning(self, "No Selection", "Select windows to save")
            return

        current_windows = {w.hwnd: w for w in self.app.window_manager.get_all_windows()}
        windows = [current_windows[h] for h in self.selected_windows if h in current_windows]
        if not windows:
            QMessageBox.warning(self, "Windows Gone", "Selected windows no longer exist")
            return

        auto_launch_config = {
            hwnd: cb.isChecked() for hwnd, cb in self.auto_launch_vars.items()
        }
        if self.app.layout_manager.save_layout(name, windows, auto_launch_config):
            self.app.commands._refresh_layout_commands()
            self._refresh_layout_dropdown()
            self.app.mark_dirty("home", "voice")
            self.layout_name_entry.clear()
            self.selected_windows.clear()
            self.refresh_windows()
            self.app.set_status(f"Layout '{name}' saved", COLORS["success"])

    def refresh_saved_layouts(self):
        self._refresh_layout_dropdown()


def _clear(layout):
    while layout.count():
        child = layout.takeAt(0)
        if child.widget():
            child.widget().deleteLater()
        elif child.layout():
            _clear(child.layout())
