"""Settings page — General, Appearance, Widget, Advanced sections."""

import subprocess
import sys
import threading

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QComboBox, QCheckBox,
)
from PyQt6.QtCore import Qt, pyqtSignal

from ui.styles import COLORS, font, R


class SettingsPage(QWidget):
    _hotkey_captured = pyqtSignal(str)

    def __init__(self, app):
        super().__init__()
        self.app = app
        self._hotkey_binding = False
        self._hotkey_captured.connect(self._apply_hotkey)
        self._init_ui()

    def _init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(4, 4, 4, 4)
        scroll.setWidget(content)
        outer.addWidget(scroll)

        # ── GENERAL ──
        layout.addWidget(self._section_label("GENERAL"))

        # Voice Hotkey
        row, right = self._setting_row("Voice Hotkey")
        current_hotkey = self.app.config.get('hotkeys', 'voice_record', default='f9').upper()
        self._hotkey_btn = QPushButton(current_hotkey)
        self._hotkey_btn.setFixedSize(160, 32)
        self._hotkey_btn.clicked.connect(self._start_hotkey_capture)
        right.addWidget(self._hotkey_btn)
        layout.addWidget(row)

        # Close Behavior
        row, right = self._setting_row("Close Behavior")
        self._close_map = {"ask": "Always Ask", "minimize": "Minimize to Tray", "quit": "Quit"}
        self._close_reverse = {v: k for k, v in self._close_map.items()}
        current_close = self.app.config.get('ui', 'close_behavior', default='ask')
        self._close_combo = QComboBox()
        self._close_combo.addItems(list(self._close_map.values()))
        self._close_combo.setCurrentText(self._close_map.get(current_close, "Always Ask"))
        self._close_combo.setFixedWidth(160)
        self._close_combo.currentTextChanged.connect(
            lambda v: self.app.config.set('ui', 'close_behavior',
                                          value=self._close_reverse.get(v, "ask"))
        )
        right.addWidget(self._close_combo)
        layout.addWidget(row)

        # Voice Response
        row, right = self._setting_row("Voice Response")
        self._voice_resp_cb = QCheckBox()
        self._voice_resp_cb.setChecked(self.app.config.get('ui', 'voice_response', default=True))
        self._voice_resp_cb.stateChanged.connect(self._on_voice_response_toggle)
        right.addWidget(self._voice_resp_cb)
        layout.addWidget(row)

        # ── APPEARANCE ──
        layout.addWidget(self._section_label("APPEARANCE"))

        # UI Scale
        row, right = self._setting_row("UI Scale")
        hint = QLabel("Requires restart")
        hint.setFont(font(11))
        hint.setStyleSheet(f"color: {COLORS['text_muted']};")
        self._scale_combo = QComboBox()
        self._scale_combo.addItems(["Small", "Medium", "Large", "XL"])
        current_scale = self.app.config.get('ui', 'ui_scale', default='Medium')
        self._scale_combo.setCurrentText(current_scale)
        self._scale_combo.setFixedWidth(160)
        self._scale_combo.currentTextChanged.connect(
            lambda v: self.app.config.set('ui', 'ui_scale', value=v)
        )
        right.addWidget(hint)
        right.addWidget(self._scale_combo)
        layout.addWidget(row)

        # Widget Size
        row, right = self._setting_row("Widget Size")
        hint2 = QLabel("Requires restart")
        hint2.setFont(font(11))
        hint2.setStyleSheet(f"color: {COLORS['text_muted']};")
        self._wsize_combo = QComboBox()
        self._wsize_combo.addItems(["Small", "Medium", "Large"])
        current_wsize = self.app.config.get('ui', 'widget_size', default='Medium')
        self._wsize_combo.setCurrentText(current_wsize)
        self._wsize_combo.setFixedWidth(160)
        self._wsize_combo.currentTextChanged.connect(
            lambda v: self.app.config.set('ui', 'widget_size', value=v)
        )
        right.addWidget(hint2)
        right.addWidget(self._wsize_combo)
        layout.addWidget(row)

        # ── WIDGET ──
        layout.addWidget(self._section_label("WIDGET"))

        row, right = self._setting_row("Widget Enabled")
        self._widget_cb = QCheckBox()
        self._widget_cb.setChecked(self.app.config.get('ui', 'widget_enabled', default=True))
        self._widget_cb.stateChanged.connect(self._on_widget_toggle)
        right.addWidget(self._widget_cb)
        layout.addWidget(row)

        row, right = self._setting_row("Widget Visible in Tray")
        self._widget_tray_cb = QCheckBox()
        self._widget_tray_cb.setChecked(self.app.config.get('ui', 'widget_visible_in_tray', default=False))
        self._widget_tray_cb.stateChanged.connect(
            lambda: self.app.config.set('ui', 'widget_visible_in_tray',
                                        value=self._widget_tray_cb.isChecked())
        )
        right.addWidget(self._widget_tray_cb)
        layout.addWidget(row)

        # ── ADVANCED ──
        layout.addWidget(self._section_label("ADVANCED"))

        btn_row = QHBoxLayout()
        for text, cb in [("Open Config File", self._open_config_file),
                          ("Open Config Folder", self._open_config_folder)]:
            btn = QPushButton(text)
            btn.setFixedHeight(32)
            btn.clicked.connect(cb)
            btn_row.addWidget(btn)
        btn_row.addStretch()
        btn_w = QWidget()
        btn_w.setLayout(btn_row)
        layout.addWidget(btn_w)

        layout.addStretch()

    # ── Helpers ──

    def _section_label(self, text):
        lbl = QLabel(text)
        lbl.setFont(font(11, "bold"))
        lbl.setStyleSheet(f"color: {COLORS['text_muted']}; padding-top: 12px;")
        return lbl

    def _setting_row(self, label_text):
        """Returns (row_widget, right_layout) — add controls to right_layout."""
        row = QFrame()
        row.setStyleSheet("QFrame { background: transparent; }")
        h = QHBoxLayout(row)
        h.setContentsMargins(8, 3, 8, 3)
        lbl = QLabel(label_text)
        lbl.setFont(font(13))
        h.addWidget(lbl)
        h.addStretch()
        return row, h

    # ── Callbacks ──

    def _start_hotkey_capture(self):
        if self._hotkey_binding:
            return
        self._hotkey_binding = True
        self._hotkey_btn.setText("Press a key...")
        self._hotkey_btn.setProperty("accent", True)
        self._hotkey_btn.style().unpolish(self._hotkey_btn)
        self._hotkey_btn.style().polish(self._hotkey_btn)

        old_key = self.app.config.get('hotkeys', 'voice_record', default='f9')
        self.app.hotkey_manager.unregister(old_key)

        def on_capture():
            import keyboard as kb
            combo = kb.read_hotkey(suppress=False)
            self._hotkey_captured.emit(combo)

        threading.Thread(target=on_capture, daemon=True).start()

    def _apply_hotkey(self, new_key: str):
        self._hotkey_binding = False
        display = "+".join(
            p.capitalize() if p in ("ctrl", "alt", "shift") else p.upper()
            for p in new_key.split("+")
        )
        self._hotkey_btn.setText(display)
        self._hotkey_btn.setProperty("accent", False)
        self._hotkey_btn.style().unpolish(self._hotkey_btn)
        self._hotkey_btn.style().polish(self._hotkey_btn)

        self.app.config.set('hotkeys', 'voice_record', value=new_key.lower())
        self.app.hotkey_manager.register(new_key.lower(), self.app.toggle_voice, "Voice recording")
        self.app.update_hotkey_display(display)

    def _on_voice_response_toggle(self):
        enabled = self._voice_resp_cb.isChecked()
        self.app.config.set('ui', 'voice_response', value=enabled)
        self.app.tts.enabled = enabled

    def _on_widget_toggle(self):
        enabled = self._widget_cb.isChecked()
        self.app.config.set('ui', 'widget_enabled', value=enabled)
        if enabled:
            self.app.widget.show()
        else:
            self.app.widget.hide()

    def _open_config_file(self):
        config_file = self.app.config.config_file
        if sys.platform == "win32":
            import os
            os.startfile(str(config_file))
        else:
            subprocess.run(["xdg-open", str(config_file)])

    def _open_config_folder(self):
        config_dir = self.app.config.config_dir
        if sys.platform == "win32":
            subprocess.run(["explorer", str(config_dir)])
        else:
            subprocess.run(["xdg-open", str(config_dir)])
