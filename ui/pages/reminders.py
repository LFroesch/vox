"""Reminders page — clean timer/reminder UI with expandable rows."""

import time as _time
from datetime import datetime, timedelta

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QLineEdit, QScrollArea, QComboBox, QCheckBox,
    QDateEdit, QTimeEdit, QDialog, QDialogButtonBox,
    QSizePolicy, QGraphicsOpacityEffect,
)
from PyQt6.QtCore import Qt, QTimer, QDate, QTime, QEvent
from PyQt6.QtGui import QPainter

from ui.styles import COLORS, font, R, fmt_time


class _ElidedLabel(QLabel):
    """QLabel that elides text with '...' when too long."""
    is_elided = False

    def minimumSizeHint(self):
        sh = super().minimumSizeHint()
        return sh.__class__(0, sh.height())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setFont(self.font())
        painter.setPen(self.palette().windowText().color())
        elided = painter.fontMetrics().elidedText(
            self.text(), Qt.TextElideMode.ElideRight, self.width()
        )
        self.is_elided = (elided != self.text())
        painter.drawText(
            self.rect(),
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
            elided,
        )


class _HoverRow(QWidget):
    """Row widget that dims action buttons until hover."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._action_btns = []
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

    def add_action(self, btn):
        self._action_btns.append(btn)
        eff = QGraphicsOpacityEffect()
        eff.setOpacity(0.0)
        btn.setGraphicsEffect(eff)

    def enterEvent(self, event):
        for btn in self._action_btns:
            eff = btn.graphicsEffect()
            if eff:
                eff.setOpacity(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        for btn in self._action_btns:
            eff = btn.graphicsEffect()
            if eff:
                eff.setOpacity(0.0)
        super().leaveEvent(event)


class _ExpandableRow(QWidget):
    """Wrapper: clickable header row + collapsible detail panel."""

    def __init__(self, header_widget, detail_text="", parent=None):
        super().__init__(parent)
        self._expanded = False
        self._header_elided_label = None  # set via set_elided_label()
        self._full_label_widget = None
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Make header clickable
        self._header = header_widget
        self._header.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(self._header)

        # Detail panel (hidden by default)
        self._detail = QWidget()
        detail_layout = QVBoxLayout(self._detail)
        detail_layout.setContentsMargins(46, 0, 12, 10)
        detail_layout.setSpacing(4)
        if detail_text:
            detail_lbl = QLabel(detail_text)
            detail_lbl.setFont(font(11))
            detail_lbl.setStyleSheet(f"color: {COLORS['text_dim']};")
            detail_lbl.setWordWrap(True)
            detail_layout.addWidget(detail_lbl)
        self._detail_layout = detail_layout
        self._detail.setVisible(False)
        layout.addWidget(self._detail)

    def set_elided_label(self, elided_label):
        """Register the header's _ElidedLabel so expand can show full text when truncated."""
        self._header_elided_label = elided_label
        # Pre-create full label widget at top of detail panel (hidden until needed)
        self._full_label_widget = QLabel(elided_label.text())
        self._full_label_widget.setFont(font(12, "bold"))
        self._full_label_widget.setStyleSheet(f"color: {COLORS['text']};")
        self._full_label_widget.setWordWrap(True)
        self._full_label_widget.setVisible(False)
        self._detail_layout.insertWidget(0, self._full_label_widget)

    def add_detail_line(self, text, color=None, bold=False):
        lbl = QLabel(text)
        lbl.setFont(font(12 if bold else 10, "bold" if bold else "normal"))
        lbl.setStyleSheet(f"color: {color or COLORS['text_muted']};")
        lbl.setWordWrap(True)
        self._detail_layout.addWidget(lbl)

    def mousePressEvent(self, event):
        # Only toggle if clicking the header area (not buttons)
        if event.button() == Qt.MouseButton.LeftButton:
            child = self._header.childAt(self._header.mapFromGlobal(event.globalPosition().toPoint()))
            if isinstance(child, QPushButton):
                return super().mousePressEvent(event)
            self._expanded = not self._expanded
            self._detail.setVisible(self._expanded)
            # Update arrow if present
            if hasattr(self, '_arrow'):
                self._arrow.setText("▾" if self._expanded else "▸")
            # Swap truncated header label ↔ full detail label
            if self._header_elided_label and self._full_label_widget:
                if self._expanded and self._header_elided_label.is_elided:
                    self._header_elided_label.setVisible(False)
                    self._full_label_widget.setVisible(True)
                else:
                    self._header_elided_label.setVisible(True)
                    self._full_label_widget.setVisible(False)
        super().mousePressEvent(event)


class RemindersPage(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self._time_labels = []
        self._form_visible = False
        self._init_ui()
        self._start_ticker()

    def _init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        self._root = QVBoxLayout(content)
        self._root.setContentsMargins(16, 12, 16, 16)
        self._root.setSpacing(14)
        scroll.setWidget(content)
        outer.addWidget(scroll)

        # ── Expired / Triggered ───────────────────────────────────────
        exp_hdr = QHBoxLayout()
        exp_hdr.setContentsMargins(0, 0, 0, 0)
        exp_hdr.addWidget(_section_label("EXPIRED"))
        exp_hdr.addStretch()
        self._clear_all_btn = QPushButton("Clear all")
        self._clear_all_btn.setFixedSize(72, 26)
        self._clear_all_btn.setFont(font(9))
        self._clear_all_btn.setStyleSheet(
            f"color: {COLORS['text_muted']}; background: transparent; "
            f"border: 1px solid {COLORS['border']}; border-radius: 3px;"
        )
        self._clear_all_btn.clicked.connect(self._clear_all_expired)
        self._clear_all_btn.setVisible(False)
        exp_hdr.addWidget(self._clear_all_btn)
        self._expired_header = QWidget(); self._expired_header.setLayout(exp_hdr)
        self._root.addWidget(self._expired_header)
        self._expired_frame = QFrame()
        self._expired_frame.setProperty("section", True)
        self._expired_layout = QVBoxLayout(self._expired_frame)
        self._expired_layout.setContentsMargins(0, 0, 0, 0)
        self._expired_layout.setSpacing(0)
        self._root.addWidget(self._expired_frame)

        # ── Next 24 Hours (non-recurring) ─────────────────────────────
        self._upcoming_header = _section_label("NEXT 24 HOURS")
        self._root.addWidget(self._upcoming_header)
        self._upcoming_frame = QFrame()
        self._upcoming_frame.setProperty("section", True)
        self._upcoming_layout = QVBoxLayout(self._upcoming_frame)
        self._upcoming_layout.setContentsMargins(0, 0, 0, 0)
        self._upcoming_layout.setSpacing(0)
        self._root.addWidget(self._upcoming_frame)

        # ── Tabs: Scheduled | Recurring ───────────────────────────────
        self._active_tab = 0
        self._tab_bar = QWidget()
        tab_h = QHBoxLayout(self._tab_bar)
        tab_h.setContentsMargins(0, 0, 0, 0)
        tab_h.setSpacing(0)
        self._tab_sched_btn = QPushButton("Scheduled")
        self._tab_recur_btn = QPushButton("Recurring")
        for btn in (self._tab_sched_btn, self._tab_recur_btn):
            btn.setFixedHeight(30)
            btn.setFont(font(10, "bold"))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._tab_sched_btn.clicked.connect(lambda: self._switch_tab(0))
        self._tab_recur_btn.clicked.connect(lambda: self._switch_tab(1))
        tab_h.addWidget(self._tab_sched_btn)
        tab_h.addWidget(self._tab_recur_btn)
        tab_h.addStretch()
        self._root.addWidget(self._tab_bar)

        self._tab_frame = QFrame()
        self._tab_frame.setProperty("section", True)
        self._tab_layout = QVBoxLayout(self._tab_frame)
        self._tab_layout.setContentsMargins(0, 0, 0, 0)
        self._tab_layout.setSpacing(0)
        self._root.addWidget(self._tab_frame)

        # ── New button / form ─────────────────────────────────────────
        self._new_btn = QPushButton("+ New")
        self._new_btn.setFixedHeight(36)
        self._new_btn.setFont(font(11))
        self._new_btn.setProperty("accent", True)
        self._new_btn.clicked.connect(self._toggle_form)
        self._root.addWidget(self._new_btn)

        self._form_frame = self._build_form()
        self._form_frame.setVisible(False)
        self._root.addWidget(self._form_frame)

        self._root.addStretch()
        self._build_timer_fields()
        self.refresh_list()

    # ── Form ──────────────────────────────────────────────────────────

    def _build_form(self):
        frame = QFrame()
        frame.setProperty("section", True)
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(14, 14, 14, 14)
        fl.setSpacing(10)

        # Type
        r1 = QHBoxLayout()
        r1.setSpacing(8)
        r1.addWidget(_field_label("Type"))
        self._type_combo = QComboBox()
        self._type_combo.addItems(["Timer", "Reminder", "Recurring"])
        self._type_combo.setFixedHeight(30)
        self._type_combo.setFixedWidth(120)
        self._type_combo.currentTextChanged.connect(self._on_type_change)
        r1.addWidget(self._type_combo)
        r1.addStretch()
        fl.addLayout(r1)

        # Label
        r2 = QHBoxLayout()
        r2.setSpacing(8)
        r2.addWidget(_field_label("Label"))
        self._label_entry = QLineEdit()
        self._label_entry.setPlaceholderText("e.g. Focus time")
        self._label_entry.setFixedHeight(30)
        r2.addWidget(self._label_entry)
        fl.addLayout(r2)

        # Dynamic fields
        self._fields_container = QWidget()
        self._fields_layout = QVBoxLayout(self._fields_container)
        self._fields_layout.setContentsMargins(0, 0, 0, 0)
        self._fields_layout.setSpacing(12)
        fl.addWidget(self._fields_container)

        # Buttons
        r4 = QHBoxLayout()
        r4.setSpacing(8)
        cancel = QPushButton("Cancel")
        cancel.setFixedSize(72, 32)
        cancel.setFont(font(11))
        cancel.clicked.connect(self._toggle_form)
        r4.addWidget(cancel)
        r4.addStretch()
        add = QPushButton("Add")
        add.setFixedSize(72, 32)
        add.setFont(font(11))
        add.setProperty("accent", True)
        add.clicked.connect(self._add_from_form)
        r4.addWidget(add)
        fl.addLayout(r4)

        return frame

    def _toggle_form(self):
        self._form_visible = not self._form_visible
        self._form_frame.setVisible(self._form_visible)
        self._new_btn.setVisible(not self._form_visible)

    # ── Dynamic form fields ───────────────────────────────────────────

    def _clear_fields(self):
        while self._fields_layout.count():
            child = self._fields_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
            elif child.layout():
                _clear_layout(child.layout())

    def _hrow(self):
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)
        return w, h

    def _build_timer_fields(self):
        self._clear_fields()
        row, h = self._hrow()
        h.addWidget(_field_label("Duration"))
        self._rem_h = QLineEdit(); self._rem_h.setPlaceholderText("0h"); self._rem_h.setFixedWidth(48); self._rem_h.setFixedHeight(28)
        self._rem_m = QLineEdit(); self._rem_m.setPlaceholderText("0m"); self._rem_m.setFixedWidth(48); self._rem_m.setFixedHeight(28)
        self._rem_s = QLineEdit(); self._rem_s.setPlaceholderText("0s"); self._rem_s.setFixedWidth(48); self._rem_s.setFixedHeight(28)
        for w in (self._rem_h, self._rem_m, self._rem_s):
            h.addWidget(w)
        h.addStretch()
        self._fields_layout.addWidget(row)

        # Quick presets
        preset_row, ph = self._hrow()
        ph.addWidget(_field_label("Quick"))
        preset_ss = (
            f"QPushButton {{ color: {COLORS['text_dim']}; background: {COLORS['surface_light']}; "
            f"border: 1px solid {COLORS['border']}; border-radius: 12px; padding: 2px 10px; }}"
            f"QPushButton:hover {{ color: {COLORS['text']}; border-color: {COLORS['text_dim']}; }}"
        )
        for label, mins in [("5m", 5), ("15m", 15), ("30m", 30), ("1h", 60)]:
            btn = QPushButton(label)
            btn.setFixedSize(44, 24)
            btn.setFont(font(10))
            btn.setStyleSheet(preset_ss)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, m=mins: self._fill_timer_preset(m))
            ph.addWidget(btn)
        ph.addStretch()
        self._fields_layout.addWidget(preset_row)

        msg_row, mh = self._hrow()
        mh.addWidget(_field_label("Message"))
        self._timer_msg = QLineEdit()
        self._timer_msg.setPlaceholderText("Optional context (shown on expand)")
        self._timer_msg.setFixedHeight(28)
        mh.addWidget(self._timer_msg, stretch=1)
        self._fields_layout.addWidget(msg_row)

    def _build_reminder_fields(self):
        self._clear_fields()
        r0, h0 = self._hrow()
        h0.addWidget(_field_label("Message"))
        self._rem_msg = QLineEdit()
        self._rem_msg.setPlaceholderText("Reminder text")
        self._rem_msg.setFixedHeight(28)
        h0.addWidget(self._rem_msg, stretch=1)
        self._fields_layout.addWidget(r0)

        r1, h1 = self._hrow()
        h1.addWidget(_field_label("Date"))
        self._rem_date = self._date_picker()
        h1.addWidget(self._rem_date)
        for b in self._date_quick_btns(self._rem_date):
            h1.addWidget(b)
        h1.addStretch()
        self._fields_layout.addWidget(r1)

        r2, h2 = self._hrow()
        h2.addWidget(_field_label("Time"))
        self._rem_time = self._time_picker()
        h2.addWidget(self._rem_time)
        h2.addStretch()
        self._fields_layout.addWidget(r2)

    def _build_recurring_fields(self):
        self._clear_fields()
        r1, h1 = self._hrow()
        h1.addWidget(_field_label("Repeat"))
        self._recur_type_combo = QComboBox()
        self._recur_type_combo.addItems(["Daily", "Weekdays", "Weekends", "Weekly", "Interval"])
        self._recur_type_combo.setFixedWidth(110)
        self._recur_type_combo.setFixedHeight(28)
        self._recur_type_combo.currentTextChanged.connect(self._on_recur_subtype_change)
        h1.addWidget(self._recur_type_combo)
        h1.addStretch()
        self._fields_layout.addWidget(r1)

        self._recur_dyn_widget = QWidget()
        self._recur_dyn_layout = QHBoxLayout(self._recur_dyn_widget)
        self._recur_dyn_layout.setContentsMargins(0, 0, 0, 0)
        self._recur_dyn_layout.setSpacing(8)
        self._fields_layout.addWidget(self._recur_dyn_widget)

        self._recur_days_widget, h_days = self._hrow()
        h_days.addWidget(_field_label("Days"))
        self._day_checks = []
        for i, day in enumerate(["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]):
            cb = QCheckBox(day)
            cb.setFont(font(10))
            cb.setChecked(i < 5)
            h_days.addWidget(cb)
            self._day_checks.append(cb)
        h_days.addStretch()
        self._recur_days_widget.setVisible(False)
        self._fields_layout.addWidget(self._recur_days_widget)

        self._build_recur_time_fields()

    def _clear_recur_dyn(self):
        while self._recur_dyn_layout.count():
            child = self._recur_dyn_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def _build_recur_time_fields(self):
        self._clear_recur_dyn()
        self._recur_dyn_layout.addWidget(_field_label("Time"))
        self._recur_time = self._time_picker()
        self._recur_dyn_layout.addWidget(self._recur_time)
        self._recur_dyn_layout.addStretch()

    def _build_recur_interval_fields(self):
        self._clear_recur_dyn()
        self._recur_dyn_layout.addWidget(_field_label("Every"))
        self._recur_ih = QLineEdit(); self._recur_ih.setPlaceholderText("0h"); self._recur_ih.setFixedWidth(48); self._recur_ih.setFixedHeight(28)
        self._recur_im = QLineEdit(); self._recur_im.setPlaceholderText("30m"); self._recur_im.setFixedWidth(48); self._recur_im.setFixedHeight(28)
        self._recur_is = QLineEdit(); self._recur_is.setPlaceholderText("0s"); self._recur_is.setFixedWidth(48); self._recur_is.setFixedHeight(28)
        for w in (self._recur_ih, self._recur_im, self._recur_is):
            self._recur_dyn_layout.addWidget(w)
        self._recur_dyn_layout.addStretch()

    def _on_recur_subtype_change(self, t):
        self._recur_days_widget.setVisible(t == "Weekly")
        if t == "Interval":
            self._build_recur_interval_fields()
        else:
            self._build_recur_time_fields()

    def _fill_timer_preset(self, minutes):
        h, m = divmod(minutes, 60)
        self._rem_h.setText(str(h) if h else "")
        self._rem_m.setText(str(m) if m else "")
        self._rem_s.setText("")

    def _on_type_change(self, t):
        builders = {
            "Timer": self._build_timer_fields,
            "Reminder": self._build_reminder_fields,
            "Recurring": self._build_recurring_fields,
        }
        builders.get(t, self._build_timer_fields)()

    # ── Pickers / helpers ─────────────────────────────────────────────

    def _date_picker(self):
        w = QDateEdit()
        w.setCalendarPopup(True)
        w.setDate(QDate.currentDate())
        w.setFixedHeight(28)
        w.setDisplayFormat("MMM d, yyyy")
        return w

    def _time_picker(self):
        w = QTimeEdit()
        now = QTime.currentTime()
        w.setTime(QTime(now.hour() + 1 if now.hour() < 23 else 0, 0))
        w.setFixedHeight(28)
        w.setDisplayFormat("hh:mm AP")
        return w

    def _date_quick_btns(self, date_widget):
        today = QPushButton("Today")
        today.setFixedSize(72, 24)
        today.setFont(font(10))
        today.clicked.connect(lambda: date_widget.setDate(QDate.currentDate()))
        tmrw = QPushButton("+1d")
        tmrw.setFixedSize(48, 24)
        tmrw.setFont(font(10))
        tmrw.clicked.connect(lambda: date_widget.setDate(QDate.currentDate().addDays(1)))
        return today, tmrw

    # ── Add from form ─────────────────────────────────────────────────

    def _add_from_form(self):
        t = self._type_combo.currentText()
        label = self._label_entry.text().strip() or t

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
            msg = self._timer_msg.text().strip()
            self.app.reminders.create_timer(label, seconds, message=msg)
            self._rem_h.clear(); self._rem_m.clear(); self._rem_s.clear()
            self._timer_msg.clear()

        elif t == "Reminder":
            d = self._rem_date.date()
            ti = self._rem_time.time()
            fire_at = datetime(d.year(), d.month(), d.day(), ti.hour(), ti.minute()).timestamp()
            if fire_at <= _time.time():
                self._rem_date.setStyleSheet(f"border-color: {COLORS['error']};")
                return
            self._rem_date.setStyleSheet("")
            msg = self._rem_msg.text().strip()
            self.app.reminders.create_at(label, "reminder", fire_at, msg or label)
            self._rem_msg.clear()

        else:  # Recurring
            rtype = self._recur_type_combo.currentText()
            if rtype == "Interval":
                try:
                    h = int(self._recur_ih.text() or 0)
                    m = int(self._recur_im.text() or 0)
                    s = int(self._recur_is.text() or 0)
                except ValueError:
                    return
                seconds = h * 3600 + m * 60 + s
                if seconds <= 0:
                    return
                recur = {"type": "interval", "seconds": seconds}
            else:
                ti = self._recur_time.time()
                hhmm = f"{ti.hour():02d}:{ti.minute():02d}"
                if rtype == "Daily":
                    recur = {"type": "daily", "time": hhmm}
                elif rtype == "Weekdays":
                    recur = {"type": "weekly", "days": [0, 1, 2, 3, 4], "time": hhmm}
                elif rtype == "Weekends":
                    recur = {"type": "weekly", "days": [5, 6], "time": hhmm}
                else:
                    days = [i for i, cb in enumerate(self._day_checks) if cb.isChecked()]
                    if not days:
                        return
                    recur = {"type": "weekly", "days": days, "time": hhmm}
            self.app.reminders.create_recurring(label, label, recur)

        self._label_entry.clear()
        self._toggle_form()
        self.refresh_list()
        self.app.push_reminders_to_ui()

    # ── Edit dialog ───────────────────────────────────────────────────

    def _open_edit_dialog(self, entry):
        dlg = QDialog(self)
        dlg.setWindowTitle("Edit")
        dlg.setMinimumWidth(360)
        dlg.setStyleSheet(f"QDialog {{ background: {COLORS['bg']}; }}")

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(16, 16, 16, 14)
        layout.setSpacing(10)

        def add_field(label_text, widget):
            row = QHBoxLayout()
            row.setSpacing(8)
            row.addWidget(_field_label(label_text))
            row.addWidget(widget, stretch=1)
            w = QWidget(); w.setLayout(row)
            layout.addWidget(w)
            return widget

        lbl_edit = QLineEdit(entry.label)
        lbl_edit.setFixedHeight(28)
        add_field("Label", lbl_edit)

        date_edit = time_edit = msg_edit = recur_time_edit = None
        dur_h = dur_m = dur_s = None
        recur_interval_h = recur_interval_m = recur_interval_s = None
        recur_type_combo = None
        day_checks = None

        if entry.type == "timer" and not entry.fired:
            remaining = max(0, int(entry.fire_at - _time.time()))
            rh, rm, rs = remaining // 3600, (remaining % 3600) // 60, remaining % 60

            dur_row = QHBoxLayout()
            dur_row.setSpacing(8)
            dur_row.addWidget(_field_label("Time"))
            dur_h = QLineEdit(str(rh)); dur_h.setFixedWidth(48); dur_h.setFixedHeight(28); dur_h.setPlaceholderText("0h")
            dur_m = QLineEdit(str(rm)); dur_m.setFixedWidth(48); dur_m.setFixedHeight(28); dur_m.setPlaceholderText("0m")
            dur_s = QLineEdit(str(rs)); dur_s.setFixedWidth(48); dur_s.setFixedHeight(28); dur_s.setPlaceholderText("0s")
            for w in (dur_h, dur_m, dur_s):
                dur_row.addWidget(w)
            dur_row.addStretch()
            dw = QWidget(); dw.setLayout(dur_row)
            layout.addWidget(dw)

        if entry.type == "timer":
            msg_val = entry.message if entry.message != entry.label else ""
            msg_edit = QLineEdit(msg_val)
            msg_edit.setPlaceholderText("Optional context")
            msg_edit.setFixedHeight(28)
            add_field("Message", msg_edit)

        elif entry.type == "reminder" and not entry.recur:
            dt = datetime.fromtimestamp(entry.fire_at)
            date_edit = QDateEdit()
            date_edit.setCalendarPopup(True)
            date_edit.setDate(QDate(dt.year, dt.month, dt.day))
            date_edit.setDisplayFormat("MMM d, yyyy")
            date_edit.setFixedHeight(28)

            date_row = QHBoxLayout()
            date_row.setSpacing(8)
            date_row.addWidget(_field_label("Date"))
            date_row.addWidget(date_edit, stretch=1)
            for b in self._date_quick_btns(date_edit):
                date_row.addWidget(b)
            dw = QWidget(); dw.setLayout(date_row)
            layout.addWidget(dw)

            time_edit = QTimeEdit()
            time_edit.setTime(QTime(dt.hour, dt.minute))
            time_edit.setDisplayFormat("hh:mm AP")
            time_edit.setFixedHeight(28)
            add_field("Time", time_edit)

        if entry.type == "reminder" and not entry.recur:
            msg_val = entry.message if entry.message != entry.label else ""
            msg_edit = QLineEdit(msg_val)
            msg_edit.setPlaceholderText("Message text")
            msg_edit.setFixedHeight(28)
            add_field("Message", msg_edit)

        if entry.recur:
            rtype = entry.recur.get("type")
            if rtype == "interval":
                secs = entry.recur.get("seconds", 0)
                rh = secs // 3600
                rm = (secs % 3600) // 60
                rs = secs % 60

                int_row = QHBoxLayout()
                int_row.setSpacing(8)
                int_row.addWidget(_field_label("Every"))
                recur_interval_h = QLineEdit(str(rh)); recur_interval_h.setFixedWidth(48); recur_interval_h.setFixedHeight(28); recur_interval_h.setPlaceholderText("0h")
                recur_interval_m = QLineEdit(str(rm)); recur_interval_m.setFixedWidth(48); recur_interval_m.setFixedHeight(28); recur_interval_m.setPlaceholderText("0m")
                recur_interval_s = QLineEdit(str(rs)); recur_interval_s.setFixedWidth(48); recur_interval_s.setFixedHeight(28); recur_interval_s.setPlaceholderText("0s")
                for w in (recur_interval_h, recur_interval_m, recur_interval_s):
                    int_row.addWidget(w)
                int_row.addStretch()
                iw = QWidget(); iw.setLayout(int_row)
                layout.addWidget(iw)
            else:
                recur_type_combo = QComboBox()
                recur_type_combo.addItems(["Daily", "Weekdays", "Weekends", "Weekly"])
                recur_type_combo.setFixedHeight(28)
                recur_type_combo.setFixedWidth(110)
                days = entry.recur.get("days", [])
                if rtype == "daily":
                    recur_type_combo.setCurrentText("Daily")
                elif sorted(days) == [0, 1, 2, 3, 4]:
                    recur_type_combo.setCurrentText("Weekdays")
                elif sorted(days) == [5, 6]:
                    recur_type_combo.setCurrentText("Weekends")
                else:
                    recur_type_combo.setCurrentText("Weekly")
                add_field("Repeat", recur_type_combo)

                days_row = QHBoxLayout()
                days_row.setSpacing(8)
                days_row.addWidget(_field_label("Days"))
                day_checks = []
                for i, day in enumerate(["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]):
                    cb = QCheckBox(day)
                    cb.setFont(font(10))
                    cb.setChecked(i in days)
                    days_row.addWidget(cb)
                    day_checks.append(cb)
                days_row.addStretch()
                days_w = QWidget(); days_w.setLayout(days_row)
                days_w.setVisible(recur_type_combo.currentText() == "Weekly")
                recur_type_combo.currentTextChanged.connect(
                    lambda t, dw=days_w: dw.setVisible(t == "Weekly")
                )
                layout.addWidget(days_w)

                h_m = entry.recur.get("time", "09:00").split(":")
                recur_time_edit = QTimeEdit()
                recur_time_edit.setTime(QTime(int(h_m[0]), int(h_m[1])))
                recur_time_edit.setDisplayFormat("hh:mm AP")
                recur_time_edit.setFixedHeight(28)
                add_field("Time", recur_time_edit)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        btns.setStyleSheet(f"color: {COLORS['text']};")
        btns.rejected.connect(dlg.reject)

        def do_save():
            updates = {"label": lbl_edit.text().strip() or entry.label}

            if dur_h is not None:
                try:
                    h = int(dur_h.text() or 0)
                    m = int(dur_m.text() or 0)
                    s = int(dur_s.text() or 0)
                except ValueError:
                    return
                secs = h * 3600 + m * 60 + s
                if secs > 0:
                    updates["fire_at"] = _time.time() + secs
                    updates["fired"] = False

            if date_edit and time_edit:
                d = date_edit.date()
                ti = time_edit.time()
                fire_at = datetime(d.year(), d.month(), d.day(), ti.hour(), ti.minute()).timestamp()
                updates["fire_at"] = fire_at
                updates["fired"] = False

            if msg_edit is not None:
                updates["message"] = msg_edit.text().strip() or updates["label"]

            if recur_interval_h is not None:
                try:
                    h = int(recur_interval_h.text() or 0)
                    m = int(recur_interval_m.text() or 0)
                    s = int(recur_interval_s.text() or 0)
                except ValueError:
                    return
                secs = h * 3600 + m * 60 + s
                if secs > 0:
                    recur = {"type": "interval", "seconds": secs}
                    updates["recur"] = recur
                    updates["fire_at"] = self.app.reminders._next_fire(recur)

            if recur_time_edit:
                ti = recur_time_edit.time()
                hhmm = f"{ti.hour():02d}:{ti.minute():02d}"
                rt = recur_type_combo.currentText()
                if rt == "Daily":
                    recur = {"type": "daily", "time": hhmm}
                elif rt == "Weekdays":
                    recur = {"type": "weekly", "days": [0, 1, 2, 3, 4], "time": hhmm}
                elif rt == "Weekends":
                    recur = {"type": "weekly", "days": [5, 6], "time": hhmm}
                else:
                    days = [i for i, cb in enumerate(day_checks) if cb.isChecked()]
                    if not days:
                        return
                    recur = {"type": "weekly", "days": days, "time": hhmm}
                updates["recur"] = recur
                updates["fire_at"] = self.app.reminders._next_fire(recur)

            self.app.reminders.update_entry(entry.id, **updates)
            self.refresh_list()
            self.app.push_reminders_to_ui()
            dlg.accept()

        btns.accepted.connect(do_save)
        layout.addWidget(btns)
        dlg.exec()

    # ── List rendering ────────────────────────────────────────────────

    def refresh_list(self):
        _clear_layout(self._expired_layout)
        _clear_layout(self._upcoming_layout)
        _clear_layout(self._tab_layout)
        self._time_labels = []

        active = self.app.reminders.get_active()
        now = _time.time()
        cutoff = now + 86400

        expired = sorted(
            [e for e in active if (not e.recur and e.fired) or (e.recur and e.triggered)],
            key=lambda e: e.fire_at,
        )
        upcoming = sorted(
            [e for e in active if not e.recur and not e.fired and e.fire_at <= cutoff],
            key=lambda e: e.fire_at,
        )
        scheduled = sorted(
            [e for e in active if not e.recur and not e.fired and e.fire_at > cutoff],
            key=lambda e: e.fire_at,
        )
        recurring = sorted(
            [e for e in active if e.recur and not e.triggered],
            key=lambda e: e.fire_at,
        )

        self._render_expired(expired)
        self._render_upcoming(upcoming)
        self._update_tab_style()
        if self._active_tab == 0:
            self._render_tab_entries(scheduled, empty_msg="No scheduled reminders")
        else:
            self._render_tab_recurring(recurring)

    def _switch_tab(self, idx):
        self._active_tab = idx
        self.refresh_list()

    def _update_tab_style(self):
        active_ss = (
            f"QPushButton {{ color: {COLORS['text']}; background: {COLORS['surface_light']}; "
            f"border: 1px solid {COLORS['border']}; border-bottom: none; "
            f"border-radius: 4px 4px 0 0; padding: 4px 14px; }}"
        )
        inactive_ss = (
            f"QPushButton {{ color: {COLORS['text_muted']}; background: transparent; "
            f"border: none; border-bottom: 1px solid {COLORS['border']}; "
            f"border-radius: 0; padding: 4px 14px; }}"
            f"QPushButton:hover {{ color: {COLORS['text']}; }}"
        )
        self._tab_sched_btn.setStyleSheet(active_ss if self._active_tab == 0 else inactive_ss)
        self._tab_recur_btn.setStyleSheet(active_ss if self._active_tab == 1 else inactive_ss)

    def _render_expired(self, entries):
        has_entries = bool(entries)
        self._expired_header.setVisible(has_entries)
        self._expired_frame.setVisible(has_entries)
        self._clear_all_btn.setVisible(has_entries)
        if not has_entries:
            return
        for i, entry in enumerate(entries):
            if i > 0:
                self._expired_layout.addWidget(_sep())
            if entry.recur:
                self._expired_layout.addWidget(self._triggered_row(entry))
            else:
                self._expired_layout.addWidget(self._fired_row(entry))

    def _render_upcoming(self, entries):
        has_entries = bool(entries)
        self._upcoming_header.setVisible(has_entries)
        self._upcoming_frame.setVisible(has_entries)
        if not has_entries:
            return
        now = _time.time()
        for i, entry in enumerate(entries):
            if i > 0:
                self._upcoming_layout.addWidget(_sep())
            self._upcoming_layout.addWidget(self._pending_row(entry, now))

    def _render_tab_entries(self, entries, empty_msg="No entries"):
        if not entries:
            self._tab_layout.addWidget(_empty(empty_msg))
            return
        now = _time.time()
        for i, entry in enumerate(entries):
            if i > 0:
                self._tab_layout.addWidget(_sep())
            self._tab_layout.addWidget(self._pending_row(entry, now))

    def _render_tab_recurring(self, entries):
        if not entries:
            self._tab_layout.addWidget(_empty("No recurring reminders"))
            return
        for i, entry in enumerate(entries):
            if i > 0:
                self._tab_layout.addWidget(_sep())
            self._tab_layout.addWidget(self._recurring_row(entry))

    # ── Row builders ──────────────────────────────────────────────────

    def _pending_row(self, entry, now):
        header = _HoverRow()
        row = QHBoxLayout(header)
        row.setContentsMargins(12, 10, 10, 10)
        row.setSpacing(10)

        # Expand arrow
        arrow = QLabel("▸")
        arrow.setFont(font(10))
        arrow.setStyleSheet(f"color: {COLORS['text_muted']};")
        arrow.setFixedWidth(12)
        row.addWidget(arrow)

        # Type badge
        badge = _type_badge(entry.type)
        row.addWidget(badge)

        # Name
        name = _ElidedLabel(entry.label)
        name.setFont(font(12))
        name.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        row.addWidget(name, stretch=1)

        # Time / countdown
        if entry.type == "timer":
            remaining = max(0, entry.fire_at - now)
            time_text = _fmt_countdown(remaining)
        else:
            time_text = _friendly_date(entry.fire_at)

        time_lbl = QLabel(time_text)
        time_lbl.setFont(font(12, "bold"))
        time_lbl.setStyleSheet(f"color: {COLORS['text_dim']};")
        row.addWidget(time_lbl)
        self._time_labels.append((time_lbl, entry.id, entry.type == "timer", entry.fire_at))

        # Actions (hover-only)
        edit_btn = _emoji_btn("✏️", lambda _, e=entry: self._open_edit_dialog(e))
        del_btn = _emoji_btn("🗑️", lambda _, eid=entry.id: self._cancel(eid), danger=True)
        for btn in (edit_btn, del_btn):
            row.addWidget(btn)
            header.add_action(btn)

        # Build expandable wrapper
        detail_text = ""
        if entry.message and entry.message != entry.label:
            detail_text = entry.message

        exp = _ExpandableRow(header, detail_text)
        exp._arrow = arrow
        exp.set_elided_label(name)

        if entry.type == "timer":
            exp.add_detail_line(f"Started {_friendly_date(entry.created)}")
        elif entry.type == "reminder":
            fire_dt = datetime.fromtimestamp(entry.fire_at)
            exp.add_detail_line(f"{fire_dt.strftime('%A, %B %d at')} {fmt_time(fire_dt, seconds=False).strip()}")

        return exp

    def _fired_row(self, entry):
        header = _HoverRow()
        row = QHBoxLayout(header)
        row.setContentsMargins(12, 10, 10, 10)
        row.setSpacing(10)

        # Expand arrow
        arrow = QLabel("▸")
        arrow.setFont(font(10))
        arrow.setStyleSheet(f"color: {COLORS['text_muted']};")
        arrow.setFixedWidth(12)
        row.addWidget(arrow)

        # Type badge (dimmed)
        badge = _type_badge(entry.type, dimmed=True)
        row.addWidget(badge)

        # Name
        name = _ElidedLabel(entry.label)
        name.setFont(font(12))
        name.setStyleSheet(f"color: {COLORS['text_dim']};")
        name.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        row.addWidget(name, stretch=1)

        # Fired time
        fired_lbl = QLabel(_friendly_date(entry.fire_at))
        fired_lbl.setFont(font(10))
        fired_lbl.setStyleSheet(f"color: {COLORS['warning']};")
        row.addWidget(fired_lbl)

        # Snooze (5m)
        snooze_btn = QPushButton("💤")
        snooze_btn.setFixedSize(40, 24)
        snooze_btn.setFont(font(9))
        snooze_btn.setStyleSheet(
            f"QPushButton {{ color: {COLORS['text_dim']}; background: transparent; "
            f"border: 1px solid {COLORS['border']}; border-radius: 3px; }}"
            f"QPushButton:hover {{ color: {COLORS['text']}; border-color: {COLORS['text_dim']}; }}"
        )
        snooze_btn.clicked.connect(lambda _, eid=entry.id: self._snooze(eid, 300))
        row.addWidget(snooze_btn)
        header.add_action(snooze_btn)

        edit_btn = _emoji_btn("✏️", lambda _, e=entry: self._open_edit_dialog(e))
        del_btn = _emoji_btn("🗑️", lambda _, eid=entry.id: self._cancel(eid), danger=True)
        for btn in (edit_btn, del_btn):
            row.addWidget(btn)
            header.add_action(btn)

        # Build expandable wrapper
        detail_text = ""
        if entry.message and entry.message != entry.label:
            detail_text = entry.message

        exp = _ExpandableRow(header, detail_text)
        exp._arrow = arrow
        exp.set_elided_label(name)

        exp.add_detail_line(f"Created {_friendly_date(entry.created)}")

        return exp

    def _triggered_row(self, entry):
        header = _HoverRow()
        row = QHBoxLayout(header)
        row.setContentsMargins(12, 10, 10, 10)
        row.setSpacing(10)

        # Expand arrow
        arrow = QLabel("▸")
        arrow.setFont(font(10))
        arrow.setStyleSheet(f"color: {COLORS['text_muted']};")
        arrow.setFixedWidth(12)
        row.addWidget(arrow)

        dot = QLabel("⚠️")
        dot.setFont(font(12))
        dot.setFixedWidth(22)
        row.addWidget(dot)

        name = _ElidedLabel(entry.label)
        name.setFont(font(12))
        name.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        row.addWidget(name, stretch=1)

        dismiss_btn = QPushButton("Dismiss")
        dismiss_btn.setFixedSize(68, 26)
        dismiss_btn.setFont(font(10))
        dismiss_btn.setStyleSheet(
            f"QPushButton {{ color: {COLORS['text_dim']}; background: transparent; "
            f"border: 1px solid {COLORS['border']}; border-radius: 3px; }}"
            f"QPushButton:hover {{ color: {COLORS['text']}; border-color: {COLORS['text_dim']}; }}"
        )
        dismiss_btn.clicked.connect(lambda _, eid=entry.id: self._dismiss(eid))
        row.addWidget(dismiss_btn)

        exp = _ExpandableRow(header)
        exp._arrow = arrow
        exp.set_elided_label(name)

        exp.add_detail_line(_recur_desc(entry.recur))
        exp.add_detail_line(f"Fired {_friendly_date(entry.fire_at)}", COLORS['warning'])

        return exp

    def _recurring_row(self, entry):
        header = _HoverRow()
        row = QHBoxLayout(header)
        row.setContentsMargins(12, 10, 10, 10)
        row.setSpacing(10)

        # Expand arrow
        arrow = QLabel("▸")
        arrow.setFont(font(10))
        arrow.setStyleSheet(f"color: {COLORS['text_muted']};")
        arrow.setFixedWidth(12)
        row.addWidget(arrow)

        dot = QLabel("🔁")
        dot.setFont(font(12))
        dot.setFixedWidth(22)
        row.addWidget(dot)

        # Name + schedule on one line
        name = _ElidedLabel(entry.label)
        name.setFont(font(12))
        name.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        row.addWidget(name, stretch=1)

        sched = QLabel(_recur_desc(entry.recur))
        sched.setFont(font(10))
        sched.setStyleSheet(f"color: {COLORS['text_muted']};")
        row.addWidget(sched)

        # Next fire
        next_text = _friendly_date(entry.fire_at, prefix="Next")
        next_lbl = QLabel(next_text)
        next_lbl.setFont(font(11))
        next_lbl.setStyleSheet(f"color: {COLORS['text_dim']};")
        row.addWidget(next_lbl)

        # Actions (hover-only)
        edit_btn = _emoji_btn("✏️", lambda _, e=entry: self._open_edit_dialog(e))
        del_btn = _emoji_btn("🗑️", lambda _, eid=entry.id: self._cancel(eid), danger=True)
        for btn in (edit_btn, del_btn):
            row.addWidget(btn)
            header.add_action(btn)

        exp = _ExpandableRow(header)
        exp._arrow = arrow
        exp.set_elided_label(name)

        fire_dt = datetime.fromtimestamp(entry.fire_at)
        exp.add_detail_line(f"Next: {fire_dt.strftime('%A, %B %d')} at {fmt_time(fire_dt, seconds=False).strip()}")
        if entry.message and entry.message != entry.label:
            exp.add_detail_line(entry.message, COLORS['text_dim'])

        return exp

    # ── Actions ───────────────────────────────────────────────────────

    def _cancel(self, eid):
        self.app.reminders.cancel(eid)
        self.refresh_list()
        self.app.push_reminders_to_ui()

    def _snooze(self, eid, seconds):
        self.app.reminders.snooze(eid, seconds)
        self.refresh_list()
        self.app.push_reminders_to_ui()

    def _clear_all_fired(self):
        self.app.reminders.clear_fired()
        self.refresh_list()
        self.app.push_reminders_to_ui()

    def _clear_all_expired(self):
        self.app.reminders.clear_fired()
        self.app.reminders.dismiss_all_triggered()
        self.refresh_list()
        self.app.push_reminders_to_ui()

    def _dismiss(self, eid):
        self.app.reminders.dismiss(eid)
        self.refresh_list()
        self.app.push_reminders_to_ui()

    def _dismiss_all_triggered(self):
        self.app.reminders.dismiss_all_triggered()
        self.refresh_list()
        self.app.push_reminders_to_ui()

    def _reset_recurring(self, eid):
        self.app.reminders.reset_recurring(eid)
        self.refresh_list()
        self.app.push_reminders_to_ui()

    # ── Ticker ────────────────────────────────────────────────────────

    def _start_ticker(self):
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)

    def _tick(self):
        now = _time.time()
        for lbl, eid, is_timer, fire_at in self._time_labels:
            if is_timer:
                remaining = max(0, fire_at - now)
                lbl.setText(_fmt_countdown(remaining))
                if remaining <= 60:
                    lbl.setStyleSheet(f"color: {COLORS['error']}; font-weight: bold;")
                elif remaining <= 300:
                    lbl.setStyleSheet(f"color: {COLORS['warning']};")
                else:
                    lbl.setStyleSheet(f"color: {COLORS['text_dim']};")


# ── Helpers ───────────────────────────────────────────────────────────

def _section_label(text):
    lbl = QLabel(text)
    lbl.setFont(font(9, "bold"))
    lbl.setStyleSheet(f"color: {COLORS['text_muted']};")
    lbl.setContentsMargins(2, 4, 0, 0)
    return lbl


def _field_label(text):
    lbl = QLabel(text)
    lbl.setFont(font(11))
    lbl.setStyleSheet(f"color: {COLORS['text_dim']};")
    lbl.setFixedWidth(54)
    return lbl


def _empty(text):
    lbl = QLabel(text)
    lbl.setFont(font(11))
    lbl.setStyleSheet(f"color: {COLORS['text_muted']};")
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setContentsMargins(0, 14, 0, 14)
    return lbl


def _type_char(entry_type):
    return {"timer": "⏱️", "reminder": "📌"}.get(entry_type, "*")


def _type_badge(entry_type, dimmed=False):
    text = {"timer": "⏱️", "reminder": "📌"}.get(entry_type, entry_type.upper())
    lbl = QLabel(text)
    lbl.setFont(font(8, "bold"))
    lbl.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    color = COLORS['text_muted'] if dimmed else COLORS['text_dim']
    lbl.setStyleSheet(
        f"color: {color}; background: {COLORS['surface_light']}; "
        f"border: 1px solid {COLORS['border']}; border-radius: 3px; "
        f"padding: 2px 6px;"
    )
    return lbl


def _emoji_btn(emoji, callback, danger=False):
    btn = QPushButton(emoji)
    btn.setFixedSize(28, 24)
    btn.setStyleSheet(
        f"QPushButton {{ background: transparent; border: 1px solid {COLORS['border']}; "
        f"border-radius: 3px; padding: 0; }}"
        f"QPushButton:hover {{ border-color: {COLORS['error'] if danger else COLORS['text_dim']}; }}"
    )
    btn.clicked.connect(callback)
    return btn


def _fmt_countdown(remaining):
    remaining = max(0, int(remaining))
    h = remaining // 3600
    m = (remaining % 3600) // 60
    s = remaining % 60
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _friendly_date(timestamp, prefix=""):
    """Human-friendly date/time: 'Today 3:30 PM', 'Tomorrow 9:00 AM', 'Wed, Mar 16 2:00 PM'."""
    dt = datetime.fromtimestamp(timestamp)
    now = datetime.now()
    today = now.date()
    tomorrow = today + timedelta(days=1)
    time_str = fmt_time(dt, seconds=False).strip()

    if dt.date() == today:
        day_part = "Today"
    elif dt.date() == tomorrow:
        day_part = "Tomorrow"
    elif dt.date() == today - timedelta(days=1):
        day_part = "Yesterday"
    elif abs((dt.date() - today).days) < 7:
        day_part = dt.strftime("%A")  # "Monday", "Tuesday", etc.
    else:
        day_part = dt.strftime("%a, %b %d")  # "Wed, Mar 16"

    result = f"{day_part} {time_str}"
    if prefix:
        result = f"{prefix} {result}"
    return result


def _recur_desc(recur):
    if not recur:
        return ""
    rtype = recur.get("type")
    if rtype == "interval":
        secs = recur["seconds"]
        if secs >= 3600 and secs % 3600 == 0:
            n = secs // 3600
            return f"Every {n} {'hour' if n == 1 else 'hours'}"
        elif secs >= 60 and secs % 60 == 0:
            n = secs // 60
            return f"Every {n} {'minute' if n == 1 else 'minutes'}"
        return f"Every {secs}s"
    h, m = map(int, recur["time"].split(":"))
    period = "AM" if h < 12 else "PM"
    h12 = h % 12 or 12
    time_str = f"{h12}:{m:02d} {period}"
    if rtype == "daily":
        return f"Daily at {time_str}"
    if rtype == "weekly":
        days = recur.get("days", [])
        if sorted(days) == [0, 1, 2, 3, 4]:
            return f"Weekdays at {time_str}"
        if sorted(days) == [5, 6]:
            return f"Weekends at {time_str}"
        day_names = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
        return f"{', '.join(day_names[d] for d in sorted(days))} at {time_str}"
    return ""


def _sep():
    sep = QFrame()
    sep.setFixedHeight(1)
    sep.setStyleSheet(f"background: {COLORS['border']};")
    return sep


def _clear_layout(layout):
    while layout.count():
        child = layout.takeAt(0)
        if child.widget():
            child.widget().deleteLater()
        elif child.layout():
            _clear_layout(child.layout())
