"""Main vox application — QMainWindow with sidebar navigation."""

import socket
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QListWidget, QListWidgetItem,
    QStackedWidget, QMessageBox, QDialog, QScrollArea,
    QCheckBox, QApplication, QSystemTrayIcon, QMenu,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QTimer
from PyQt6.QtGui import QIcon, QAction

from core.config import get_config
from core.hotkeys import HotkeyManager
from modules.voice import VoiceRecognizer, CommandManager
from modules.voice.tts import TextToSpeech
from modules.windows import WindowManager, LayoutManager
from modules.launcher import Launcher
from modules.clipboard import ClipboardManager
from modules.reminders import ReminderManager, ReminderEntry
from modules.workflows import WorkflowManager

from ui.styles import COLORS, font, R, build_stylesheet, set_ui_scale, fmt_time
from ui.widget import FloatingWidget
from ui.pages import (
    HomePage, VoicePage, WindowsPage, LaunchersPage,
    ClipboardPage, RemindersPage, SettingsPage,
)


class VoxApp(QMainWindow):
    """Main vox application window."""

    # Signals for thread-safe UI updates from background threads
    voice_result_signal = pyqtSignal(object)
    voice_status_signal = pyqtSignal(str)
    voice_error_signal = pyqtSignal(str)
    clipboard_signal = pyqtSignal(object)
    reminder_fire_signal = pyqtSignal(object)
    workflow_done_signal = pyqtSignal(str)
    restore_signal = pyqtSignal()

    def __init__(self, q_app: QApplication):
        super().__init__()
        self._q_app = q_app
        self.setWindowTitle("vox")
        self.setFixedSize(900, 650)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowMaximizeButtonHint
        )

        # Initialize core
        self.config = get_config()
        self.hotkey_manager = HotkeyManager()

        # Apply UI scale
        set_ui_scale(self.config.get('ui', 'ui_scale', default='Medium'))

        # Apply stylesheet
        q_app.setStyleSheet(build_stylesheet())

        # Set window icon
        self._icon_path = self._resolve_icon_path()
        if self._icon_path and self._icon_path.exists():
            icon = QIcon(str(self._icon_path))
            self.setWindowIcon(icon)
            q_app.setWindowIcon(icon)

        # Initialize modules
        self.tts = TextToSpeech()
        self.tts.enabled = self.config.get('ui', 'voice_response', default=True)
        self.voice = VoiceRecognizer()
        self.commands = CommandManager()
        self.window_manager = WindowManager()
        self.layout_manager = LayoutManager(self.window_manager)
        self.launcher = Launcher()
        self.clipboard_mgr = ClipboardManager()
        self.reminders = ReminderManager(self.config.data_dir)
        self.workflow_manager = WorkflowManager(self.launcher, self.layout_manager)

        # Register voice commands
        self.commands.register_layout_commands(
            self.layout_manager, on_load_callback=self._on_layout_loaded
        )
        self.commands.register_launcher_commands(self.launcher)
        self.commands.register_workflow_commands(
            self.workflow_manager, on_run_callback=self._on_workflow_run
        )

        # State
        self.last_command = ""
        self.snippets: List[Dict] = []
        self._load_snippets()
        self._notes_path = Path(self.config.config_dir) / "notes.md"
        self._dirty = {"home": True, "voice": True, "windows": True, "clipboard": True}

        # Wire signals
        self.voice_result_signal.connect(self._handle_voice_result)
        self.voice_status_signal.connect(self._handle_voice_status)
        self.voice_error_signal.connect(self._handle_voice_error)
        self.clipboard_signal.connect(self._handle_clipboard_entry)
        self.reminder_fire_signal.connect(self._handle_reminder_fire)
        self.workflow_done_signal.connect(self._on_workflow_complete)
        self.restore_signal.connect(self._do_restore)

        # Wire callbacks → emit signals
        self.voice.on_result = lambda texts: self.voice_result_signal.emit(texts)
        self.voice.on_status = lambda text: self.voice_status_signal.emit(text)
        self.voice.on_error = lambda text: self.voice_error_signal.emit(text)
        self.voice.on_recognition_failed = lambda msg="Didn't catch that": self.tts.speak(msg)
        self.clipboard_mgr.on_new_entry = lambda entry: self.clipboard_signal.emit(entry)
        self.reminders.on_fire = lambda entry: self.reminder_fire_signal.emit(entry)

        # Build UI
        self._create_ui()

        # Floating widget
        self.widget = FloatingWidget(
            self.voice.toggle_recording,
            self._show_main_window,
            self._get_widget_actions,
            widget_size=self.config.get('ui', 'widget_size', default='Medium'),
            dismiss_reminder_cb=self._dismiss_reminder_from_widget,
        )
        if self.config.get('ui', 'widget_enabled', default=True):
            self.widget.show()

        # Show mic status if unavailable
        if not self.voice.mic_available:
            self.record_btn.setEnabled(False)
            self.set_status("Mic unavailable — check audio input", COLORS["error"])

        # Tray icon
        self._tray_icon = None

        # Single-instance listener
        self._instance_listener = None
        self._start_instance_listener()

        # Start modules
        self._setup_hotkeys()
        self.clipboard_mgr.start_monitoring()
        self.reminders.start()  # Start after UI is fully built
        self.push_reminders_to_ui()  # Initial widget state

    # ── Icon helper ──

    @staticmethod
    def _resolve_icon_path() -> Optional[Path]:
        if getattr(sys, 'frozen', False):
            p = Path(sys._MEIPASS) / "myicon.ico"
        else:
            p = Path(__file__).parent.parent / "myicon.ico"
        return p if p.exists() else None

    # ── UI Creation ──

    def _create_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header
        self._create_header(main_layout)

        # Body: sidebar + content
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        # Sidebar
        self.sidebar = QListWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(150)
        self.sidebar.setIconSize(QSize(0, 0))

        pages = [
            ("Home", "🏠"),
            ("Windows", "🪟"),
            ("Launchers", "🚀"),
            ("Clipboard", "📋"),
            ("Reminders", "⏰"),
            ("Voice", "🎤"),
            ("Settings", "⚙️"),
        ]
        for name, icon in pages:
            item = QListWidgetItem(f"{icon}  {name}")
            item.setSizeHint(QSize(150, 44))
            self.sidebar.addItem(item)

        self._reminders_sidebar_item = self.sidebar.item(4)  # "Reminders" row
        self.sidebar.setCurrentRow(0)
        self.sidebar.currentRowChanged.connect(self._on_page_change)
        body.addWidget(self.sidebar)

        # Stacked pages
        self.stack = QStackedWidget()
        self.page_home = HomePage(self)
        self.page_windows = WindowsPage(self)
        self.page_launchers = LaunchersPage(self)
        self.page_clipboard = ClipboardPage(self)
        self.page_reminders = RemindersPage(self)
        self.page_voice = VoicePage(self)
        self.page_settings = SettingsPage(self)

        for page in [self.page_home, self.page_windows, self.page_launchers,
                      self.page_clipboard, self.page_reminders, self.page_voice,
                      self.page_settings]:
            self.stack.addWidget(page)

        body.addWidget(self.stack, stretch=1)
        main_layout.addLayout(body, stretch=1)

    def _create_header(self, parent_layout):
        header = QFrame()
        header.setObjectName("header")
        header.setFixedHeight(52)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(16, 0, 12, 0)

        title = QLabel("vox")
        title.setFont(font(50, "bold"))
        title.setStyleSheet(
            f"color: {COLORS['text']}; "
            f"letter-spacing: 3px; "
            f"padding: 0 3px;"
        )
        h_layout.addWidget(title)

        sep = QLabel("│")
        sep.setFont(font(18))
        sep.setStyleSheet(f"color: {COLORS['border']}; padding: 0 2px;")
        h_layout.addWidget(sep)

        voice_key = self.config.get('hotkeys', 'voice_record', default='F9').upper()
        self.status_label = QLabel(f"Press {voice_key} to speak")
        self.status_label.setFont(font(13))
        self.status_label.setStyleSheet(f"color: {COLORS['text_dim']};")
        h_layout.addWidget(self.status_label, stretch=1)

        self.record_btn = QPushButton(f"Record [{voice_key}]")
        self.record_btn.setFixedSize(150, 34)
        self.record_btn.setProperty("accent", True)
        self.record_btn.setFont(font(13, "bold"))
        self.record_btn.clicked.connect(self.voice.toggle_recording)
        h_layout.addWidget(self.record_btn)

        widget_btn = QPushButton("Widget")
        widget_btn.setFixedSize(80, 30)
        widget_btn.clicked.connect(self._toggle_widget)
        h_layout.addWidget(widget_btn)
        self._widget_header_btn = widget_btn

        parent_layout.addWidget(header)

    # ── Page navigation ──

    def _on_page_change(self, index: int):
        self.stack.setCurrentIndex(index)
        page_names = ["home", "windows", "launchers", "clipboard", "reminders", "voice", "settings"]
        current = page_names[index] if index < len(page_names) else ""

        if current == "windows" and self._dirty.get("windows"):
            self.page_windows.refresh_windows()
            self._dirty["windows"] = False
        elif current == "home" and self._dirty.get("home"):
            self.page_home.refresh_quick_actions()
            self._dirty["home"] = False
        elif current == "voice" and self._dirty.get("voice"):
            self.page_voice.refresh()
            self._dirty["voice"] = False
        elif current == "clipboard" and self._dirty.get("clipboard"):
            self.page_clipboard.refresh_history()
            self.page_clipboard.refresh_snippets()
            self._dirty["clipboard"] = False

    def navigate_to(self, page_name: str):
        names = ["home", "windows", "launchers", "clipboard", "reminders", "voice", "settings"]
        if page_name in names:
            self.sidebar.setCurrentRow(names.index(page_name))

    # ── Public helpers used by pages ──

    def set_status(self, text: str, color: str = None):
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color: {color or COLORS['text']};")
        self.widget.set_status(text, color)

    def push_reminders_to_ui(self):
        """Refresh the reminders page, widget, and sidebar badge."""
        if hasattr(self, 'page_reminders'):
            self.page_reminders.refresh_list()
        active = self.reminders.get_active()
        self.widget.update_reminders(active)
        # Sidebar badge count (expired = fired one-shots + triggered recurring)
        count = len([e for e in active if e.fired or (e.recur and e.triggered)])
        badge = f"  ({count})" if count > 0 else ""
        self._reminders_sidebar_item.setText(f"⏰  Reminders{badge}")

    def _dismiss_reminder_from_widget(self, eid):
        self.reminders.dismiss(eid)
        self.push_reminders_to_ui()

    def mark_dirty(self, *names):
        for n in names:
            self._dirty[n] = True
        self.widget.refresh_actions()

    def is_favorite(self, category, name):
        return name in self.config.get('favorites', category, default=[])

    def toggle_favorite(self, category, name):
        favs = self.config.get('favorites', category, default=[])
        if name in favs:
            favs.remove(name)
        else:
            favs.append(name)
        self.config.set('favorites', category, value=favs)
        self._dirty["home"] = True
        self.widget.refresh_actions()
        # Refresh home if visible
        if self.stack.currentWidget() is self.page_home:
            self.page_home.refresh_quick_actions()

    def quick_load_layout(self, name: str):
        result = self.layout_manager.load_layout(name)
        color = COLORS["success"] if result['applied'] > 0 else COLORS["warning"]
        self.set_status(f"Layout '{name}': {result['applied']}/{result['total']}", color)

    def edit_layout(self, name: str):
        """Open the edit-layout dialog (ported from old _edit_layout_contents)."""
        if name not in self.layout_manager.layouts:
            return
        layout_data = self.layout_manager.layouts[name]

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Edit Layout: {name}")
        dlg.resize(520, 520)
        dlg.setStyleSheet(f"QDialog {{ background: {COLORS['bg']}; }}")

        main_layout = QVBoxLayout(dlg)
        main_layout.setContentsMargins(12, 10, 12, 10)

        # Current windows in layout
        QLabel(f"In Layout '{name}'").setFont(font(15, "bold"))
        lbl = QLabel(f"In Layout '{name}'")
        lbl.setFont(font(15, "bold"))
        main_layout.addWidget(lbl)

        scroll1 = QScrollArea()
        scroll1.setWidgetResizable(True)
        scroll1.setMaximumHeight(180)
        existing_w = QWidget()
        existing_layout = QVBoxLayout(existing_w)
        existing_layout.setContentsMargins(5, 5, 5, 5)
        scroll1.setWidget(existing_w)
        main_layout.addWidget(scroll1)

        window_vars = {}

        for key, wd in layout_data.items():
            if 'identifier' not in wd:
                continue
            app_type = wd['identifier'].get('app_type', 'unknown')
            display_name = self.window_manager.get_app_display_name(app_type)
            pos = wd.get('position', {})
            pos_str = f"{pos.get('width', '?')}x{pos.get('height', '?')}"

            row = QHBoxLayout()
            cb = QCheckBox()
            cb.setChecked(True)
            window_vars[key] = cb
            row.addWidget(cb)

            n_lbl = QLabel(display_name)
            n_lbl.setFont(font(13, "bold"))
            row.addWidget(n_lbl)

            p_lbl = QLabel(pos_str)
            p_lbl.setStyleSheet(f"color: {COLORS['text_dim']};")
            row.addWidget(p_lbl)
            row.addStretch()

            row_w = QWidget()
            row_w.setLayout(row)
            existing_layout.addWidget(row_w)

        if not layout_data:
            existing_layout.addWidget(QLabel("(empty)"))

        # Available windows to add
        lbl2 = QLabel("Add from Open Windows")
        lbl2.setFont(font(15, "bold"))
        main_layout.addWidget(lbl2)

        scroll2 = QScrollArea()
        scroll2.setWidgetResizable(True)
        available_w = QWidget()
        available_layout = QVBoxLayout(available_w)
        available_layout.setContentsMargins(5, 5, 5, 5)
        scroll2.setWidget(available_w)
        main_layout.addWidget(scroll2, stretch=1)

        current_windows = self.window_manager.get_all_windows()
        add_window_vars = {}

        if not current_windows:
            available_layout.addWidget(QLabel("No windows open"))
        else:
            for window in current_windows:
                display_name = self.window_manager.get_app_display_name(
                    self.window_manager.get_app_type(window)
                )
                title = window.title[:35] + "..." if len(window.title) > 35 else window.title

                row = QHBoxLayout()
                cb = QCheckBox()
                row.addWidget(cb)
                n_lbl = QLabel(display_name)
                n_lbl.setFont(font(13, "bold"))
                row.addWidget(n_lbl)
                t_lbl = QLabel(title)
                t_lbl.setStyleSheet(f"color: {COLORS['text_dim']};")
                t_lbl.setFont(font(12))
                row.addWidget(t_lbl)
                row.addStretch()
                add_window_vars[window.hwnd] = (cb, window)

                row_w = QWidget()
                row_w.setLayout(row)
                available_layout.addWidget(row_w)

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
            new_layout = {}
            for key, wd in layout_data.items():
                if key in window_vars and window_vars[key].isChecked():
                    new_layout[key] = wd.copy()

            next_idx = len(new_layout)
            for hwnd, (cb, window) in add_window_vars.items():
                if cb.isChecked():
                    identifier = self.window_manager.create_smart_identifier(window)
                    new_layout[f"window_{next_idx}"] = {
                        "identifier": identifier,
                        "position": {"x": window.x, "y": window.y,
                                     "width": window.width, "height": window.height},
                        "exe_path": window.exe_path,
                        "is_borderless": window.is_borderless,
                    }
                    next_idx += 1

            self.layout_manager.layouts[name] = new_layout
            self.layout_manager._save_layouts()
            self.page_windows.refresh_saved_layouts()
            self.mark_dirty("home", "voice")
            self.set_status(f"Layout '{name}' updated", COLORS["success"])
            dlg.accept()

        save_btn.clicked.connect(do_save)
        btn_row.addWidget(save_btn)
        main_layout.addLayout(btn_row)

        dlg.exec()

    def delete_layout(self, name: str):
        reply = QMessageBox.question(
            self, "Delete Layout", f"Delete layout '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            if self.layout_manager.delete_layout(name):
                self.commands._refresh_layout_commands()
                self.mark_dirty("home", "voice")

    def _load_snippets(self):
        self.snippets = self.config.get('clipboard', 'snippets', default=[])

    def save_snippets(self):
        self.config.set('clipboard', 'snippets', value=self.snippets)

    def update_hotkey_display(self, display: str):
        """Called by settings page after hotkey rebind."""
        self.status_label.setText(f"Press {display} to speak")
        self.record_btn.setText(f"Record [{display}]")

    def toggle_voice(self):
        self.voice.toggle_recording()

    # ── Widget ──

    def _toggle_widget(self):
        if self.widget.isVisible():
            self.widget.hide()
        else:
            self.widget.show()

    def _get_widget_actions(self):
        actions = {"layouts": [], "launchers": [], "workflows": []}
        fav_layouts = set(self.config.get('favorites', 'layouts', default=[]))
        fav_launchers = set(self.config.get('favorites', 'launchers', default=[]))
        fav_workflows = set(self.config.get('favorites', 'workflows', default=[]))

        for name in self.layout_manager.get_layout_names():
            if name in fav_layouts:
                actions["layouts"].append((name, lambda n=name: self.quick_load_layout(n)))

        for item in self.launcher.get_all_items():
            if item.name in fav_launchers:
                actions["launchers"].append((item.name, lambda i=item: self.launcher.launch(i)))

        for name in self.workflow_manager.get_names():
            if name in fav_workflows:
                actions["workflows"].append((name, lambda n=name: self.run_workflow(n)))

        return actions

    # ── Voice callbacks (run on main thread via signals) ──

    def _handle_voice_result(self, alternatives):
        # Accept list of alternative transcriptions or a single string
        if isinstance(alternatives, str):
            alternatives = [alternatives]
        text = alternatives[0]  # best transcription (used for free-text like notes/reminders)

        timestamp = fmt_time(seconds=False)
        self.last_command = text
        response_to_speak = None

        note_text = self._extract_note_text(text)
        reminder_response = self._handle_reminder_voice(text)

        if note_text:
            self._save_note(note_text)
            result = {"executed": True, "success": True, "type": "note"}
            response_to_speak = "Note saved"
        elif reminder_response is not None:
            result = {"executed": True, "success": True, "type": "reminder"}
            response_to_speak = reminder_response
        else:
            # Try each alternative transcription for command matching
            result = {"executed": False, "success": False, "type": None, "response": None}
            for alt in alternatives:
                result = self.commands.execute(alt)
                if result["executed"]:
                    text = alt  # use the alternative that matched
                    response_to_speak = result.get("response")
                    break

            if not result["executed"]:
                # Try launcher fallback with each alternative
                for alt in alternatives:
                    item = self.launcher.get_by_voice_phrase(alt)
                    if item:
                        self.launcher.launch(item)
                        result = {"executed": True, "success": True, "type": "launcher"}
                        text = alt
                        response_to_speak = f"Launching {item.name}"
                        break

            if not result["executed"]:
                response_to_speak = "Command not known"

        self.tts.speak(response_to_speak)
        self.widget.set_tts_response(response_to_speak or "")
        self.widget.set_action(text if result["executed"] else "")

        status = ">" if result["executed"] else "?"
        log_entry = f"[{timestamp}] {status} {text}\n"
        self.page_home.prepend_voice_log(log_entry)

        if result["executed"]:
            self.set_status(f"> {text}", COLORS["success"])
        else:
            self.set_status(f"? {text}", COLORS["warning"])

    def _handle_voice_status(self, status: str):
        self.set_status(status, COLORS["text_dim"])
        voice_key = self.config.get('hotkeys', 'voice_record', default='F9').upper()
        is_recording = "Listening" in status

        self.widget.set_recording(is_recording)

        if is_recording:
            self.record_btn.setText("REC Recording...")
            self.record_btn.setStyleSheet(
                f"background: {COLORS['error']}; color: {COLORS['text']}; "
                f"border: none; border-radius: {R['md']}px; font-weight: bold;"
            )
        else:
            self.record_btn.setText(f"Record [{voice_key}]")
            self.record_btn.setStyleSheet("")  # Reset to QSS default
            self.record_btn.setProperty("accent", True)
            self.record_btn.style().unpolish(self.record_btn)
            self.record_btn.style().polish(self.record_btn)

    def _handle_voice_error(self, error: str):
        self.set_status(error, COLORS["error"])

    def _handle_clipboard_entry(self, entry):
        if self.stack.currentWidget() is self.page_clipboard:
            self.page_clipboard.refresh_history()
        else:
            self._dirty["clipboard"] = True

    def _handle_reminder_fire(self, entry: ReminderEntry):
        try:
            if self.config.get('notifications', 'sound', default=True):
                self.reminders._play_audio()
            if self.config.get('notifications', 'tts', default=True):
                self.tts.speak(entry.message)
            if self.config.get('notifications', 'tray', default=True):
                self._show_win_notification("vox", entry.message)
            self.push_reminders_to_ui()
        except Exception:
            pass

    def _on_layout_loaded(self, name: str, result: dict):
        msg = f"Layout '{name}': {result['applied']}/{result['total']}"
        color = COLORS["success"] if result['applied'] > 0 else COLORS["warning"]
        self.set_status(msg, color)

    def run_workflow(self, name: str):
        self.set_status(f"Running workflow '{name}'...", COLORS["accent"])
        self.workflow_manager.execute(
            name, on_complete=lambda n: self.workflow_done_signal.emit(n)
        )

    def _on_workflow_run(self, name: str):
        """Voice callback for running a workflow."""
        self.run_workflow(name)

    def _on_workflow_complete(self, name: str):
        self.set_status(f"Workflow '{name}' complete", COLORS["success"])

    # ── Note / reminder helpers ──

    def _extract_note_text(self, text: str) -> Optional[str]:
        lower = text.lower().strip()
        for prefix in ["take a note ", "take note ", "note "]:
            if lower.startswith(prefix):
                return text[len(prefix):].strip() or None
        return None

    def _save_note(self, text: str):
        now = datetime.now()
        timestamp = f"{now.strftime('%Y-%m-%d')} | {fmt_time(now, seconds=False)}"
        entry = f"[{timestamp}] {text}"
        try:
            existing = ""
            if self._notes_path.exists():
                existing = self._notes_path.read_text(encoding="utf-8")
            with open(self._notes_path, "w", encoding="utf-8") as f:
                if existing.strip():
                    f.write(existing.rstrip("\n") + "\n")
                f.write(entry + "\n")
        except Exception as e:
            print(f"Failed to save note: {e}")
        self.page_home.append_note(entry)
        self.set_status(f"Note saved: {text[:30]}", COLORS["success"])

    def _handle_reminder_voice(self, text: str):
        from modules.reminders.manager import ReminderManager as _RM
        parsed = _RM.parse_voice_command(text)
        if parsed is None:
            return None
        if parsed[0] == 'timer':
            _, label, seconds = parsed
            self.reminders.create_timer(label, seconds)
            self.page_reminders.refresh_list()
            self.push_reminders_to_ui()
            m, s = divmod(seconds, 60)
            h, m = divmod(m, 60)
            if h:
                return f"Timer set for {h}h {m}m"
            elif m:
                return f"Timer set for {m} minute{'s' if m != 1 else ''}"
            else:
                return f"Timer set for {s} second{'s' if s != 1 else ''}"
        elif parsed[0] == 'reminder':
            _, label, message, time_str = parsed
            entry = self.reminders.create_reminder(label, time_str, message=message)
            if entry is None:
                return "Couldn't parse that time"
            self.page_reminders.refresh_list()
            self.push_reminders_to_ui()
            fire_dt = datetime.fromtimestamp(entry.fire_at)
            return f"Reminder set for {fire_dt.strftime('%I:%M %p').lstrip('0')}"
        elif parsed[0] == 'recurring':
            _, label, recur = parsed
            # Resolve time_str → HH:MM for non-interval types
            if recur.get("type") != "interval" and "time_str" in recur:
                fire_ts = self.reminders._parse_time(recur["time_str"])
                if fire_ts is None:
                    return "Couldn't parse that time"
                fire_dt = datetime.fromtimestamp(fire_ts)
                recur = {**recur, "time": f"{fire_dt.hour:02d}:{fire_dt.minute:02d}"}
                del recur["time_str"]
            self.reminders.create_recurring(label, label, recur)
            self.page_reminders.refresh_list()
            self.push_reminders_to_ui()
            from ui.pages.reminders import _recur_desc
            return f"Recurring reminder set: {_recur_desc(recur)}"
        return None

    # ── Notification ──

    def _show_win_notification(self, title: str, message: str):
        # Try QSystemTrayIcon notification first
        if self._tray_icon and self._tray_icon.isVisible():
            self._tray_icon.showMessage(title, message,
                                        QSystemTrayIcon.MessageIcon.Information, 5000)
            return

        # Fallback: PowerShell balloon
        t = title.replace('"', "'")
        msg = message.replace('"', "'")
        script = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            "$n = New-Object System.Windows.Forms.NotifyIcon; "
            "$n.Icon = [System.Drawing.SystemIcons]::Information; "
            "$n.Visible = $true; "
            f'$n.ShowBalloonTip(5000, "{t}", "{msg}", '
            "[System.Windows.Forms.ToolTipIcon]::Info); "
            "Start-Sleep -Milliseconds 5500; "
            "$n.Dispose()"
        )
        try:
            subprocess.Popen(
                ["powershell", "-WindowStyle", "Hidden", "-NoProfile", "-Command", script],
                creationflags=0x08000000,
            )
        except Exception:
            pass

    # ── Hotkeys ──

    def _setup_hotkeys(self):
        voice_key = self.config.get('hotkeys', 'voice_record', default='f9')
        self.hotkey_manager.register(voice_key, self.toggle_voice, "Voice recording")

    # ── Window management ──

    def _show_main_window(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    # ── Close / Tray ──

    def closeEvent(self, event):
        behavior = self.config.get('ui', 'close_behavior', default='ask')
        if behavior == "minimize":
            event.ignore()
            self._minimize_to_tray()
        elif behavior == "quit":
            event.accept()
            self._full_quit()
        else:
            event.ignore()
            self._ask_close()

    def _ask_close(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Close vox")
        dlg.setFixedSize(300, 120)
        dlg.setStyleSheet(f"QDialog {{ background: {COLORS['bg']}; }}")

        layout = QVBoxLayout(dlg)
        lbl = QLabel("Minimize to system tray?")
        lbl.setFont(font(14))
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        for text, cb in [("Minimize", lambda: (dlg.accept(), self._minimize_to_tray())),
                          ("Quit", lambda: (dlg.accept(), self._full_quit())),
                          ("Cancel", dlg.reject)]:
            btn = QPushButton(text)
            btn.setFixedSize(80, 30)
            btn.clicked.connect(cb)
            btn_row.addWidget(btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        dlg.exec()

    def _minimize_to_tray(self):
        self.hide()
        if self.widget and not self.config.get('ui', 'widget_visible_in_tray', default=False):
            self.widget.hide()
        self._create_tray_icon()

    def _create_tray_icon(self):
        if self._tray_icon:
            return

        self._tray_icon = QSystemTrayIcon(self)
        if self._icon_path and self._icon_path.exists():
            self._tray_icon.setIcon(QIcon(str(self._icon_path)))
        else:
            self._tray_icon.setIcon(self._q_app.windowIcon())

        menu = QMenu()
        show_action = QAction("Show", self)
        show_action.triggered.connect(self._restore_from_tray)
        menu.addAction(show_action)

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self._tray_quit)
        menu.addAction(quit_action)

        self._tray_icon.setContextMenu(menu)
        self._tray_icon.activated.connect(self._on_tray_activated)
        self._tray_icon.show()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._restore_from_tray()

    def _restore_from_tray(self):
        if self._tray_icon:
            self._tray_icon.hide()
            self._tray_icon = None
        self._do_restore()

    def _do_restore(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()
        if self.widget and self.config.get('ui', 'widget_enabled', default=True):
            self.widget.show()

    def _tray_quit(self):
        if self._tray_icon:
            self._tray_icon.hide()
            self._tray_icon = None
        self._full_quit()

    def _full_quit(self):
        self._cleanup()
        self._q_app.quit()

    def _cleanup(self):
        if self._tray_icon:
            self._tray_icon.hide()
            self._tray_icon = None
        if self._instance_listener:
            self._instance_listener.close()
        self.hotkey_manager.cleanup()
        self.clipboard_mgr.stop_monitoring()
        if self.widget:
            self.widget.close()

    # ── Single-instance listener ──

    def _start_instance_listener(self):
        try:
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind(("127.0.0.1", 19847))
            srv.listen(1)
            self._instance_listener = srv
            threading.Thread(target=self._instance_listen_loop, daemon=True).start()
        except OSError:
            pass

    def _instance_listen_loop(self):
        while True:
            try:
                conn, _ = self._instance_listener.accept()
                data = conn.recv(16)
                conn.close()
                if data == b"SHOW":
                    self.restore_signal.emit()
            except OSError:
                break

    # ── Run ──

    def run(self):
        self.show()
        sys.exit(self._q_app.exec())
