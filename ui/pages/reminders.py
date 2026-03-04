"""Reminders page — Active list + add form (Timer / Alarm / Reminder)."""

import time as _time
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QLineEdit, QScrollArea, QComboBox, QCheckBox,
    QGridLayout,
)
from PyQt6.QtCore import Qt, QTimer

from ui.styles import COLORS, font, R, fmt_time


class RemindersPage(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self._time_labels = []  # (QLabel, entry_id, is_timer, fire_at)
        self._init_ui()
        self._start_ticker()

    def _init_ui(self):
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(8, 8, 8, 8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(4, 4, 4, 4)
        scroll.setWidget(content)
        outer_layout.addWidget(scroll)

        # ── Active section ──
        active_lbl = QLabel("Active")
        active_lbl.setFont(font(11, "bold"))
        active_lbl.setStyleSheet(f"color: {COLORS['text_muted']};")
        layout.addWidget(active_lbl)

        self._list_frame = QFrame()
        self._list_frame.setProperty("section", True)
        self._list_layout = QVBoxLayout(self._list_frame)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(0)
        layout.addWidget(self._list_frame)

        # ── Add New section ──
        add_lbl = QLabel("Add New")
        add_lbl.setFont(font(11, "bold"))
        add_lbl.setStyleSheet(f"color: {COLORS['text_muted']};")
        layout.addWidget(add_lbl)

        add_frame = QFrame()
        add_frame.setProperty("section", True)
        add_layout = QGridLayout(add_frame)
        add_layout.setContentsMargins(12, 12, 12, 12)

        # Row 0: Type + Label
        add_layout.addWidget(self._dim_label("Type"), 0, 0)
        self._type_combo = QComboBox()
        self._type_combo.addItems(["Timer", "Alarm", "Reminder"])
        self._type_combo.setFixedWidth(110)
        self._type_combo.setFixedHeight(30)
        self._type_combo.currentTextChanged.connect(self._on_type_change)
        add_layout.addWidget(self._type_combo, 0, 1)

        add_layout.addWidget(self._dim_label("Label"), 0, 2)
        self._label_entry = QLineEdit()
        self._label_entry.setPlaceholderText("e.g. Focus time")
        self._label_entry.setFixedHeight(30)
        add_layout.addWidget(self._label_entry, 0, 3)
        add_layout.setColumnStretch(3, 1)

        # Row 1: Dynamic fields container
        self._fields_container = QWidget()
        self._fields_layout = QHBoxLayout(self._fields_container)
        self._fields_layout.setContentsMargins(0, 0, 0, 0)
        add_layout.addWidget(self._fields_container, 1, 0, 1, 4)

        # Row 2: Alerts
        alerts_row = QHBoxLayout()
        alerts_row.addWidget(self._dim_label("Alerts"))

        self._alert_sound = QCheckBox("Sound")
        self._alert_sound.setFont(font(12))
        alerts_row.addWidget(self._alert_sound)

        self._alert_tts = QCheckBox("TTS")
        self._alert_tts.setFont(font(12))
        alerts_row.addWidget(self._alert_tts)

        self._alert_tray = QCheckBox("Tray")
        self._alert_tray.setFont(font(12))
        alerts_row.addWidget(self._alert_tray)

        sounds_dir = self.app.reminders.sounds_dir
        mp3s = list(sounds_dir.glob("*.mp3"))
        hint = f"♪ {mp3s[0].name}" if mp3s else "~/.vox/sounds/*(.mp3)"
        hint_lbl = QLabel(f"({hint})")
        hint_lbl.setFont(font(10))
        hint_lbl.setStyleSheet(f"color: {COLORS['text_muted']};")
        alerts_row.addWidget(hint_lbl)
        alerts_row.addStretch()

        alerts_w = QWidget()
        alerts_w.setLayout(alerts_row)
        add_layout.addWidget(alerts_w, 2, 0, 1, 4)

        # Row 3: Add button
        add_btn = QPushButton("+ Add")
        add_btn.setFixedSize(80, 30)
        add_btn.clicked.connect(self._add_from_form)
        add_layout.addWidget(add_btn, 3, 3, alignment=Qt.AlignmentFlag.AlignRight)

        layout.addWidget(add_frame)
        layout.addStretch()

        self._build_timer_fields()
        self.refresh_list()

    def _dim_label(self, text):
        lbl = QLabel(text)
        lbl.setFont(font(12))
        lbl.setStyleSheet(f"color: {COLORS['text_dim']};")
        lbl.setFixedWidth(50)
        return lbl

    # ── Dynamic fields ──

    def _clear_fields(self):
        while self._fields_layout.count():
            child = self._fields_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def _build_timer_fields(self):
        self._clear_fields()
        lbl = self._dim_label("Duration")
        lbl.setFixedWidth(60)
        self._fields_layout.addWidget(lbl)
        self._rem_h = QLineEdit()
        self._rem_h.setPlaceholderText("0h")
        self._rem_h.setFixedWidth(48)
        self._rem_h.setFixedHeight(28)
        self._fields_layout.addWidget(self._rem_h)
        self._rem_m = QLineEdit()
        self._rem_m.setPlaceholderText("25m")
        self._rem_m.setFixedWidth(48)
        self._rem_m.setFixedHeight(28)
        self._fields_layout.addWidget(self._rem_m)
        self._rem_s = QLineEdit()
        self._rem_s.setPlaceholderText("0s")
        self._rem_s.setFixedWidth(48)
        self._rem_s.setFixedHeight(28)
        self._fields_layout.addWidget(self._rem_s)
        self._fields_layout.addStretch()

    def _build_alarm_fields(self):
        self._clear_fields()
        lbl = self._dim_label("Time")
        lbl.setFixedWidth(60)
        self._fields_layout.addWidget(lbl)
        self._rem_time = QLineEdit()
        self._rem_time.setPlaceholderText("e.g. 3:30 PM or 15:30")
        self._rem_time.setFixedHeight(28)
        self._fields_layout.addWidget(self._rem_time, stretch=1)

    def _build_reminder_fields(self):
        self._clear_fields()
        lbl = self._dim_label("Message")
        lbl.setFixedWidth(60)
        self._fields_layout.addWidget(lbl)
        self._rem_msg = QLineEdit()
        self._rem_msg.setPlaceholderText("Reminder text")
        self._rem_msg.setFixedHeight(28)
        self._fields_layout.addWidget(self._rem_msg, stretch=1)
        lbl2 = self._dim_label("Time")
        lbl2.setFixedWidth(40)
        self._fields_layout.addWidget(lbl2)
        self._rem_time = QLineEdit()
        self._rem_time.setPlaceholderText("e.g. 3:30 PM or 15:30")
        self._rem_time.setFixedHeight(28)
        self._fields_layout.addWidget(self._rem_time, stretch=1)

    def _on_type_change(self, t):
        if t == "Timer":
            self._build_timer_fields()
        elif t == "Alarm":
            self._build_alarm_fields()
        else:
            self._build_reminder_fields()

    # ── Add ──

    def _add_from_form(self):
        t = self._type_combo.currentText()
        label = self._label_entry.text().strip() or t
        alerts = {
            "sound": self._alert_sound.isChecked(),
            "tts": self._alert_tts.isChecked(),
            "tray": self._alert_tray.isChecked(),
        }

        if t == "Timer":
            try:
                h = int(self._rem_h.text() or 0)
                m = int(self._rem_m.text() or 0)
                s = int(self._rem_s.text() or 0)
            except ValueError:
                return
            seconds = h * 3600 + m * 60 + s
            if seconds <= 0:
                return
            self.app.reminders.create_timer(label, seconds, alerts=alerts)
            self._rem_h.clear()
            self._rem_m.clear()
            self._rem_s.clear()

        elif t == "Alarm":
            time_str = self._rem_time.text().strip()
            if not time_str:
                return
            entry = self.app.reminders.create_alarm(label, time_str, alerts=alerts)
            if entry is None:
                self._rem_time.setStyleSheet(f"border-color: {COLORS['error']};")
                return
            self._rem_time.setStyleSheet("")
            self._rem_time.clear()

        else:  # Reminder
            msg = self._rem_msg.text().strip()
            time_str = self._rem_time.text().strip()
            if not time_str:
                return
            entry = self.app.reminders.create_reminder(label, msg or label, time_str, alerts=alerts)
            if entry is None:
                self._rem_time.setStyleSheet(f"border-color: {COLORS['error']};")
                return
            self._rem_time.setStyleSheet("")
            self._rem_msg.clear()
            self._rem_time.clear()

        self._label_entry.clear()
        self.refresh_list()

    # ── Active list ──

    def refresh_list(self):
        _clear(self._list_layout)
        self._time_labels = []

        active = self.app.reminders.get_active()
        if not active:
            lbl = QLabel("No active timers or reminders")
            lbl.setFont(font(12))
            lbl.setStyleSheet(f"color: {COLORS['text_muted']};")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._list_layout.addWidget(lbl)
            return

        TYPE_ICON = {"timer": "⏱", "alarm": "⏰", "reminder": "🔔"}
        now = _time.time()

        for i, entry in enumerate(active):
            if i > 0:
                sep = QFrame()
                sep.setFixedHeight(1)
                sep.setStyleSheet(f"background: {COLORS['border']};")
                self._list_layout.addWidget(sep)

            row = QHBoxLayout()
            row.setContentsMargins(10, 10, 6, 10)

            icon = QLabel(TYPE_ICON.get(entry.type, "•"))
            icon.setFont(font(14))
            icon.setStyleSheet(f"color: {COLORS['text_dim']};")
            icon.setFixedWidth(28)
            row.addWidget(icon)

            name = QLabel(entry.label)
            name.setFont(font(12))
            row.addWidget(name)

            row.addStretch()

            if entry.type == "timer":
                remaining = max(0, entry.fire_at - now)
                time_text = self._format_countdown(remaining)
            else:
                fire_dt = datetime.fromtimestamp(entry.fire_at)
                time_text = fmt_time(fire_dt, seconds=False)

            time_lbl = QLabel(time_text)
            time_lbl.setFont(font(12))
            time_lbl.setStyleSheet(f"color: {COLORS['text_dim']};")
            row.addWidget(time_lbl)

            self._time_labels.append((time_lbl, entry.id, entry.type == "timer", entry.fire_at))

            # Alert badges
            alerts = entry.alerts if isinstance(entry.alerts, dict) else {}
            badges = ""
            if alerts.get("sound"):
                badges += "♪"
            if alerts.get("tts"):
                badges += "T"
            if alerts.get("tray"):
                badges += "⬝"
            if badges:
                badge_lbl = QLabel(badges)
                badge_lbl.setFont(font(10))
                badge_lbl.setStyleSheet(f"color: {COLORS['text_muted']};")
                row.addWidget(badge_lbl)

            cancel_btn = QPushButton("×")
            cancel_btn.setFixedSize(28, 28)
            cancel_btn.setProperty("flat", True)
            cancel_btn.setStyleSheet(f"QPushButton:hover {{ color: {COLORS['error']}; }}")
            cancel_btn.clicked.connect(lambda _, eid=entry.id: self._cancel(eid))
            row.addWidget(cancel_btn)

            row_w = QWidget()
            row_w.setLayout(row)
            self._list_layout.addWidget(row_w)

    def _cancel(self, eid):
        self.app.reminders.cancel(eid)
        self.refresh_list()

    def _format_countdown(self, remaining):
        remaining = max(0, int(remaining))
        h = remaining // 3600
        m = (remaining % 3600) // 60
        s = remaining % 60
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"

    # ── Ticker ──

    def _start_ticker(self):
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)

    def _tick(self):
        now = _time.time()
        for lbl, eid, is_timer, fire_at in self._time_labels:
            if is_timer:
                remaining = max(0, fire_at - now)
                lbl.setText(self._format_countdown(remaining))


def _clear(layout):
    while layout.count():
        child = layout.takeAt(0)
        if child.widget():
            child.widget().deleteLater()
        elif child.layout():
            _clear(child.layout())
