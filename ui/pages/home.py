"""Home page — Quick Actions (collapsible) + Voice Log / Notes sub-tabs."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QTextEdit, QGridLayout, QFrame,
)
from PyQt6.QtCore import Qt
from pathlib import Path

from ui.styles import COLORS, font, R


class HomePage(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self._qa_expanded = True
        self._last_quick_actions = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # -- Quick Actions collapsible --
        self._qa_btn = QPushButton("▾  Quick Actions")
        self._qa_btn.setFont(font(13, "bold"))
        self._qa_btn.setProperty("flat", True)
        self._qa_btn.setStyleSheet(
            f"text-align: left; padding: 8px 12px; background: {COLORS['surface_light']}; "
            f"border: 1px solid {COLORS['border']}; border-radius: {R['lg']}px; color: {COLORS['text_dim']};"
        )
        self._qa_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._qa_btn.clicked.connect(self._toggle_quick_actions)
        layout.addWidget(self._qa_btn)

        self._qa_container = QFrame()
        self._qa_container.setProperty("card", True)
        self._qa_layout = QVBoxLayout(self._qa_container)
        self._qa_layout.setContentsMargins(6, 4, 6, 4)
        layout.addWidget(self._qa_container)

        # -- Sub-tabs: Voice Log | Notes --
        tabs = QTabWidget()
        layout.addWidget(tabs, stretch=1)

        # Voice Log tab
        voice_log_widget = QWidget()
        vl_layout = QVBoxLayout(voice_log_widget)
        vl_layout.setContentsMargins(4, 4, 4, 4)

        self.voice_log_text = QTextEdit()
        self.voice_log_text.setReadOnly(True)
        self.voice_log_text.setFont(font(13, family="Consolas"))
        vl_layout.addWidget(self.voice_log_text)

        vl_btn_row = QHBoxLayout()
        vl_btn_row.addStretch()
        clear_btn = QPushButton("Clear")
        clear_btn.setFixedSize(70, 30)
        clear_btn.clicked.connect(self._clear_voice_log)
        vl_btn_row.addWidget(clear_btn)
        vl_layout.addLayout(vl_btn_row)

        tabs.addTab(voice_log_widget, "Voice Log")

        # Notes tab
        notes_widget = QWidget()
        notes_layout = QVBoxLayout(notes_widget)
        notes_layout.setContentsMargins(4, 4, 4, 4)

        self.notes_text = QTextEdit()
        self.notes_text.setFont(font(13, family="Consolas"))
        notes_layout.addWidget(self.notes_text)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        reload_btn = QPushButton("Reload")
        reload_btn.setFixedSize(70, 30)
        reload_btn.clicked.connect(self.load_notes)
        btn_row.addWidget(reload_btn)

        save_btn = QPushButton("Save")
        save_btn.setFixedSize(70, 30)
        save_btn.setProperty("accent", True)
        save_btn.clicked.connect(self.save_notes)
        btn_row.addWidget(save_btn)

        notes_layout.addLayout(btn_row)
        tabs.addTab(notes_widget, "Notes")

        # Load initial content
        self._load_voice_log()
        self.load_notes()
        self.refresh_quick_actions()

    # -- Quick Actions --
    def _toggle_quick_actions(self):
        self._qa_expanded = not self._qa_expanded
        self._qa_btn.setText("▾  Quick Actions" if self._qa_expanded else "▸  Quick Actions")
        self._qa_container.setVisible(self._qa_expanded)

    def refresh_quick_actions(self):
        fav_layouts = self.app.config.get('favorites', 'layouts', default=[])
        fav_launchers = self.app.config.get('favorites', 'launchers', default=[])
        fav_workflows = self.app.config.get('favorites', 'workflows', default=[])

        layout_actions = []
        for name in self.app.layout_manager.get_layout_names():
            if name in fav_layouts:
                layout_actions.append(name)

        launcher_actions = []
        for item in self.app.launcher.get_all_items():
            if item.name in fav_launchers:
                launcher_actions.append(item)

        workflow_actions = []
        wm = getattr(self.app, 'workflow_manager', None)
        if wm:
            for name in wm.get_names():
                if name in fav_workflows:
                    workflow_actions.append(name)

        new_state = (tuple(fav_layouts), tuple(fav_launchers), tuple(fav_workflows),
                     tuple(layout_actions), tuple(i.name for i in launcher_actions),
                     tuple(workflow_actions))
        if self._last_quick_actions == new_state:
            return
        self._last_quick_actions = new_state

        # Clear
        while self._qa_layout.count():
            child = self._qa_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
            elif child.layout():
                _clear_layout(child.layout())

        if not layout_actions and not launcher_actions and not workflow_actions:
            lbl = QLabel("\u2665 Favorite layouts, launchers, or workflows to pin them here")
            lbl.setStyleSheet(f"color: {COLORS['text_dim']};")
            lbl.setFont(font(12))
            self._qa_layout.addWidget(lbl)
            return

        cols = 4
        if layout_actions:
            sec = QLabel("Layouts")
            sec.setFont(font(11, "bold"))
            sec.setStyleSheet(f"color: {COLORS['text_muted']};")
            self._qa_layout.addWidget(sec)

            grid = QGridLayout()
            grid.setSpacing(3)
            for i, name in enumerate(layout_actions):
                btn = QPushButton(name)
                btn.setFixedHeight(28)
                btn.setFont(font(12))
                btn.setStyleSheet(
                    f"background: {COLORS['surface']}; color: {COLORS['text_dim']}; "
                    f"border: 1px solid {COLORS['border']}; border-radius: 14px; padding: 2px 10px;"
                )
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.clicked.connect(lambda checked, n=name: self.app.quick_load_layout(n))
                grid.addWidget(btn, i // cols, i % cols)
            container = QWidget()
            container.setLayout(grid)
            self._qa_layout.addWidget(container)

        if launcher_actions:
            sec = QLabel("Launchers")
            sec.setFont(font(11, "bold"))
            sec.setStyleSheet(f"color: {COLORS['text_muted']};")
            self._qa_layout.addWidget(sec)

            grid = QGridLayout()
            grid.setSpacing(3)
            for i, item in enumerate(launcher_actions):
                btn = QPushButton(item.name)
                btn.setFixedHeight(28)
                btn.setFont(font(12))
                btn.setStyleSheet(
                    f"background: {COLORS['surface']}; color: {COLORS['text_dim']}; "
                    f"border: 1px solid {COLORS['border']}; border-radius: 14px; padding: 2px 10px;"
                )
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.clicked.connect(lambda checked, it=item: self.app.launcher.launch(it))
                grid.addWidget(btn, i // cols, i % cols)
            container = QWidget()
            container.setLayout(grid)
            self._qa_layout.addWidget(container)

        if workflow_actions:
            sec = QLabel("Workflows")
            sec.setFont(font(11, "bold"))
            sec.setStyleSheet(f"color: {COLORS['text_muted']};")
            self._qa_layout.addWidget(sec)

            grid = QGridLayout()
            grid.setSpacing(3)
            for i, name in enumerate(workflow_actions):
                btn = QPushButton(name)
                btn.setFixedHeight(28)
                btn.setFont(font(12))
                btn.setStyleSheet(
                    f"background: {COLORS['surface']}; color: {COLORS['text_dim']}; "
                    f"border: 1px solid {COLORS['border']}; border-radius: 14px; padding: 2px 10px;"
                )
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.clicked.connect(lambda checked, n=name: self.app.run_workflow(n))
                grid.addWidget(btn, i // cols, i % cols)
            container = QWidget()
            container.setLayout(grid)
            self._qa_layout.addWidget(container)

    # -- Voice Log --
    def _load_voice_log(self):
        log_path = Path(self.app.config.config_dir) / "voice_log.txt"
        if log_path.exists():
            try:
                lines = log_path.read_text(encoding="utf-8").splitlines()
                self.voice_log_text.setPlainText("\n".join(reversed(lines)))
            except Exception as e:
                print(f"Failed to load voice log: {e}")

    def _clear_voice_log(self):
        self.voice_log_text.clear()
        log_path = Path(self.app.config.config_dir) / "voice_log.txt"
        try:
            log_path.write_text("", encoding="utf-8")
        except Exception:
            pass
        self.app.set_status("Voice log cleared", COLORS["success"])

    def prepend_voice_log(self, entry: str):
        cursor = self.voice_log_text.textCursor()
        cursor.movePosition(cursor.MoveOperation.Start)
        cursor.insertText(entry)
        self.voice_log_text.setTextCursor(cursor)
        # Save to file
        log_path = Path(self.app.config.config_dir) / "voice_log.txt"
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(entry)
        except Exception:
            pass

    # -- Notes --
    def load_notes(self):
        notes_path = Path(self.app.config.config_dir) / "notes.md"
        if notes_path.exists():
            try:
                self.notes_text.setPlainText(notes_path.read_text(encoding="utf-8"))
            except Exception as e:
                print(f"Failed to load notes: {e}")
        else:
            self.notes_text.clear()

    def save_notes(self):
        notes_path = Path(self.app.config.config_dir) / "notes.md"
        try:
            notes_path.write_text(self.notes_text.toPlainText(), encoding="utf-8")
            self.app.set_status("Notes saved", COLORS["success"])
        except Exception as e:
            print(f"Failed to save notes: {e}")

    def append_note(self, text: str):
        self.notes_text.append(text)


def _clear_layout(layout):
    while layout.count():
        child = layout.takeAt(0)
        if child.widget():
            child.widget().deleteLater()
        elif child.layout():
            _clear_layout(child.layout())
