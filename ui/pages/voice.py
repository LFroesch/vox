"""Voice page — list of available voice commands."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QFrame,
)

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

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)

        self._container = QWidget()
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(4, 4, 4, 4)
        self._layout.setSpacing(2)
        scroll.setWidget(self._container)

        self.refresh()

    def refresh(self):
        _clear(self._layout)

        # Special commands
        self._add_section("Special", [
            ('"note [text]" / "take note [text]"', "Save to notes pad"),
        ])

        # Layout commands
        layouts = self.app.layout_manager.get_layout_names()
        if layouts:
            cmds = [(f'"{n}" or "{n} layout"', "Apply window layout") for n in layouts]
            self._add_section("Layouts", cmds)

        # Launcher commands
        launcher_cmds = []
        for item in self.app.launcher.get_all_items():
            if item.voice_phrase:
                launcher_cmds.append((f'"{item.voice_phrase}"', f"Launch {item.name}"))
        if launcher_cmds:
            self._add_section("Launchers", launcher_cmds)

        # Built-in commands by module
        for module_name, module_info in COMMAND_MODULES.items():
            cmds = []
            for cmd_name, cmd_info in module_info["commands"].items():
                phrases = cmd_info["phrases"][:2]
                phrase_str = " / ".join(f'"{p}"' for p in phrases)
                if len(cmd_info["phrases"]) > 2:
                    phrase_str += " ..."
                cmds.append((phrase_str, cmd_info["description"]))
            self._add_section(module_name.title(), cmds)

        self._layout.addStretch()

    def _add_section(self, title: str, commands: list):
        header = QFrame()
        header.setProperty("section", True)
        header.setStyleSheet(
            f"background: {COLORS['surface']}; border: 1px solid {COLORS['border']}; "
            f"border-radius: {R['md']}px; padding: 6px 10px;"
        )
        h_layout = QVBoxLayout(header)
        h_layout.setContentsMargins(10, 6, 10, 6)
        lbl = QLabel(title.upper())
        lbl.setFont(font(11, "bold"))
        lbl.setStyleSheet(f"color: {COLORS['text_muted']}; border: none;")
        h_layout.addWidget(lbl)
        self._layout.addWidget(header)

        for phrase, description in commands:
            row = QHBoxLayout()
            row.setContentsMargins(15, 1, 5, 1)

            phrase_lbl = QLabel(phrase)
            phrase_lbl.setFont(font(13))
            phrase_lbl.setStyleSheet(f"color: {COLORS['success']};")
            phrase_lbl.setMinimumWidth(280)
            row.addWidget(phrase_lbl)

            desc_lbl = QLabel(description)
            desc_lbl.setFont(font(13))
            desc_lbl.setStyleSheet(f"color: {COLORS['text_dim']};")
            row.addWidget(desc_lbl, stretch=1)

            wrapper = QWidget()
            wrapper.setLayout(row)
            self._layout.addWidget(wrapper)


def _clear(layout):
    while layout.count():
        child = layout.takeAt(0)
        if child.widget():
            child.widget().deleteLater()
        elif child.layout():
            _clear(child.layout())
