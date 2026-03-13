"""Floating widget — always-on-top, frameless, draggable, collapsible sections."""

import time as _time
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QApplication,
)
from PyQt6.QtCore import Qt, QPoint, QTimer

from ui.styles import COLORS, font, R, WIDGET_WIDTHS, _ui_scale_factor


class FloatingWidget(QWidget):
    MAX_H = 500

    def __init__(self, voice_toggle_cb, show_main_cb, get_actions_cb=None,
                 widget_size="Medium", dismiss_reminder_cb=None):
        super().__init__()
        self.voice_toggle = voice_toggle_cb
        self.show_main = show_main_cb
        self.get_actions = get_actions_cb
        self._dismiss_cb = dismiss_reminder_cb
        base_width = WIDGET_WIDTHS.get(widget_size, 320)
        self._width = int(base_width * _ui_scale_factor)

        self._status_expanded = False
        self._reminders_expanded = False
        self._layouts_expanded = False
        self._launchers_expanded = False
        self._drag_pos = None

        # Window flags
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(self._width)
        self.setMinimumHeight(int(200 * _ui_scale_factor))

        # Position top-right
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            self.move(geo.right() - self._width - 20, geo.top() + 10)

        self._build_ui()
        self._update_size()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)

        # Container with rounded border
        self.container = QFrame()
        self.container.setStyleSheet(
            f"QFrame#widget_container {{ background: #18181b; "
            f"border: 1px solid {COLORS['border']}; border-radius: 14px; }}"
        )
        self.container.setObjectName("widget_container")
        c_layout = QVBoxLayout(self.container)
        c_layout.setContentsMargins(6, 6, 6, 10)
        c_layout.setSpacing(2)
        outer.addWidget(self.container)

        # Top bar
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)

        self.mic_btn = QPushButton("MIC")
        self.mic_btn.setFixedSize(72, 26)
        self.mic_btn.setFont(font(11, "bold"))
        self.mic_btn.setStyleSheet(
            f"background: {COLORS['surface_light']}; color: {COLORS['text']}; "
            f"border-radius: {R['md']}px; border: none;"
        )
        self.mic_btn.clicked.connect(self.voice_toggle)
        top_bar.addWidget(self.mic_btn)

        title = QLabel("vox")
        title.setFont(font(21, "bold"))
        title.setStyleSheet(
            f"color: {COLORS['text']}; letter-spacing: 4px;"
        )
        top_bar.addWidget(title)

        top_bar.addStretch()

        show_btn = QPushButton("⊞")
        show_btn.setFixedSize(24, 24)
        show_btn.setFont(font(12))
        show_btn.setStyleSheet(
            f"background: transparent; border: none; color: {COLORS['text_dim']};"
        )
        show_btn.clicked.connect(self.show_main)
        top_bar.addWidget(show_btn)

        close_btn = QPushButton("×")
        close_btn.setFixedSize(24, 24)
        close_btn.setFont(font(14))
        close_btn.setStyleSheet(
            f"QPushButton {{ background: #3d1a1a; border: none; color: {COLORS['error']}; border-radius: 4px; }}"
            f"QPushButton:hover {{ background: {COLORS['error']}; color: {COLORS['text']}; }}"
        )
        close_btn.clicked.connect(self.hide)
        top_bar.addWidget(close_btn)

        c_layout.addLayout(top_bar)

        # Separator
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {COLORS['border']};")
        c_layout.addWidget(sep)

        # Scrollable body
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._body = QWidget()
        self._body_layout = QVBoxLayout(self._body)
        self._body_layout.setContentsMargins(2, 0, 2, 0)
        self._body_layout.setSpacing(0)
        scroll.setWidget(self._body)
        c_layout.addWidget(scroll, stretch=1)

        # -- Status section --
        self._status_header = self._section_header("Status", "status")
        self._body_layout.addWidget(self._status_header)
        self._status_content = QWidget()
        sc_layout = QVBoxLayout(self._status_content)
        sc_layout.setContentsMargins(6, 2, 6, 6)
        sc_layout.setSpacing(4)

        self.status_label = QLabel("Ready")
        self.status_label.setFont(font(12))
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet(
            f"color: {COLORS['text_dim']}; "
            f"background: {COLORS['surface']}; "
            f"border-radius: 5px; padding: 4px 6px;"
        )
        sc_layout.addWidget(self.status_label)

        self.tts_label = QLabel("")
        self.tts_label.setFont(font(11))
        self.tts_label.setWordWrap(True)
        self.tts_label.setStyleSheet(
            f"color: {COLORS['success']}; "
            f"background: transparent; "
            f"border-left: 2px solid {COLORS['success']}; "
            f"padding: 2px 6px;"
        )
        self.tts_label.hide()
        sc_layout.addWidget(self.tts_label)

        # action_label kept for API compat but not shown
        self.action_label = QLabel("")
        self.action_label.hide()

        self._status_content.hide()
        self._body_layout.addWidget(self._status_content)

        # -- Reminders section --
        self._reminders_header = self._section_header("Reminders", "reminders")
        self._body_layout.addWidget(self._reminders_header)
        self._reminders_content = QWidget()
        self._reminders_content_layout = QVBoxLayout(self._reminders_content)
        self._reminders_content_layout.setContentsMargins(6, 2, 6, 6)
        self._reminders_content_layout.setSpacing(2)
        self._reminders_content.hide()
        self._body_layout.addWidget(self._reminders_content)

        self._rem_entries = []
        self._rem_time_labels = []
        self._rem_ticker = QTimer(self)
        self._rem_ticker.timeout.connect(self._tick_reminders)
        self._rem_ticker.start(1000)

        # -- Layouts section --
        self._layouts_header = self._section_header("Layouts", "layouts")
        self._body_layout.addWidget(self._layouts_header)
        self._layouts_content = QWidget()
        self._layouts_content_layout = QGridLayout(self._layouts_content)
        self._layouts_content_layout.setContentsMargins(2, 0, 2, 4)
        self._layouts_content_layout.setSpacing(2)
        self._layouts_content_layout.setColumnStretch(0, 1)
        self._layouts_content_layout.setColumnStretch(1, 1)
        self._layouts_content.hide()
        self._body_layout.addWidget(self._layouts_content)

        # -- Launchers section --
        self._launchers_header = self._section_header("Launchers", "launchers")
        self._body_layout.addWidget(self._launchers_header)
        self._launchers_content = QWidget()
        self._launchers_content_layout = QGridLayout(self._launchers_content)
        self._launchers_content_layout.setContentsMargins(2, 0, 2, 4)
        self._launchers_content_layout.setSpacing(2)
        self._launchers_content_layout.setColumnStretch(0, 1)
        self._launchers_content_layout.setColumnStretch(1, 1)
        self._launchers_content.hide()
        self._body_layout.addWidget(self._launchers_content)

        self._body_layout.addStretch()

    def _section_header(self, label, section):
        btn = QPushButton(f"▸  {label}")
        btn.setFont(font(12))
        btn.setStyleSheet(
            f"text-align: left; background: transparent; border: none; "
            f"color: {COLORS['text_dim']}; padding: 4px 4px;"
        )
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedHeight(28)
        btn.clicked.connect(lambda: self._toggle_section(section))
        return btn

    # ── Sections ──

    def _toggle_section(self, section):
        attr = f"_{section}_expanded"
        header = getattr(self, f"_{section}_header")
        content = getattr(self, f"_{section}_content")
        label = {"status": "Status", "reminders": "Reminders", "layouts": "Layouts", "launchers": "Launchers"}[section]

        expanded = not getattr(self, attr)
        setattr(self, attr, expanded)
        header.setText(f"{'▾' if expanded else '▸'}  {label}")
        content.setVisible(expanded)

        if expanded:
            if section == "reminders":
                self._refresh_reminders()
            elif section == "layouts":
                self._refresh_layouts()
            elif section == "launchers":
                self._refresh_launchers()

        self._update_size()

    def _update_size(self):
        self.setMaximumHeight(self.MAX_H)
        self.adjustSize()

    # ── Action lists ──

    def _build_action_list(self, parent_layout, items, empty_msg):
        _clear(parent_layout)
        if not items:
            lbl = QLabel(empty_msg)
            lbl.setFont(font(11))
            lbl.setStyleSheet(f"color: {COLORS['text_muted']};")
            parent_layout.addWidget(lbl, 0, 0, 1, 2)
        else:
            for i, (name, callback) in enumerate(items):
                btn = QPushButton(name)
                btn.setFixedHeight(28)
                btn.setFont(font(11))
                btn.setStyleSheet(
                    f"text-align: left; background: {COLORS['surface_light']}; "
                    f"color: {COLORS['text']}; border-radius: {R['md']}px; "
                    f"padding: 2px 8px; border: none;"
                )
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.clicked.connect(lambda _, cb=callback: cb())
                parent_layout.addWidget(btn, i // 2, i % 2)
        self._update_size()

    def _refresh_layouts(self):
        if not self.get_actions:
            return
        actions = self.get_actions()
        self._build_action_list(
            self._layouts_content_layout,
            actions.get("layouts", []),
            "No favorited layouts"
        )

    def _refresh_launchers(self):
        if not self.get_actions:
            return
        actions = self.get_actions()
        self._build_action_list(
            self._launchers_content_layout,
            actions.get("launchers", []),
            "No favorited launchers"
        )

    def refresh_actions(self):
        if self._reminders_expanded:
            self._refresh_reminders()
        if self._layouts_expanded:
            self._refresh_layouts()
        if self._launchers_expanded:
            self._refresh_launchers()

    # ── Reminders ──

    def update_reminders(self, entries):
        """Called by app.push_reminders_to_ui() with active reminder entries."""
        self._rem_entries = entries
        # Update header with count
        now = _time.time()
        triggered = [e for e in entries if getattr(e, 'triggered', False)]
        pending = [e for e in entries if not getattr(e, 'recur', None) and not getattr(e, 'fired', False) and e.fire_at <= now + 86400]
        fired = [e for e in entries if not getattr(e, 'recur', None) and getattr(e, 'fired', False)]
        count = len(triggered) + len(pending) + len(fired)
        label = f"Reminders ({count})" if count else "Reminders"
        arrow = "▾" if self._reminders_expanded else "▸"
        self._reminders_header.setText(f"{arrow}  {label}")
        if self._reminders_expanded:
            self._refresh_reminders()

    def _refresh_reminders(self):
        _clear(self._reminders_content_layout)
        entries = self._rem_entries

        triggered = [e for e in entries if getattr(e, 'triggered', False)]
        now = _time.time()
        pending = [e for e in entries if not getattr(e, 'recur', None) and not getattr(e, 'fired', False) and e.fire_at <= now + 86400]
        fired = [e for e in entries if not getattr(e, 'recur', None) and getattr(e, 'fired', False)]

        items = triggered + sorted(pending, key=lambda e: e.fire_at) + fired
        if not items:
            lbl = QLabel("No active reminders")
            lbl.setFont(font(11))
            lbl.setStyleSheet(f"color: {COLORS['text_muted']};")
            self._reminders_content_layout.addWidget(lbl)
            self._update_size()
            return

        self._rem_time_labels = []
        for entry in items[:5]:
            row = QHBoxLayout()
            row.setContentsMargins(2, 2, 2, 2)
            row.setSpacing(6)

            is_triggered = getattr(entry, 'triggered', False)
            is_fired = getattr(entry, 'fired', False)
            is_alert = is_triggered or is_fired
            icon = "⚠️" if is_alert else {"timer": "⏱️", "reminder": "📌"}.get(entry.type, "🔔")
            dot = QLabel(icon)
            dot.setFont(font(10))
            dot.setFixedWidth(18)
            row.addWidget(dot)

            name = QLabel(entry.label)
            name.setFont(font(11))
            name.setStyleSheet(f"color: {COLORS['warning'] if is_alert else COLORS['text']};")
            row.addWidget(name)
            row.addStretch()

            if is_triggered:
                dismiss_btn = QPushButton("✓")
                dismiss_btn.setFixedSize(24, 20)
                dismiss_btn.setFont(font(10))
                dismiss_btn.setStyleSheet(
                    f"QPushButton {{ background: transparent; border: 1px solid {COLORS['border']}; "
                    f"border-radius: 3px; color: {COLORS['text_dim']}; padding: 0; }}"
                    f"QPushButton:hover {{ border-color: {COLORS['success']}; color: {COLORS['success']}; }}"
                )
                dismiss_btn.clicked.connect(lambda _, eid=entry.id: self._dismiss_reminder(eid))
                row.addWidget(dismiss_btn)
            elif is_fired:
                done_lbl = QLabel("Done")
                done_lbl.setFont(font(10))
                done_lbl.setStyleSheet(f"color: {COLORS['warning']};")
                row.addWidget(done_lbl)
            else:
                now = _time.time()
                if entry.type == "timer":
                    remaining = max(0, entry.fire_at - now)
                    time_text = _fmt_countdown(remaining)
                else:
                    from datetime import datetime
                    time_text = datetime.fromtimestamp(entry.fire_at).strftime("%I:%M %p").lstrip("0")
                time_lbl = QLabel(time_text)
                time_lbl.setFont(font(10))
                time_lbl.setStyleSheet(f"color: {COLORS['text_dim']};")
                row.addWidget(time_lbl)
                if entry.type == "timer":
                    self._rem_time_labels.append((time_lbl, entry.fire_at))

            rw = QWidget()
            rw.setLayout(row)
            self._reminders_content_layout.addWidget(rw)

        if len(items) > 5:
            more = QLabel(f"+{len(items) - 5} more")
            more.setFont(font(10))
            more.setStyleSheet(f"color: {COLORS['text_muted']};")
            self._reminders_content_layout.addWidget(more)

        self._update_size()

    def _dismiss_reminder(self, eid):
        """Dismiss from widget — needs app reference."""
        if self._dismiss_cb:
            self._dismiss_cb(eid)

    def _tick_reminders(self):
        if not self._reminders_expanded or not hasattr(self, '_rem_time_labels'):
            return
        now = _time.time()
        for lbl, fire_at in self._rem_time_labels:
            remaining = max(0, fire_at - now)
            lbl.setText(_fmt_countdown(remaining))
            if remaining <= 60:
                lbl.setStyleSheet(f"color: {COLORS['error']}; font-weight: bold;")
            elif remaining <= 300:
                lbl.setStyleSheet(f"color: {COLORS['warning']};")

    # ── Resize ──

    def resize_to(self, size: str):
        from ui.styles import WIDGET_WIDTHS, _ui_scale_factor
        base_width = WIDGET_WIDTHS.get(size, 215)
        self._width = int(base_width * _ui_scale_factor)
        self.setFixedWidth(self._width)
        self._update_size()

    # ── Status updates ──

    def set_recording(self, is_recording: bool):
        if is_recording:
            self.mic_btn.setStyleSheet(
                f"background: {COLORS['error']}; color: {COLORS['text']}; "
                f"border-radius: {R['md']}px; border: 2px solid #ff9999; font-weight: bold;"
            )
            self.mic_btn.setText("● REC")
        else:
            self.mic_btn.setStyleSheet(
                f"background: {COLORS['surface_light']}; color: {COLORS['text']}; "
                f"border-radius: {R['md']}px; border: none;"
            )
            self.mic_btn.setText("MIC")

    def set_status(self, text: str, color: str = None):
        c = color or COLORS['text_dim']
        self.status_label.setText(text)
        self.status_label.setStyleSheet(
            f"color: {c}; "
            f"background: {COLORS['surface']}; "
            f"border-radius: 5px; padding: 4px 6px;"
        )

    def set_tts_response(self, text: str):
        if text:
            self.tts_label.setText(text)
            self.tts_label.show()
        else:
            self.tts_label.hide()

    def set_action(self, text: str):
        self.action_label.setText(text[:40])

    # ── Drag ──

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def mouseDoubleClickEvent(self, event):
        self.show_main()


def _fmt_countdown(remaining):
    remaining = max(0, int(remaining))
    h = remaining // 3600
    m = (remaining % 3600) // 60
    s = remaining % 60
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _clear(layout):
    while layout.count():
        child = layout.takeAt(0)
        if child.widget():
            child.widget().deleteLater()
        elif child.layout():
            _clear(child.layout())
