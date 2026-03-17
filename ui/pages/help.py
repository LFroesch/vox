"""Help page — app overview, feature guides, and voice command reference."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QFrame, QScrollArea,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from modules.voice import COMMAND_MODULES
from ui.styles import COLORS, font, R


class HelpPage(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self._init_ui()

    def _init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)

        self._container = QWidget()
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(4, 4, 4, 4)
        self._layout.setSpacing(10)
        scroll.setWidget(self._container)

        self.refresh()

    def refresh(self):
        _clear(self._layout)

        self._add_overview()
        self._add_features()
        self._add_voice_section()

        self._layout.addStretch()

    # ── Overview ────────────────────────────────────────

    def _add_overview(self):
        frame = self._card()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        self._heading(layout, "GETTING STARTED")

        tips = [
            (self.app.config.get('hotkeys', 'voice_record', default='F9').upper(),
             "Hold to record a voice command, release to execute"),
            ("Widget", "Always-on-top floating panel — mic button, quick actions, reminder countdowns"),
            ("Tray", "Minimize to system tray. Double-click tray icon to restore"),
            ("Favorites", "Click the heart on any launcher, layout, or workflow to pin it to Quick Actions on the Home page and widget"),
        ]
        for key, desc in tips:
            row = QHBoxLayout()
            row.setSpacing(8)
            k = QLabel(key)
            k.setFont(font(12, "bold"))
            k.setStyleSheet(f"color: {COLORS['accent']}; background: transparent; border: none;")
            k.setFixedWidth(70)
            d = QLabel(desc)
            d.setFont(font(12))
            d.setStyleSheet(f"color: {COLORS['text_dim']}; background: transparent; border: none;")
            d.setWordWrap(True)
            row.addWidget(k)
            row.addWidget(d, 1)
            layout.addLayout(row)

        self._layout.addWidget(frame)

    # ── Features ────────────────────────────────────────

    def _add_features(self):
        frame = self._card()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        self._heading(layout, "FEATURES")

        features = [
            ("Launchers", "Add apps, terminals, URLs, folders, and scripts. "
             "Give any item a voice phrase to launch it hands-free. "
             "Terminal items can run commands in PowerShell or WSL."),
            ("Layouts", "Save your current window arrangement and restore it by name or voice. "
             "Handles multi-monitor setups and multiple windows of the same app. "
             "Layouts are pure positioning — use workflows to also launch apps."),
            ("Workflows", "Batch-launch a sequence of apps and commands, then optionally apply a layout. "
             "Import steps from existing launchers. Run via voice: \"run [name]\" or \"start [name]\"."),
            ("Reminders", "Set countdown timers, alarms at specific times, or recurring schedules. "
             "Voice: \"set timer 10 minutes\", \"remind me to X at 3pm\", \"every weekday at 9am check email\". "
             "No time given defaults to tomorrow at 9am. Fired reminders persist so you can snooze or dismiss them."),
            ("Clipboard", "Automatically tracks clipboard history. Save frequently used text as snippets for quick access."),
            ("Notes", "Say \"note [text]\" or \"take a note [text]\" to append to your notes pad (Home tab)."),
        ]
        for title, desc in features:
            t = QLabel(title)
            t.setFont(font(12, "bold"))
            t.setStyleSheet(f"color: {COLORS['text']}; background: transparent; border: none;")
            layout.addWidget(t)
            d = QLabel(desc)
            d.setFont(font(12))
            d.setStyleSheet(f"color: {COLORS['text_dim']}; background: transparent; border: none;")
            d.setWordWrap(True)
            d.setContentsMargins(0, 0, 0, 4)
            layout.addWidget(d)

        self._layout.addWidget(frame)

    # ── Voice Commands ──────────────────────────────────

    def _add_voice_section(self):
        self._section_heading("VOICE COMMANDS")
        self._add_matching_banner()

        sections = []

        sections.append(("Search", "NLP — just ask naturally", [
            ('"search/google/look up [query]"',          "Prefix stripped, searches the query"),
            ('"what is / who is / how to ..."',          "Full phrase used as search query"),
        ]))

        sections.append(("Notes & Timers", "NLP — natural language parsing", [
            ('"note [text]"',                            "Save to notes pad"),
            ('"timer for [duration]"',                   "Countdown — \"5 minutes\", \"half an hour\", \"a couple minutes\""),
        ]))

        sections.append(("Reminders", "NLP — natural language dates & times", [
            ('"remind me to [task] [when]"',             "One-shot — times, dates, days of week"),
            ('"remind me to [task]"',                    "No time given → defaults to tomorrow at 9am"),
            ('"remind me every [schedule] to [task]"',   "Recurring — daily, weekdays, interval, etc."),
        ]))

        layouts = self.app.layout_manager.get_layout_names()
        if layouts:
            cmds = [(f'"{n}" / "{n} layout" / "swap {n}"', "Apply window layout") for n in layouts]
            sections.append(("Layouts", "exact phrase — layout name + optional keyword", cmds))

        launcher_cmds = []
        for item in self.app.launcher.get_all_items():
            if item.voice_phrase:
                launcher_cmds.append((f'"{item.voice_phrase}"', f"Launch {item.name}"))
        if launcher_cmds:
            sections.append(("Launchers", "exact phrase as configured on the launcher tab", launcher_cmds))

        for module_name, module_info in COMMAND_MODULES.items():
            cmds = []
            for cmd_name, cmd_info in module_info["commands"].items():
                phrases = cmd_info["phrases"][:2]
                phrase_str = " / ".join(f'"{p}"' for p in phrases)
                if len(cmd_info["phrases"]) > 2:
                    phrase_str += " ..."
                cmds.append((phrase_str, cmd_info["description"]))
            sections.append((module_name.title(), "fuzzy match — token overlap, variations & stop words ignored", cmds))

        for title, subtitle, commands in sections:
            self._add_command_section(title, subtitle, commands)

    def _add_matching_banner(self):
        frame = self._card()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        title_lbl = QLabel("HOW MATCHING WORKS")
        title_lbl.setFont(font(11, "bold"))
        title_lbl.setStyleSheet(f"color: {COLORS['text_muted']}; background: transparent; border: none;")
        layout.addWidget(title_lbl)

        steps = [
            ("1", "Notes & Reminders", "\"note ...\", \"remind me ...\", \"timer ...\" — NLP parsed first"),
            ("2", "Search intent",     "search / google / what is / who is / how to ..."),
            ("3", "Exact phrase",      "command matched word-for-word"),
            ("4", "Fuzzy match",       "token overlap ≥75%, stop words (a/the/please...) ignored"),
            ("5", "Launcher phrase",   "configured voice phrase on the launcher tab"),
        ]
        for num, label, desc in steps:
            row = QHBoxLayout()
            row.setSpacing(6)
            n = QLabel(num)
            n.setFont(font(11, "bold"))
            n.setStyleSheet(f"color: {COLORS['accent']}; background: transparent; border: none;")
            n.setFixedWidth(14)
            lbl = QLabel(label)
            lbl.setFont(font(12, "bold"))
            lbl.setStyleSheet(f"color: {COLORS['text']}; background: transparent; border: none;")
            lbl.setFixedWidth(140)
            d = QLabel(desc)
            d.setFont(font(12))
            d.setStyleSheet(f"color: {COLORS['text_dim']}; background: transparent; border: none;")
            row.addWidget(n)
            row.addWidget(lbl)
            row.addWidget(d)
            row.addStretch()
            layout.addLayout(row)

        self._layout.addWidget(frame)

    def _add_command_section(self, title: str, subtitle: str, commands: list):
        row = QHBoxLayout()
        row.setSpacing(6)
        t = QLabel(title.upper())
        t.setFont(font(11, "bold"))
        t.setStyleSheet(f"color: {COLORS['text_muted']};")
        s = QLabel(f"— {subtitle}")
        s.setFont(font(11))
        s.setStyleSheet(f"color: {COLORS['text_dim']};")
        row.addWidget(t)
        row.addWidget(s)
        row.addStretch()
        self._layout.addLayout(row)

        table = QTableWidget()
        table.setColumnCount(2)
        table.setRowCount(len(commands))
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        table.setShowGrid(False)

        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        row_height = 28
        table.verticalHeader().setDefaultSectionSize(row_height)
        table.setFixedHeight(row_height * len(commands) + 4)

        table.setStyleSheet(f"""
            QTableWidget {{
                background: {COLORS['surface_light']};
                border: 1px solid {COLORS['border']};
                border-radius: {R['md']}px;
                gridline-color: transparent;
            }}
            QTableWidget::item {{
                padding: 3px 10px;
            }}
        """)

        for i, (phrase, desc) in enumerate(commands):
            phrase_item = QTableWidgetItem(phrase)
            phrase_item.setFont(font(13))
            phrase_item.setForeground(QColor(COLORS['success']))

            desc_item = QTableWidgetItem(desc)
            desc_item.setFont(font(13))
            desc_item.setForeground(QColor(COLORS['text_dim']))

            table.setItem(i, 0, phrase_item)
            table.setItem(i, 1, desc_item)

        self._layout.addWidget(table)

    # ── Helpers ─────────────────────────────────────────

    def _card(self) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: {R['md']}px;
            }}
        """)
        return frame

    def _heading(self, layout, text: str):
        lbl = QLabel(text)
        lbl.setFont(font(11, "bold"))
        lbl.setStyleSheet(f"color: {COLORS['text_muted']}; background: transparent; border: none;")
        layout.addWidget(lbl)

    def _section_heading(self, text: str):
        lbl = QLabel(text)
        lbl.setFont(font(13, "bold"))
        lbl.setStyleSheet(f"color: {COLORS['text_muted']};")
        lbl.setContentsMargins(0, 6, 0, 2)
        self._layout.addWidget(lbl)


def _clear(layout):
    while layout.count():
        child = layout.takeAt(0)
        if child.widget():
            child.widget().deleteLater()
        elif child.layout():
            _clear(child.layout())
