"""Windows page — Layouts tab + Workflows tab in a QTabWidget."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QLineEdit, QCheckBox, QScrollArea, QMessageBox,
    QGridLayout, QComboBox, QTabWidget, QDialog, QSpinBox,
    QFileDialog,
)
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QColor, QFont as QF, QPen

from ui.styles import COLORS, font, R, PREVIEW_COLORS
from modules.workflows.workflow import Workflow, WorkflowStep


def _next_name(base: str, exists_fn) -> str:
    """Generate 'Name (2)', 'Name (3)', etc. until no conflict."""
    i = 2
    while True:
        candidate = f"{base} ({i})"
        if not exists_fn(candidate):
            return candidate
        i += 1


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
        self._collapsed_groups = set()
        self._windows_initialized = False
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self._tabs = QTabWidget()
        layout.addWidget(self._tabs)

        # == Layouts Tab ==
        layouts_tab = QWidget()
        self._build_layouts_tab(layouts_tab)
        self._tabs.addTab(layouts_tab, "Layouts")

        # == Workflows Tab ==
        workflows_tab = QWidget()
        self._build_workflows_tab(workflows_tab)
        self._tabs.addTab(workflows_tab, "Workflows")

    # ═══════════════════════════════════════════
    # LAYOUTS TAB
    # ═══════════════════════════════════════════

    def _build_layouts_tab(self, parent):
        layout = QVBoxLayout(parent)
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
        self._load_btn.setFixedSize(60, 30)
        self._load_btn.setProperty("accent", True)
        self._load_btn.clicked.connect(self._load_selected_layout)
        row.addWidget(self._load_btn)

        edit_btn = QPushButton("Edit")
        edit_btn.setFixedSize(60, 30)
        edit_btn.clicked.connect(self._edit_selected_layout)
        row.addWidget(edit_btn)

        del_btn = QPushButton("Delete")
        del_btn.setFixedSize(80, 30)
        del_btn.clicked.connect(self._delete_selected_layout)
        row.addWidget(del_btn)

        dup_btn = QPushButton("Dup")
        dup_btn.setFixedSize(50, 30)
        dup_btn.clicked.connect(self._duplicate_selected_layout)
        row.addWidget(dup_btn)

        self._fav_btn = QPushButton("\U0001f90d")
        self._fav_btn.setFixedSize(44, 30)
        self._fav_btn.setFont(font(14))
        self._fav_btn.clicked.connect(self._toggle_fav_layout)
        row.addWidget(self._fav_btn)

        row.addStretch()
        sa_layout.addLayout(row)

        # Preview
        self._preview = LayoutPreview()
        sa_layout.addWidget(self._preview)

        # Legend
        self._legend_widget = QWidget()
        self._legend_layout = QHBoxLayout(self._legend_widget)
        self._legend_layout.setContentsMargins(0, 2, 0, 2)
        self._legend_layout.setSpacing(12)
        sa_layout.addWidget(self._legend_widget)

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
            self._rebuild_legend([])
            return

        layout_data = self.app.layout_manager.layouts.get(name, {})
        if layout_data:
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

        app_colors = []
        seen = {}
        color_idx = 0
        for wd in layout_data.values():
            if 'identifier' in wd:
                app = wd['identifier'].get('app_type', 'unknown')
                if app not in seen:
                    seen[app] = PREVIEW_COLORS[color_idx % len(PREVIEW_COLORS)]
                    color_idx += 1
                    display = self.app.window_manager.get_app_display_name(app)
                    app_colors.append((display, seen[app]))
        self._rebuild_legend(app_colors)
        self._update_fav_btn()

    def _rebuild_legend(self, app_colors: list):
        _clear(self._legend_layout)
        for name, color in app_colors:
            dot = QLabel("\u25cf")
            dot.setFont(font(12))
            dot.setStyleSheet(f"color: {color};")
            dot.setFixedWidth(14)
            self._legend_layout.addWidget(dot)
            lbl = QLabel(name)
            lbl.setFont(font(11))
            lbl.setStyleSheet(f"color: {COLORS['text_dim']};")
            self._legend_layout.addWidget(lbl)
        self._legend_layout.addStretch()

    def _update_fav_btn(self):
        name = self._layout_dropdown.currentText()
        if name and name != "(none)" and self.app.is_favorite('layouts', name):
            self._fav_btn.setText("\u2764\ufe0f")
        else:
            self._fav_btn.setText("\U0001f90d")

    def _load_selected_layout(self):
        name = self._layout_dropdown.currentText()
        if name and name != "(none)":
            self.app.quick_load_layout(name)
            self.app.set_status(f"Layout '{name}' loaded", COLORS["success"])

    def _edit_selected_layout(self):
        name = self._layout_dropdown.currentText()
        if name and name != "(none)":
            self.app.edit_layout(name)

    def _delete_selected_layout(self):
        name = self._layout_dropdown.currentText()
        if name and name != "(none)":
            reply = QMessageBox.question(
                self, "Delete Layout",
                f"Delete layout '{name}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.app.delete_layout(name)
                self._refresh_layout_dropdown()

    def _duplicate_selected_layout(self):
        name = self._layout_dropdown.currentText()
        if not name or name == "(none)":
            return
        import copy
        lm = self.app.layout_manager
        new_name = _next_name(name, lambda n: n in lm.layouts)
        lm.layouts[new_name] = copy.deepcopy(lm.layouts[name])
        lm._save_layouts()
        self.app.commands._refresh_layout_commands()
        self._refresh_layout_dropdown()
        self._layout_dropdown.setCurrentText(new_name)
        self.app.mark_dirty("home", "voice")
        self.app.set_status(f"Duplicated as '{new_name}'", COLORS["success"])

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

        dim_lbl = QLabel(f"{window.width}\u00d7{window.height}")
        dim_lbl.setFont(font(11))
        dim_lbl.setStyleSheet(f"color: {COLORS['text_muted']};")
        row.addWidget(dim_lbl)

        self._window_list_layout.addWidget(entry)

    def _toggle_window_select(self, hwnd: int):
        if hwnd in self.selected_windows:
            self.selected_windows.remove(hwnd)
        else:
            self.selected_windows.append(hwnd)
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
        for hwnd, cb in self.window_checkboxes.items():
            cb.blockSignals(True)
            cb.setChecked(True)
            cb.blockSignals(False)
            entry = cb.parentWidget()
            if entry:
                entry.setStyleSheet(
                    f"QFrame {{ background: {COLORS['hover']}; border-radius: {R['md']}px; }}"
                )
        self._update_save_bar()

    def _deselect_all(self):
        self.selected_windows.clear()
        for hwnd, cb in self.window_checkboxes.items():
            cb.blockSignals(True)
            cb.setChecked(False)
            cb.blockSignals(False)
            entry = cb.parentWidget()
            if entry:
                entry.setStyleSheet(
                    f"QFrame {{ background: {COLORS['surface_light']}; border-radius: {R['md']}px; }}"
                )
        self._update_save_bar()

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

        if self.app.layout_manager.save_layout(name, windows):
            self.app.commands._refresh_layout_commands()
            self._refresh_layout_dropdown()
            self.app.mark_dirty("home", "voice")
            self.layout_name_entry.clear()
            self.selected_windows.clear()
            self.refresh_windows()
            self.app.set_status(f"Layout '{name}' saved", COLORS["success"])

    def refresh_saved_layouts(self):
        self._refresh_layout_dropdown()

    # ═══════════════════════════════════════════
    # WORKFLOWS TAB
    # ═══════════════════════════════════════════

    def _build_workflows_tab(self, parent):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(8, 8, 8, 8)

        # Top bar: dropdown + buttons
        top = QFrame()
        top.setProperty("card", True)
        top_layout = QVBoxLayout(top)
        top_layout.setContentsMargins(10, 8, 10, 8)

        row = QHBoxLayout()
        lbl = QLabel("WORKFLOW")
        lbl.setFont(font(11, "bold"))
        lbl.setStyleSheet(f"color: {COLORS['text_muted']};")
        row.addWidget(lbl)

        self._wf_dropdown = QComboBox()
        self._wf_dropdown.setMinimumWidth(180)
        self._wf_dropdown.currentTextChanged.connect(self._on_workflow_selected)
        row.addWidget(self._wf_dropdown)

        run_btn = QPushButton("Run")
        run_btn.setFixedSize(60, 30)
        run_btn.setProperty("accent", True)
        run_btn.clicked.connect(self._run_selected_workflow)
        row.addWidget(run_btn)

        edit_btn = QPushButton("Edit")
        edit_btn.setFixedSize(60, 30)
        edit_btn.clicked.connect(self._edit_selected_workflow)
        row.addWidget(edit_btn)

        del_btn = QPushButton("Delete")
        del_btn.setFixedSize(80, 30)
        del_btn.clicked.connect(self._delete_selected_workflow)
        row.addWidget(del_btn)

        wf_dup_btn = QPushButton("Dup")
        wf_dup_btn.setFixedSize(50, 30)
        wf_dup_btn.clicked.connect(self._duplicate_selected_workflow)
        row.addWidget(wf_dup_btn)

        self._wf_fav_btn = QPushButton("\U0001f90d")
        self._wf_fav_btn.setFixedSize(44, 30)
        self._wf_fav_btn.setFont(font(14))
        self._wf_fav_btn.clicked.connect(self._toggle_fav_workflow)
        row.addWidget(self._wf_fav_btn)

        new_btn = QPushButton("+ New")
        new_btn.setFixedSize(68, 30)
        new_btn.clicked.connect(self._new_workflow)
        row.addWidget(new_btn)

        row.addStretch()
        top_layout.addLayout(row)
        layout.addWidget(top)

        # Detail view (read-only)
        detail = QFrame()
        detail.setProperty("card", True)
        self._wf_detail_layout = QVBoxLayout(detail)
        self._wf_detail_layout.setContentsMargins(10, 8, 10, 8)
        layout.addWidget(detail, stretch=1)

        self._refresh_workflow_dropdown()

    def _refresh_workflow_dropdown(self):
        wm = self._get_wf_manager()
        if not wm:
            return
        names = wm.get_names()
        self._wf_dropdown.blockSignals(True)
        self._wf_dropdown.clear()
        if names:
            self._wf_dropdown.addItems(names)
        else:
            self._wf_dropdown.addItem("(none)")
        self._wf_dropdown.blockSignals(False)
        self._on_workflow_selected(self._wf_dropdown.currentText())

    def _get_wf_manager(self):
        return getattr(self.app, 'workflow_manager', None)

    def _on_workflow_selected(self, name: str = ""):
        _clear(self._wf_detail_layout)
        self._update_wf_fav_btn()

        wm = self._get_wf_manager()
        if not wm or not name or name == "(none)":
            lbl = QLabel("No workflow selected")
            lbl.setStyleSheet(f"color: {COLORS['text_dim']};")
            lbl.setFont(font(13))
            self._wf_detail_layout.addWidget(lbl)
            return

        wf = wm.get(name)
        if not wf:
            return

        # Header
        title = QLabel(wf.name)
        title.setFont(font(15, "bold"))
        self._wf_detail_layout.addWidget(title)

        if wf.voice_phrase:
            vp = QLabel(f"Voice: \"{wf.voice_phrase}\"")
            vp.setFont(font(12))
            vp.setStyleSheet(f"color: {COLORS['success']};")
            self._wf_detail_layout.addWidget(vp)

        # Steps
        if wf.steps:
            steps_lbl = QLabel(f"Steps ({len(wf.steps)})")
            steps_lbl.setFont(font(12, "bold"))
            steps_lbl.setStyleSheet(f"color: {COLORS['text_dim']};")
            self._wf_detail_layout.addWidget(steps_lbl)

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setStyleSheet("QScrollArea { border: none; }")
            steps_w = QWidget()
            steps_layout = QVBoxLayout(steps_w)
            steps_layout.setContentsMargins(0, 0, 0, 0)
            steps_layout.setSpacing(2)

            for i, step in enumerate(wf.steps):
                row = QFrame()
                row.setStyleSheet(
                    f"QFrame {{ background: {COLORS['surface_light']}; "
                    f"border-radius: {R['md']}px; }}"
                )
                row.setFixedHeight(36)
                rl = QHBoxLayout(row)
                rl.setContentsMargins(8, 0, 8, 0)

                num = QLabel(f"{i+1}.")
                num.setFont(font(11))
                num.setStyleSheet(f"color: {COLORS['text_muted']};")
                num.setFixedWidth(22)
                rl.addWidget(num)

                badge = QLabel(step.item_type)
                badge.setFont(font(10, "bold"))
                badge.setFixedWidth(60)
                badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
                badge.setStyleSheet(
                    f"background: {COLORS['surface']}; color: {COLORS['accent']}; "
                    f"border-radius: 4px; padding: 1px 4px;"
                )
                rl.addWidget(badge)

                name_lbl = QLabel(step.name)
                name_lbl.setFont(font(12, "bold"))
                rl.addWidget(name_lbl)

                if step.launcher_ref:
                    link_icon = QLabel("🔗")
                    link_icon.setFixedWidth(20)
                    link_icon.setToolTip(f"Linked to launcher: {step.launcher_ref}")
                    rl.addWidget(link_icon)

                path_text = step.path
                if step.args:
                    path_text += f"  {step.args}"
                if len(path_text) > 50:
                    path_text = "..." + path_text[-47:]
                path_lbl = QLabel(path_text)
                path_lbl.setFont(font(11))
                path_lbl.setStyleSheet(f"color: {COLORS['text_dim']};")
                rl.addWidget(path_lbl, stretch=1)

                steps_layout.addWidget(row)

            steps_layout.addStretch()
            scroll.setWidget(steps_w)
            self._wf_detail_layout.addWidget(scroll, stretch=1)
        else:
            empty = QLabel("No steps defined")
            empty.setStyleSheet(f"color: {COLORS['text_dim']};")
            self._wf_detail_layout.addWidget(empty)

        # Linked layout info
        if wf.linked_layout:
            link_lbl = QLabel(f"Linked layout: {wf.linked_layout}  (delay: {wf.layout_delay}s)")
            link_lbl.setFont(font(12))
            link_lbl.setStyleSheet(f"color: {COLORS['text_dim']};")
            self._wf_detail_layout.addWidget(link_lbl)
        else:
            no_link = QLabel("No linked layout")
            no_link.setFont(font(11))
            no_link.setStyleSheet(f"color: {COLORS['text_muted']};")
            self._wf_detail_layout.addWidget(no_link)

    def _update_wf_fav_btn(self):
        name = self._wf_dropdown.currentText()
        if name and name != "(none)" and self.app.is_favorite('workflows', name):
            self._wf_fav_btn.setText("\u2764\ufe0f")
        else:
            self._wf_fav_btn.setText("\U0001f90d")

    def _run_selected_workflow(self):
        name = self._wf_dropdown.currentText()
        if name and name != "(none)":
            self.app.run_workflow(name)

    def _edit_selected_workflow(self):
        name = self._wf_dropdown.currentText()
        if name and name != "(none)":
            wm = self._get_wf_manager()
            if wm:
                wf = wm.get(name)
                if wf:
                    self._open_workflow_dialog(wf)

    def _delete_selected_workflow(self):
        name = self._wf_dropdown.currentText()
        if not name or name == "(none)":
            return
        reply = QMessageBox.question(
            self, "Delete Workflow",
            f"Delete workflow '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            wm = self._get_wf_manager()
            if wm and wm.delete_workflow(name):
                self.app.commands._refresh_workflow_commands()
                self.app.mark_dirty("home", "voice")
                self._refresh_workflow_dropdown()

    def _duplicate_selected_workflow(self):
        name = self._wf_dropdown.currentText()
        if not name or name == "(none)":
            return
        wm = self._get_wf_manager()
        if not wm:
            return
        wf = wm.get(name)
        if not wf:
            return
        import copy
        new_name = _next_name(name, lambda n: wm.get(n) is not None)
        dup = copy.deepcopy(wf)
        dup.name = new_name
        dup.voice_phrase = ""
        wm.save_workflow(dup)
        self.app.commands._refresh_workflow_commands()
        self._refresh_workflow_dropdown()
        self._wf_dropdown.setCurrentText(new_name)
        self.app.mark_dirty("home", "voice")
        self.app.set_status(f"Duplicated as '{new_name}'", COLORS["success"])

    def _toggle_fav_workflow(self):
        name = self._wf_dropdown.currentText()
        if name and name != "(none)":
            self.app.toggle_favorite('workflows', name)
            self._update_wf_fav_btn()

    def _new_workflow(self):
        self._open_workflow_dialog(None)

    def _open_workflow_dialog(self, existing: 'Workflow | None'):
        """Open create/edit workflow dialog."""
        is_edit = existing is not None
        dlg = QDialog(self)
        dlg.setWindowTitle("Edit Workflow" if is_edit else "New Workflow")
        dlg.resize(560, 500)
        dlg.setStyleSheet(f"QDialog {{ background: {COLORS['bg']}; }}")

        main = QVBoxLayout(dlg)
        main.setContentsMargins(12, 10, 12, 10)

        # Name
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Name:"))
        name_entry = QLineEdit()
        name_entry.setPlaceholderText("Workflow name...")
        if is_edit:
            name_entry.setText(existing.name)
        name_row.addWidget(name_entry)
        main.addLayout(name_row)

        # Voice phrase
        vp_row = QHBoxLayout()
        vp_row.addWidget(QLabel("Voice:"))
        vp_entry = QLineEdit()
        vp_entry.setPlaceholderText("Voice phrase (optional)...")
        if is_edit and existing.voice_phrase:
            vp_entry.setText(existing.voice_phrase)
        vp_row.addWidget(vp_entry)
        main.addLayout(vp_row)

        # Steps list (mutable)
        steps_lbl = QLabel("Steps")
        steps_lbl.setFont(font(13, "bold"))
        steps_lbl.setStyleSheet(f"color: {COLORS['text_dim']};")
        main.addWidget(steps_lbl)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        steps_container = QWidget()
        steps_layout = QVBoxLayout(steps_container)
        steps_layout.setContentsMargins(0, 0, 0, 0)
        steps_layout.setSpacing(4)
        scroll.setWidget(steps_container)
        main.addWidget(scroll, stretch=1)

        step_rows = []  # list of dicts with widgets

        def add_step_row(step: 'WorkflowStep | None' = None):
            row_w = QFrame()
            row_w.setStyleSheet(
                f"QFrame {{ background: {COLORS['surface_light']}; "
                f"border-radius: {R['md']}px; }}"
            )
            rl = QHBoxLayout(row_w)
            rl.setContentsMargins(6, 4, 6, 4)

            type_combo = QComboBox()
            type_combo.addItems(["app", "terminal", "url", "folder", "command", "script"])
            type_combo.setFixedWidth(80)
            if step:
                idx = type_combo.findText(step.item_type)
                if idx >= 0:
                    type_combo.setCurrentIndex(idx)
            rl.addWidget(type_combo)

            sname = QLineEdit()
            sname.setPlaceholderText("Name")
            sname.setFixedWidth(100)
            if step:
                sname.setText(step.name)
            rl.addWidget(sname)

            spath = QLineEdit()
            spath.setPlaceholderText("Path / command")
            if step:
                spath.setText(step.path)
            rl.addWidget(spath, stretch=1)

            sargs = QLineEdit()
            sargs.setPlaceholderText("Args")
            sargs.setFixedWidth(80)
            if step and step.args:
                sargs.setText(step.args)
            rl.addWidget(sargs)

            browse_btn = QPushButton("\U0001f4c2")
            browse_btn.setFixedSize(36, 28)

            def do_browse():
                path, _ = QFileDialog.getOpenFileName(dlg, "Select File")
                if path:
                    spath.setText(path)
            browse_btn.clicked.connect(do_browse)
            rl.addWidget(browse_btn)

            del_btn = QPushButton("\u00d7")
            del_btn.setFixedSize(32, 28)
            del_btn.setFont(font(14))
            del_btn.setStyleSheet(f"color: {COLORS['error']};")

            # Linked launcher indicator
            ref = step.launcher_ref if step else None
            if ref:
                link_lbl = QLabel("🔗")
                link_lbl.setFixedWidth(20)
                link_lbl.setToolTip(f"Linked to launcher: {ref}")
                rl.insertWidget(0, link_lbl)

            row_data = {
                "widget": row_w, "type": type_combo, "name": sname,
                "path": spath, "args": sargs, "launcher_ref": ref,
            }

            # Terminal type combo (only shown for terminal type)
            term_combo = QComboBox()
            term_combo.addItems(["powershell", "wsl", "cmd"])
            term_combo.setFixedWidth(90)
            if step and step.terminal_type:
                idx = term_combo.findText(step.terminal_type)
                if idx >= 0:
                    term_combo.setCurrentIndex(idx)
            term_combo.setVisible(type_combo.currentText() == "terminal")
            rl.insertWidget(5, term_combo)
            row_data["terminal_type"] = term_combo

            new_tab_cb = QCheckBox("Tab")
            new_tab_cb.setToolTip("Open in new terminal tab")
            if step:
                new_tab_cb.setChecked(step.new_tab)
            new_tab_cb.setVisible(type_combo.currentText() == "terminal")
            rl.insertWidget(6, new_tab_cb)
            row_data["new_tab"] = new_tab_cb

            def on_type_change(t):
                is_term = t == "terminal"
                term_combo.setVisible(is_term)
                new_tab_cb.setVisible(is_term)
            type_combo.currentTextChanged.connect(on_type_change)

            def do_delete():
                step_rows.remove(row_data)
                row_w.deleteLater()
            del_btn.clicked.connect(do_delete)
            rl.addWidget(del_btn)

            step_rows.append(row_data)
            # Insert before stretch
            idx = steps_layout.count() - 1 if steps_layout.count() > 0 else 0
            steps_layout.insertWidget(idx, row_w)

        # Populate existing steps
        if is_edit:
            for s in existing.steps:
                add_step_row(s)

        steps_layout.addStretch()

        btn_row_steps = QHBoxLayout()
        add_btn = QPushButton("+ Add Step")
        add_btn.setFixedHeight(30)
        add_btn.clicked.connect(lambda: add_step_row())
        btn_row_steps.addWidget(add_btn)

        from_launcher_btn = QPushButton("+ From Launcher")
        from_launcher_btn.setFixedHeight(30)
        from_launcher_btn.setToolTip("Import an existing launcher item as a step")

        def pick_from_launcher():
            all_items = self.app.launcher.get_all_items()
            if not all_items:
                QMessageBox.information(dlg, "No Launchers", "No launcher items to import")
                return

            TYPE_ORDER = ["app", "terminal", "url", "folder"]
            TYPE_LABELS = {"app": "Apps", "terminal": "Terminal", "url": "URLs", "folder": "Folders"}

            all_items.sort(key=lambda i: (
                TYPE_ORDER.index(i.item_type) if i.item_type in TYPE_ORDER else len(TYPE_ORDER),
                i.name.lower()
            ))

            pick_dlg = QDialog(dlg)
            pick_dlg.setWindowTitle("Pick Launcher")
            pick_dlg.resize(380, 380)
            pick_dlg.setStyleSheet(f"QDialog {{ background: {COLORS['bg']}; }}")
            pl = QVBoxLayout(pick_dlg)
            pl.setContentsMargins(8, 8, 8, 8)

            # Filter row
            filter_row = QHBoxLayout()
            pick_search = QLineEdit()
            pick_search.setPlaceholderText("Search...")
            pick_search.setFixedHeight(28)
            filter_row.addWidget(pick_search, stretch=1)

            pick_type_filter = QComboBox()
            pick_type_filter.addItems(["All"] + TYPE_ORDER)
            pick_type_filter.setFixedWidth(90)
            pick_type_filter.setFixedHeight(28)
            filter_row.addWidget(pick_type_filter)
            pl.addLayout(filter_row)

            pick_scroll = QScrollArea()
            pick_scroll.setWidgetResizable(True)
            pick_w = QWidget()
            pick_l = QVBoxLayout(pick_w)
            pick_l.setContentsMargins(4, 4, 4, 4)
            pick_l.setSpacing(2)

            # Build grouped list with section headers
            pick_headers = {}  # type -> header widget
            pick_buttons = []  # list of (widget, item)

            for t in TYPE_ORDER:
                group = [i for i in all_items if i.item_type == t]
                if not group:
                    continue
                header = QLabel(f"  {TYPE_LABELS.get(t, t.title())}  ({len(group)})")
                header.setFixedHeight(24)
                header.setFont(font(11, "bold"))
                header.setStyleSheet(
                    f"background: {COLORS['surface']}; color: {COLORS['text_dim']}; "
                    f"border-radius: {R['sm']}px; padding-left: 6px;"
                )
                pick_l.addWidget(header)
                pick_headers[t] = header

                for item in group:
                    btn = QPushButton(f"{item.name}")
                    btn.setFixedHeight(30)
                    btn.setCursor(Qt.CursorShape.PointingHandCursor)
                    btn.setStyleSheet(
                        f"QPushButton {{ text-align: left; padding-left: 12px; }}"
                        f"QPushButton:hover {{ background: {COLORS['hover']}; }}"
                    )
                    def do_pick(checked, it=item):
                        step = WorkflowStep(
                            name=it.name,
                            item_type=it.item_type,
                            path=it.path,
                            args=it.args,
                            terminal_type=it.terminal_type,
                            new_tab=it.new_tab,
                            launcher_ref=it.name,
                        )
                        add_step_row(step)
                        pick_dlg.accept()
                    btn.clicked.connect(do_pick)
                    pick_l.addWidget(btn)
                    pick_buttons.append((btn, item))

            pick_l.addStretch()
            pick_scroll.setWidget(pick_w)
            pl.addWidget(pick_scroll)

            def apply_pick_filter():
                q = pick_search.text().strip().lower()
                tf = pick_type_filter.currentText()
                visible_counts = {t: 0 for t in pick_headers}
                for btn, item in pick_buttons:
                    show = True
                    if tf != "All" and item.item_type != tf:
                        show = False
                    elif q and q not in f"{item.name} {item.path}".lower():
                        show = False
                    btn.setVisible(show)
                    if show:
                        visible_counts[item.item_type] = visible_counts.get(item.item_type, 0) + 1
                for t, header in pick_headers.items():
                    vis = tf == "All" or tf == t
                    header.setVisible(vis)
                    if vis:
                        label = TYPE_LABELS.get(t, t.title())
                        header.setText(f"  {label}  ({visible_counts.get(t, 0)})")

            pick_search.textChanged.connect(lambda: apply_pick_filter())
            pick_type_filter.currentTextChanged.connect(lambda: apply_pick_filter())

            pick_dlg.exec()

        from_launcher_btn.clicked.connect(pick_from_launcher)
        btn_row_steps.addWidget(from_launcher_btn)
        btn_row_steps.addStretch()
        main.addLayout(btn_row_steps)

        # Linked layout
        link_row = QHBoxLayout()
        link_row.addWidget(QLabel("Linked Layout:"))
        link_combo = QComboBox()
        link_combo.addItem("None")
        for ln in self.app.layout_manager.get_layout_names():
            link_combo.addItem(ln)
        if is_edit and existing.linked_layout:
            idx = link_combo.findText(existing.linked_layout)
            if idx >= 0:
                link_combo.setCurrentIndex(idx)
        link_row.addWidget(link_combo)

        link_row.addWidget(QLabel("Delay:"))
        delay_spin = QSpinBox()
        delay_spin.setRange(1, 30)
        delay_spin.setValue(existing.layout_delay if is_edit else 5)
        delay_spin.setSuffix("s")
        delay_spin.setFixedWidth(60)
        link_row.addWidget(delay_spin)
        link_row.addStretch()
        main.addLayout(link_row)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedSize(90, 34)
        cancel_btn.clicked.connect(dlg.reject)
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.setFixedSize(90, 34)
        save_btn.setProperty("accent", True)

        def do_save():
            wf_name = name_entry.text().strip()
            if not wf_name:
                QMessageBox.warning(dlg, "No Name", "Enter a workflow name")
                return

            wm = self._get_wf_manager()
            if not wm:
                return

            # Check for name conflict (rename case)
            if is_edit and wf_name != existing.name and wm.get(wf_name):
                QMessageBox.warning(dlg, "Name Taken", f"'{wf_name}' already exists")
                return

            steps = []
            for rd in step_rows:
                s = WorkflowStep(
                    name=rd["name"].text().strip() or "Untitled",
                    item_type=rd["type"].currentText(),
                    path=rd["path"].text().strip(),
                    args=rd["args"].text().strip(),
                    terminal_type=rd["terminal_type"].currentText() if rd["type"].currentText() == "terminal" else None,
                    new_tab=rd["new_tab"].isChecked() if rd["type"].currentText() == "terminal" else False,
                    launcher_ref=rd.get("launcher_ref"),
                )
                if s.path:
                    steps.append(s)

            linked = link_combo.currentText()
            if linked == "None":
                linked = ""

            wf = Workflow(
                name=wf_name,
                steps=steps,
                voice_phrase=vp_entry.text().strip(),
                linked_layout=linked,
                layout_delay=delay_spin.value(),
            )

            # If renamed, delete old
            if is_edit and wf_name != existing.name:
                wm.delete_workflow(existing.name)

            wm.save_workflow(wf)
            self.app.commands._refresh_workflow_commands()
            self.app.mark_dirty("home", "voice")
            self._refresh_workflow_dropdown()
            self.app.set_status(f"Workflow '{wf_name}' saved", COLORS["success"])
            dlg.accept()

        save_btn.clicked.connect(do_save)
        btn_row.addWidget(save_btn)
        main.addLayout(btn_row)

        dlg.exec()


def _clear(layout):
    while layout.count():
        child = layout.takeAt(0)
        if child.widget():
            child.widget().deleteLater()
        elif child.layout():
            _clear(child.layout())
