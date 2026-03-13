"""Voice page — list of available voice commands."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QFrame,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from modules.voice import COMMAND_MODULES
from ui.styles import COLORS, font, R


class VoicePage(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self._init_ui()

    def _init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)

        from PyQt6.QtWidgets import QScrollArea
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)

        self._container = QWidget()
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(4, 4, 4, 4)
        self._layout.setSpacing(6)
        scroll.setWidget(self._container)

        self.refresh()

    def refresh(self):
        _clear(self._layout)

        self._add_info_banner()

        sections = []

        sections.append(("Search", "NLP — just ask naturally", [
            ('"search/google/look up [query]"',          "Prefix stripped, searches the query"),
            ('"what is / who is / how to ..."',          "Full phrase used as search query"),
        ]))

        sections.append(("Notes & Timers", "NLP — natural language parsing", [
            ('"note [text]"',                            "Save to notes pad"),
            ('"timer for [duration]"',                   "Countdown — parses natural durations"),
        ]))

        sections.append(("Reminders", "NLP — natural language dates & times", [
            ('"remind me to [task] [when]"',             "One-shot — times, dates, days of week"),
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
            self._add_section(title, subtitle, commands)

        self._layout.addStretch()

    def _add_info_banner(self):
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: {R['md']}px;
            }}
        """)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        title_lbl = QLabel("HOW MATCHING WORKS")
        title_lbl.setFont(font(11, "bold"))
        title_lbl.setStyleSheet(f"color: {COLORS['text_muted']}; background: transparent; border: none;")
        layout.addWidget(title_lbl)

        steps = [
            ("1", "Search intent",   "search / google / what is / who is / how to ..."),
            ("2", "Exact phrase",    "command matched word-for-word"),
            ("3", "Fuzzy match",     "token overlap ≥75%, stop words (a/the/please...) ignored"),
            ("4", "Launcher phrase", "configured voice phrase on the launcher tab"),
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
            lbl.setFixedWidth(115)
            d = QLabel(desc)
            d.setFont(font(12))
            d.setStyleSheet(f"color: {COLORS['text_dim']}; background: transparent; border: none;")
            row.addWidget(n)
            row.addWidget(lbl)
            row.addWidget(d)
            row.addStretch()
            layout.addLayout(row)

        self._layout.addWidget(frame)

    def _add_section(self, title: str, subtitle: str, commands: list):
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


def _clear(layout):
    while layout.count():
        child = layout.takeAt(0)
        if child.widget():
            child.widget().deleteLater()
        elif child.layout():
            _clear(child.layout())
