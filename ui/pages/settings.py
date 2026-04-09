"""Settings page — General, Appearance, Widget, Advanced sections."""

import os
import subprocess
import sys
import threading

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QComboBox, QCheckBox,
)
from PyQt6.QtCore import Qt, pyqtSignal

from ui.styles import COLORS, font, R, fix_combo_popup


_STARTUP_REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_STARTUP_REG_NAME = "vox"


def _is_startup_enabled() -> bool:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _STARTUP_REG_KEY) as key:
            winreg.QueryValueEx(key, _STARTUP_REG_NAME)
            return True
    except Exception:
        return False


def _set_startup(enabled: bool):
    try:
        import winreg
        if enabled:
            exe = sys.executable
            script = os.path.abspath(sys.argv[0])
            if exe.lower().endswith(('python.exe', 'pythonw.exe')):
                # Use pythonw to avoid console window on startup
                pythonw = exe.lower().replace('python.exe', 'pythonw.exe')
                pythonw = os.path.join(os.path.dirname(exe), 'pythonw.exe')
                if os.path.exists(pythonw):
                    exe = pythonw
                cmd = f'"{exe}" "{script}"'
            else:
                cmd = f'"{exe}"'
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _STARTUP_REG_KEY, 0,
                                winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, _STARTUP_REG_NAME, 0, winreg.REG_SZ, cmd)
        else:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _STARTUP_REG_KEY, 0,
                                winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, _STARTUP_REG_NAME)
    except Exception as e:
        print(f"Startup registry error: {e}")


def _detect_wsl_distros() -> list[str]:
    """Return list of installed WSL distro names."""
    try:
        result = subprocess.run(
            ['wsl.exe', '--list', '--quiet'],
            capture_output=True, timeout=5,
            creationflags=0x08000000,  # CREATE_NO_WINDOW
        )
        raw = result.stdout
        # WSL outputs UTF-16-LE on Windows; fall back to utf-8
        for enc in ('utf-16-le', 'utf-8'):
            try:
                text = raw.decode(enc)
                break
            except (UnicodeDecodeError, UnicodeError):
                continue
        else:
            text = raw.decode('utf-8', errors='ignore')
        # Strip BOM, null chars, whitespace
        text = text.replace('\x00', '').strip().strip('\ufeff')
        skip = {'docker-desktop', 'docker-desktop-data'}
        return [d.strip() for d in text.splitlines() if d.strip() and d.strip().lower() not in skip]
    except Exception:
        return []


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

        # Editor
        row, right = self._setting_row("Editor")
        self._editor_map = {
            "system": "System Default", "vscode": "VS Code",
            "cursor": "Cursor", "notepad": "Notepad",
        }
        self._editor_reverse = {v: k for k, v in self._editor_map.items()}
        current_editor = self.app.config.get('general', 'editor', default='system')
        self._editor_combo = QComboBox()
        self._editor_combo.addItems(list(self._editor_map.values()))
        self._editor_combo.setCurrentText(self._editor_map.get(current_editor, "System Default"))
        self._editor_combo.setFixedWidth(160)
        self._editor_combo.currentTextChanged.connect(
            lambda v: self.app.config.set('general', 'editor',
                                          value=self._editor_reverse.get(v, "system"))
        )
        right.addWidget(self._editor_combo)
        layout.addWidget(row)

        # WSL Distro
        row, right = self._setting_row("WSL Distro")
        wsl_hint = QLabel("blank = default")
        wsl_hint.setFont(font(11))
        wsl_hint.setStyleSheet(f"color: {COLORS['text_muted']};")
        self._wsl_distro = QComboBox()
        self._wsl_distro.setEditable(True)
        distros = _detect_wsl_distros()
        self._wsl_distro.addItems([""] + distros)
        current_distro = self.app.config.get('general', 'wsl_distro', default='')
        self._wsl_distro.setCurrentText(current_distro)
        self._wsl_distro.setFixedWidth(160)
        self._wsl_distro.currentTextChanged.connect(
            lambda v: self.app.config.set('general', 'wsl_distro', value=v.strip())
        )
        right.addWidget(wsl_hint)
        right.addWidget(self._wsl_distro)
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

        # Start with Windows
        row, right = self._setting_row("Start with Windows")
        self._startup_cb = QCheckBox()
        self._startup_cb.setChecked(_is_startup_enabled())
        self._startup_cb.stateChanged.connect(lambda: _set_startup(self._startup_cb.isChecked()))
        right.addWidget(self._startup_cb)
        layout.addWidget(row)

        # Voice Response
        row, right = self._setting_row("Voice Response")
        self._voice_resp_cb = QCheckBox()
        self._voice_resp_cb.setChecked(self.app.config.get('ui', 'voice_response', default=True))
        self._voice_resp_cb.stateChanged.connect(self._on_voice_response_toggle)
        right.addWidget(self._voice_resp_cb)
        layout.addWidget(row)

        # Wake Word
        row, right = self._setting_row("Wake Word (\"Hey Vox\")")
        wake_hint = QLabel("listens always-on — may trigger on similar sounds")
        wake_hint.setFont(font(11))
        wake_hint.setStyleSheet(f"color: {COLORS['text_muted']};")
        self._wake_word_cb = QCheckBox()
        self._wake_word_cb.setChecked(
            self.app.config.get('voice', 'wake_word_enabled', default=False)
        )
        self._wake_word_cb.stateChanged.connect(self._on_wake_word_toggle)
        right.addWidget(self._wake_word_cb)
        layout.addWidget(row)
        layout.addWidget(wake_hint)

        # Reminder Confirmation TTS
        row, right = self._setting_row("Reminder Confirmation")
        hint = QLabel("full details vs brief")
        hint.setFont(font(11))
        hint.setStyleSheet(f"color: {COLORS['text_muted']};")
        self._reminder_confirm_cb = QCheckBox()
        self._reminder_confirm_cb.setChecked(
            self.app.config.get('ui', 'reminder_confirmation_tts', default=True)
        )
        self._reminder_confirm_cb.stateChanged.connect(
            lambda: self.app.config.set('ui', 'reminder_confirmation_tts',
                                        value=self._reminder_confirm_cb.isChecked())
        )
        right.addWidget(hint)
        right.addWidget(self._reminder_confirm_cb)
        layout.addWidget(row)

        # ── NOTIFICATIONS ──
        layout.addWidget(self._section_label("NOTIFICATIONS"))

        row, right = self._setting_row("Sound")
        self._notif_sound = QCheckBox()
        self._notif_sound.setChecked(self.app.config.get('notifications', 'sound', default=True))
        self._notif_sound.stateChanged.connect(
            lambda: self.app.config.set('notifications', 'sound', value=self._notif_sound.isChecked())
        )
        right.addWidget(self._notif_sound)
        layout.addWidget(row)

        row, right = self._setting_row("TTS")
        self._notif_tts = QCheckBox()
        self._notif_tts.setChecked(self.app.config.get('notifications', 'tts', default=True))
        self._notif_tts.stateChanged.connect(
            lambda: self.app.config.set('notifications', 'tts', value=self._notif_tts.isChecked())
        )
        right.addWidget(self._notif_tts)
        layout.addWidget(row)

        row, right = self._setting_row("Tray Notification")
        self._notif_tray = QCheckBox()
        self._notif_tray.setChecked(self.app.config.get('notifications', 'tray', default=True))
        self._notif_tray.stateChanged.connect(
            lambda: self.app.config.set('notifications', 'tray', value=self._notif_tray.isChecked())
        )
        right.addWidget(self._notif_tray)
        layout.addWidget(row)

        # ── APPEARANCE ──
        layout.addWidget(self._section_label("APPEARANCE"))

        # UI Scale
        row, right = self._setting_row("UI Scale")
        hint = QLabel("Requires restart")
        hint.setFont(font(11))
        hint.setStyleSheet(f"color: {COLORS['text_muted']};")
        self._scale_combo = QComboBox()
        self._scale_combo.addItems(["Small", "Medium", "Large"])
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
        self._wsize_combo = QComboBox()
        self._wsize_combo.addItems(["Small", "Large"])
        current_wsize = self.app.config.get('ui', 'widget_size', default='Large')
        self._wsize_combo.setCurrentText(current_wsize)
        self._wsize_combo.setFixedWidth(160)
        self._wsize_combo.currentTextChanged.connect(self._on_widget_size_change)
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

        # Fix combo popup z-order
        for combo in [self._editor_combo, self._wsl_distro, self._close_combo,
                       self._scale_combo, self._wsize_combo]:
            fix_combo_popup(combo)

    # ── Helpers ──

    def _section_label(self, text):
        lbl = QLabel(text)
        lbl.setFont(font(11, "bold"))
        lbl.setStyleSheet(f"color: {COLORS['text_muted']}; padding-top: 12px;")
        return lbl

    def _setting_row(self, label_text):
        """Returns (row_widget, right_layout) — add controls to right_layout."""
        row = QWidget()
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

    def _on_wake_word_toggle(self):
        enabled = self._wake_word_cb.isChecked()
        self.app.config.set('voice', 'wake_word_enabled', value=enabled)
        if enabled:
            self.app.wakeword.start()
        else:
            self.app.wakeword.stop()
        self.app.widget.set_wake_word_active(enabled)

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

    def _on_widget_size_change(self, v: str):
        self.app.config.set('ui', 'widget_size', value=v)
        if self.app.widget:
            self.app.recreate_widget()

    def _get_editor_cmd(self):
        editor = self.app.config.get('general', 'editor', default='system')
        return {"vscode": "code", "cursor": "cursor", "notepad": "notepad"}.get(editor)

    def _open_path(self, path: str, is_folder: bool = False):
        cmd = self._get_editor_cmd()
        try:
            if cmd:
                # shell=True needed on Windows for .cmd shims (code, cursor)
                subprocess.Popen(f'{cmd} "{path}"', shell=True)
            elif sys.platform == "win32":
                if is_folder:
                    subprocess.Popen(["explorer", path])
                else:
                    os.startfile(path)
            else:
                subprocess.run(["xdg-open", path])
        except Exception as e:
            print(f"Failed to open {path}: {e}")

    def _open_config_file(self):
        self._open_path(str(self.app.config.config_file))

    def _open_config_folder(self):
        self._open_path(str(self.app.config.config_dir), is_folder=True)
