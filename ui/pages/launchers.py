"""Launchers page — launcher list with search/filter + add form."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QLineEdit, QScrollArea, QMessageBox, QComboBox,
    QDialog, QGridLayout, QCheckBox, QFileDialog,
)
from PyQt6.QtCore import Qt

from modules.launcher import LaunchItem
from ui.styles import COLORS, font, R


class LaunchersPage(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self._entry_widgets = {}
        self._fingerprint = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        card = QFrame()
        card.setProperty("card", True)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(10, 8, 10, 8)

        # Title
        title = QLabel("Launcher")
        title.setFont(font(16, "bold"))
        card_layout.addWidget(title)

        # Search + type filter
        filter_row = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search...")
        self._search.setFixedHeight(30)
        self._search.textChanged.connect(lambda: self._apply_filter())
        filter_row.addWidget(self._search, stretch=1)

        self._type_filter = QComboBox()
        self._type_filter.addItems(["All", "app", "terminal", "url", "folder"])
        self._type_filter.setFixedWidth(100)
        self._type_filter.setFixedHeight(30)
        self._type_filter.currentTextChanged.connect(lambda: self._apply_filter())
        filter_row.addWidget(self._type_filter)
        card_layout.addLayout(filter_row)

        # Add form
        form = QFrame()
        form.setProperty("section", True)
        form_layout = QHBoxLayout(form)
        form_layout.setContentsMargins(4, 6, 4, 6)

        self._add_type = QComboBox()
        self._add_type.addItems(["app", "terminal", "url", "folder"])
        self._add_type.setFixedWidth(95)
        self._add_type.setFixedHeight(30)
        self._add_type.currentTextChanged.connect(self._on_type_change)
        form_layout.addWidget(self._add_type)

        self._add_terminal_type = QComboBox()
        self._add_terminal_type.addItems(["powershell", "wsl", "cmd"])
        self._add_terminal_type.setFixedWidth(95)
        self._add_terminal_type.setFixedHeight(30)
        self._add_terminal_type.hide()
        form_layout.addWidget(self._add_terminal_type)

        self._add_name = QLineEdit()
        self._add_name.setPlaceholderText("Name")
        self._add_name.setFixedWidth(100)
        form_layout.addWidget(self._add_name)

        self._add_path = QLineEdit()
        self._add_path.setPlaceholderText("Path / Command / URL")
        form_layout.addWidget(self._add_path, stretch=1)

        self._browse_btn = QPushButton("…")
        self._browse_btn.setFixedSize(30, 30)
        self._browse_btn.clicked.connect(self._browse_path)
        form_layout.addWidget(self._browse_btn)

        self._add_voice = QLineEdit()
        self._add_voice.setPlaceholderText("Voice (opt)")
        self._add_voice.setFixedWidth(90)
        form_layout.addWidget(self._add_voice)

        add_btn = QPushButton("+")
        add_btn.setFixedSize(32, 30)
        add_btn.setProperty("accent", True)
        add_btn.setFont(font(14, "bold"))
        add_btn.clicked.connect(self._add_item)
        form_layout.addWidget(add_btn)

        card_layout.addWidget(form)

        # Scrollable list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._list_widget = QWidget()
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(2)
        scroll.setWidget(self._list_widget)
        card_layout.addWidget(scroll, stretch=1)

        layout.addWidget(card)

        self._on_type_change(self._add_type.currentText())
        self.refresh()

    def _on_type_change(self, value: str):
        self._add_terminal_type.setVisible(value == "terminal")
        self._browse_btn.setVisible(value in ("app", "folder"))
        placeholders = {"terminal": "Command", "url": "URL"}
        self._add_path.setPlaceholderText(placeholders.get(value, "Path"))

    def _browse_path(self):
        if self._add_type.currentText() == "folder":
            path = QFileDialog.getExistingDirectory(self, "Select folder")
        else:
            path, _ = QFileDialog.getOpenFileName(
                self, "Select file", "",
                "Executables (*.exe);;Shortcuts (*.lnk);;All files (*.*)"
            )
        if path:
            self._add_path.setText(path)

    def _add_item(self):
        name = self._add_name.text().strip()
        path = self._add_path.text().strip()
        item_type = self._add_type.currentText()
        voice = self._add_voice.text().strip() or None
        terminal_type = self._add_terminal_type.currentText() if item_type == "terminal" else None

        if not name or not path:
            label = "Name and command required" if item_type == "terminal" else "Name and path required"
            QMessageBox.warning(self, "Missing Info", label)
            return

        item = LaunchItem(name=name, path=path, item_type=item_type,
                          voice_phrase=voice, terminal_type=terminal_type)
        if self.app.launcher.add_item(item):
            self.app.commands._refresh_launcher_commands()
            self.refresh()
            self.app.mark_dirty("home", "voice")
            self._add_name.clear()
            self._add_path.clear()
            self._add_voice.clear()
        else:
            QMessageBox.warning(self, "Exists", "Item with that name already exists")

    def refresh(self):
        all_items = self.app.launcher.get_all_items()
        fav_launchers = set(self.app.config.get('favorites', 'launchers', default=[]))
        fingerprint = tuple(
            (i.name, i.path, i.item_type, i.voice_phrase, i.terminal_type, i.name in fav_launchers)
            for i in all_items
        )

        if self._fingerprint != fingerprint:
            _clear(self._list_layout)
            self._entry_widgets = {}
            for item in all_items:
                w = self._build_entry(item, item.name in fav_launchers)
                self._entry_widgets[item.name] = (w, item)
            self._fingerprint = fingerprint

        self._apply_filter()

    def _apply_filter(self):
        search_q = self._search.text().strip().lower()
        type_filter = self._type_filter.currentText()

        for name, (widget, item) in self._entry_widgets.items():
            visible = True
            if type_filter != "All" and item.item_type != type_filter:
                visible = False
            if search_q:
                haystack = f"{item.name} {item.path} {item.voice_phrase or ''}".lower()
                if search_q not in haystack:
                    visible = False
            widget.setVisible(visible)

    def _build_entry(self, item: LaunchItem, is_fav: bool) -> QWidget:
        entry = QFrame()
        entry.setStyleSheet(
            f"QFrame {{ background: {COLORS['surface_light']}; border-radius: {R['md']}px; }}"
        )
        row = QHBoxLayout(entry)
        row.setContentsMargins(10, 6, 4, 6)

        name_lbl = QLabel(item.name)
        name_lbl.setFont(font(13, "bold"))
        row.addWidget(name_lbl)

        type_text = item.terminal_type if item.item_type == "terminal" and item.terminal_type else item.item_type
        type_lbl = QLabel(type_text)
        type_lbl.setFont(font(11))
        type_lbl.setStyleSheet(
            f"background: {COLORS['surface']}; color: {COLORS['text_muted']}; "
            f"border-radius: {R['sm']}px; padding: 2px 8px;"
        )
        row.addWidget(type_lbl)

        if item.voice_phrase:
            voice_lbl = QLabel(f'"{item.voice_phrase}"')
            voice_lbl.setFont(font(12))
            voice_lbl.setStyleSheet(f"color: {COLORS['success']};")
            row.addWidget(voice_lbl)

        row.addStretch()

        # Action buttons
        fav_btn = QPushButton("❤️" if is_fav else "🤍")
        fav_btn.setFixedSize(34, 30)
        fav_btn.setFont(font(14, family="Segoe UI Emoji"))
        fav_btn.setProperty("flat", True)
        fav_btn.clicked.connect(lambda: self._toggle_fav(item.name))
        row.addWidget(fav_btn)

        launch_btn = QPushButton("▶️")
        launch_btn.setFixedSize(34, 30)
        launch_btn.setFont(font(14, family="Segoe UI Emoji"))
        launch_btn.setProperty("flat", True)
        launch_btn.clicked.connect(lambda: self.app.launcher.launch(item))
        row.addWidget(launch_btn)

        edit_btn = QPushButton("✏️")
        edit_btn.setFixedSize(34, 30)
        edit_btn.setFont(font(14, family="Segoe UI Emoji"))
        edit_btn.setProperty("flat", True)
        edit_btn.clicked.connect(lambda: self._edit_item(item))
        row.addWidget(edit_btn)

        del_btn = QPushButton("🗑️")
        del_btn.setFixedSize(34, 30)
        del_btn.setFont(font(14, family="Segoe UI Emoji"))
        del_btn.setProperty("flat", True)
        del_btn.clicked.connect(lambda: self._delete_item(item.name))
        row.addWidget(del_btn)

        self._list_layout.addWidget(entry)
        return entry

    def _toggle_fav(self, name: str):
        self.app.toggle_favorite('launchers', name)
        self._fingerprint = None
        self.refresh()

    def _edit_item(self, item: LaunchItem):
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Edit: {item.name}")
        dlg.setFixedSize(460, 300)
        dlg.setStyleSheet(f"QDialog {{ background: {COLORS['bg']}; }}")

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(20, 16, 20, 16)

        title = QLabel("Edit Launcher Item")
        title.setFont(font(15, "bold"))
        layout.addWidget(title)

        grid = QGridLayout()
        grid.setColumnStretch(1, 1)

        # Name
        grid.addWidget(QLabel("Name:"), 0, 0)
        name_entry = QLineEdit(item.name)
        grid.addWidget(name_entry, 0, 1)

        # Type
        grid.addWidget(QLabel("Type:"), 1, 0)
        type_combo = QComboBox()
        type_combo.addItems(["app", "terminal", "url", "folder", "command", "script"])
        type_combo.setCurrentText(item.item_type)
        grid.addWidget(type_combo, 1, 1)

        # Path
        grid.addWidget(QLabel("Path:"), 2, 0)
        path_row = QHBoxLayout()
        path_entry = QLineEdit(item.path)
        path_row.addWidget(path_entry)
        browse = QPushButton("...")
        browse.setFixedWidth(36)
        browse.clicked.connect(lambda: self._browse_for_entry(type_combo, path_entry))
        path_row.addWidget(browse)
        path_container = QWidget()
        path_container.setLayout(path_row)
        grid.addWidget(path_container, 2, 1)

        # Voice
        grid.addWidget(QLabel("Voice:"), 3, 0)
        voice_entry = QLineEdit(item.voice_phrase or "")
        grid.addWidget(voice_entry, 3, 1)

        # Shell
        shell_label = QLabel("Shell:")
        shell_combo = QComboBox()
        shell_combo.addItems(["powershell", "wsl", "cmd"])
        shell_combo.setCurrentText(item.terminal_type or "powershell")

        def on_type_change(val):
            show_shell = val == "terminal"
            shell_label.setVisible(show_shell)
            shell_combo.setVisible(show_shell)
            browse.setVisible(val in ("app", "folder"))

        grid.addWidget(shell_label, 4, 0)
        grid.addWidget(shell_combo, 4, 1)
        type_combo.currentTextChanged.connect(on_type_change)
        on_type_change(item.item_type)

        layout.addLayout(grid)
        layout.addStretch()

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
            new_name = name_entry.text().strip()
            if not new_name:
                return
            item.name = new_name
            item.item_type = type_combo.currentText()
            item.path = path_entry.text().strip()
            item.voice_phrase = voice_entry.text().strip() or None
            item.terminal_type = shell_combo.currentText() if item.item_type == "terminal" else None
            self.app.launcher._save_items()
            self.app.commands._refresh_launcher_commands()
            self._fingerprint = None
            self.refresh()
            self.app.mark_dirty("home", "voice")
            self.app.set_status(f"Updated '{new_name}'", COLORS["success"])
            dlg.accept()

        save_btn.clicked.connect(do_save)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

        dlg.exec()

    def _browse_for_entry(self, type_combo, path_entry):
        if type_combo.currentText() == "folder":
            p = QFileDialog.getExistingDirectory(self, "Select folder")
        else:
            p, _ = QFileDialog.getOpenFileName(
                self, "Select file", "",
                "Executables (*.exe);;Shortcuts (*.lnk);;All files (*.*)"
            )
        if p:
            path_entry.setText(p)

    def _delete_item(self, name: str):
        reply = QMessageBox.question(
            self, "Delete", f"Delete launcher '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            if self.app.launcher.remove_item(name):
                self.app.commands._refresh_launcher_commands()
                self._fingerprint = None
                self.refresh()
                self.app.mark_dirty("home", "voice")


def _clear(layout):
    while layout.count():
        child = layout.takeAt(0)
        if child.widget():
            child.widget().deleteLater()
        elif child.layout():
            _clear(child.layout())
