"""Clipboard page — History (accordion) + Snippets sub-tabs."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QLineEdit, QScrollArea, QMessageBox, QTabWidget,
    QTextEdit, QDialog, QSizePolicy,
)
from datetime import datetime
from PyQt6.QtCore import Qt

from ui.styles import COLORS, font, R, fmt_time


def _icon_btn(text: str, tooltip: str = "") -> QPushButton:
    """Create a flat icon button with reliable rendering."""
    btn = QPushButton(text)
    btn.setFixedSize(34, 30)
    btn.setFont(font(14, family="Segoe UI Emoji"))
    btn.setProperty("flat", True)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    if tooltip:
        btn.setToolTip(tooltip)
    return btn


class ClipboardPage(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self._expanded_clip_idx = None
        self._expanded_snip_idx = None
        self._clip_fingerprint = None
        self._snip_fingerprint = None
        self._clip_frames = {}
        self._snip_frames = {}
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        card = QFrame()
        card.setProperty("card", True)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(10, 8, 10, 8)

        tabs = QTabWidget()
        card_layout.addWidget(tabs, stretch=1)
        layout.addWidget(card, stretch=1)

        # --- History tab ---
        history_w = QWidget()
        h_layout = QVBoxLayout(history_w)
        h_layout.setContentsMargins(4, 4, 4, 4)

        hdr = QHBoxLayout()
        self._clip_search = QLineEdit()
        self._clip_search.setPlaceholderText("Search history...")
        self._clip_search.setFixedHeight(26)
        self._clip_search.textChanged.connect(self._apply_clip_filter)
        hdr.addWidget(self._clip_search, stretch=1)
        clear_btn = QPushButton("Clear")
        clear_btn.setFixedSize(55, 26)
        clear_btn.clicked.connect(self._clear_clipboard)
        hdr.addWidget(clear_btn)
        h_layout.addLayout(hdr)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._clip_list = QWidget()
        self._clip_layout = QVBoxLayout(self._clip_list)
        self._clip_layout.setContentsMargins(0, 0, 0, 0)
        self._clip_layout.setSpacing(2)
        scroll.setWidget(self._clip_list)
        h_layout.addWidget(scroll, stretch=1)
        tabs.addTab(history_w, "History")

        # --- Snippets tab ---
        snippets_w = QWidget()
        s_layout = QVBoxLayout(snippets_w)
        s_layout.setContentsMargins(4, 4, 4, 4)

        shdr = QHBoxLayout()
        self._snip_search = QLineEdit()
        self._snip_search.setPlaceholderText("Search snippets...")
        self._snip_search.setFixedHeight(26)
        self._snip_search.textChanged.connect(self._apply_snip_filter)
        shdr.addWidget(self._snip_search, stretch=1)
        add_snip_btn = QPushButton("+ New")
        add_snip_btn.setFixedSize(65, 26)
        add_snip_btn.clicked.connect(self._new_snippet)
        shdr.addWidget(add_snip_btn)
        s_layout.addLayout(shdr)

        scroll2 = QScrollArea()
        scroll2.setWidgetResizable(True)
        scroll2.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._snip_list = QWidget()
        self._snip_layout = QVBoxLayout(self._snip_list)
        self._snip_layout.setContentsMargins(0, 0, 0, 0)
        self._snip_layout.setSpacing(2)
        scroll2.setWidget(self._snip_list)
        s_layout.addWidget(scroll2, stretch=1)
        tabs.addTab(snippets_w, "Snippets")

        self.refresh_history()
        self.refresh_snippets()

    # ── History ──────────────────────────────────────────────────────

    def refresh_history(self):
        history = self.app.clipboard_mgr.get_history(limit=15)
        fingerprint = tuple(e.content for e in history) if history else ()
        if self._clip_fingerprint == fingerprint:
            return
        self._clip_fingerprint = fingerprint
        self._expanded_clip_idx = None

        _clear(self._clip_layout)
        self._clip_frames = {}

        if not history:
            lbl = QLabel("No clipboard history")
            lbl.setStyleSheet(f"color: {COLORS['text_dim']};")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._clip_layout.addWidget(lbl)
            self._clip_layout.addStretch()
            return

        for i, entry in enumerate(history):
            frame = self._build_clip_entry(i, entry, False)
            self._clip_frames[i] = (frame, entry)

        self._clip_layout.addStretch()

    def _build_clip_entry(self, idx, entry, is_expanded):
        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame {{ background: {COLORS['surface_light']}; border-radius: {R['md']}px; }}"
        )
        v = QVBoxLayout(frame)
        v.setContentsMargins(8, 6, 8, 6)

        header = QHBoxLayout()
        try:
            ts_dt = datetime.strptime(entry.timestamp, "%Y-%m-%d %I:%M:%S %p")
            ts = fmt_time(ts_dt, seconds=False)
        except Exception:
            ts = entry.timestamp.split()[1] if ' ' in entry.timestamp else entry.timestamp
        ts_lbl = QLabel(ts)
        ts_lbl.setFont(font(11))
        ts_lbl.setStyleSheet(f"color: {COLORS['text_muted']};")
        header.addWidget(ts_lbl)

        toggle = "▾" if is_expanded else "▸"
        preview = entry.preview[:80].replace("\n", " ")
        text_btn = QPushButton(f"{toggle}  {preview}")
        text_btn.setFont(font(13))
        text_btn.setProperty("flat", True)
        text_btn.setStyleSheet(f"text-align: left; color: {COLORS['text']};")
        text_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        text_btn.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        text_btn.clicked.connect(lambda _=False, i=idx: self._toggle_clip(i))
        header.addWidget(text_btn, stretch=1)

        copy_btn = _icon_btn("❐", "Copy")
        copy_btn.clicked.connect(lambda _=False, i=idx: self._paste_clip(i))
        header.addWidget(copy_btn)

        save_btn = _icon_btn("★", "Save as snippet")
        save_btn.clicked.connect(lambda _=False, e=entry: self._save_as_snippet(e))
        header.addWidget(save_btn)

        v.addLayout(header)

        if is_expanded:
            text = QTextEdit()
            text.setFont(font(13, family="Consolas"))
            text.setReadOnly(True)
            text.setPlainText(entry.content)
            text.setMaximumHeight(120)
            text.setStyleSheet(
                f"background: {COLORS['surface']}; border: 1px solid {COLORS['border']}; "
                f"border-radius: {R['md']}px;"
            )
            v.addWidget(text)

        self._clip_layout.addWidget(frame)
        return frame

    def _toggle_clip(self, idx):
        old = self._expanded_clip_idx
        self._expanded_clip_idx = None if old == idx else idx

        for target in (old, self._expanded_clip_idx):
            if target is not None and target in self._clip_frames:
                old_frame, entry = self._clip_frames[target]
                # Find position in layout
                pos = self._clip_layout.indexOf(old_frame)
                old_frame.setParent(None)
                old_frame.deleteLater()
                new_frame = self._build_clip_entry(target, entry, self._expanded_clip_idx == target)
                # Remove from end (build_clip_entry appends) and insert at correct position
                self._clip_layout.removeWidget(new_frame)
                self._clip_layout.insertWidget(pos, new_frame)
                self._clip_frames[target] = (new_frame, entry)

    def _paste_clip(self, idx):
        if self.app.clipboard_mgr.paste(idx):
            self.app.set_status("Copied to clipboard", COLORS["success"])

    def _apply_clip_filter(self):
        q = self._clip_search.text().strip().lower()
        for i, (frame, entry) in self._clip_frames.items():
            if q:
                haystack = f"{entry.content}".lower()
                frame.setVisible(q in haystack)
            else:
                frame.setVisible(True)

    def _clear_clipboard(self):
        reply = QMessageBox.question(
            self, "Clear", "Clear all clipboard history?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.app.clipboard_mgr.clear_history()
            self._clip_fingerprint = None
            self.refresh_history()

    def _save_as_snippet(self, entry):
        dlg = QDialog(self)
        dlg.setWindowTitle("Save Snippet")
        dlg.setFixedSize(400, 200)
        dlg.setStyleSheet(f"QDialog {{ background: {COLORS['bg']}; }}")

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(20, 16, 20, 16)

        title = QLabel("Save as Snippet")
        title.setFont(font(15, "bold"))
        layout.addWidget(title)

        layout.addWidget(QLabel("Name:"))
        name_entry = QLineEdit()
        name_entry.setFocus()
        layout.addWidget(name_entry)

        preview = entry.content[:100] + "..." if len(entry.content) > 100 else entry.content
        prev_lbl = QLabel(f"Content: {preview}")
        prev_lbl.setFont(font(12))
        prev_lbl.setStyleSheet(f"color: {COLORS['text_muted']};")
        prev_lbl.setWordWrap(True)
        layout.addWidget(prev_lbl)

        layout.addStretch()

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel = QPushButton("Cancel")
        cancel.setFixedSize(90, 34)
        cancel.clicked.connect(dlg.reject)
        btn_row.addWidget(cancel)

        save = QPushButton("Save")
        save.setFixedSize(90, 34)
        save.setProperty("accent", True)

        def do_save():
            name = name_entry.text().strip()
            if name:
                self.app.snippets.append({
                    "name": name, "content": entry.content, "preview": entry.preview
                })
                self.app.save_snippets()
                self._snip_fingerprint = None
                self.refresh_snippets()
                self.app.set_status(f"Snippet '{name}' saved", COLORS["success"])
            dlg.accept()

        save.clicked.connect(do_save)
        name_entry.returnPressed.connect(do_save)
        btn_row.addWidget(save)
        layout.addLayout(btn_row)

        dlg.exec()

    # ── Snippets ─────────────────────────────────────────────────────

    def refresh_snippets(self):
        snippets = self.app.snippets
        fingerprint = tuple((s.get('name', ''), s.get('content', '')) for s in snippets)

        if self._snip_fingerprint != fingerprint:
            _clear(self._snip_layout)
            self._snip_frames = {}
            self._snip_fingerprint = fingerprint

            if not snippets:
                lbl = QLabel("No saved snippets. Click ★ on clipboard items to save.")
                lbl.setStyleSheet(f"color: {COLORS['text_dim']};")
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self._snip_layout.addWidget(lbl)
                self._snip_layout.addStretch()
                return

            for i, snip in enumerate(snippets):
                frame = self._build_snip_entry(i, snip, False)
                self._snip_frames[i] = (frame, snip)

            self._snip_layout.addStretch()

        self._apply_snip_filter()

    def _apply_snip_filter(self):
        q = self._snip_search.text().strip().lower()
        for i, (frame, snip) in self._snip_frames.items():
            if q:
                haystack = f"{snip.get('name', '')} {snip.get('content', '')}".lower()
                frame.setVisible(q in haystack)
            else:
                frame.setVisible(True)

    def _build_snip_entry(self, idx, snip, is_expanded):
        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame {{ background: {COLORS['surface_light']}; border-radius: {R['md']}px; }}"
        )
        v = QVBoxLayout(frame)
        v.setContentsMargins(8, 6, 8, 6)

        header = QHBoxLayout()
        toggle = "▾" if is_expanded else "▸"
        preview = snip.get("content", snip.get("preview", ""))[:60].replace("\n", " ")
        if len(snip.get("content", "")) > 60:
            preview += "…"
        label = f"{toggle}  {snip['name']}" if is_expanded else f"{toggle}  {snip['name']}  —  {preview}"

        text_btn = QPushButton(label)
        text_btn.setFont(font(13, "bold"))
        text_btn.setProperty("flat", True)
        text_btn.setStyleSheet(f"text-align: left; color: {COLORS['text']};")
        text_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        text_btn.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        text_btn.clicked.connect(lambda _=False, i=idx: self._toggle_snip(i))
        header.addWidget(text_btn, stretch=1)

        copy_btn = _icon_btn("❐", "Copy")
        copy_btn.clicked.connect(lambda _=False, c=snip["content"]: self.app.clipboard_mgr.paste_content(c))
        header.addWidget(copy_btn)

        edit_btn = _icon_btn("✏", "Edit")
        edit_btn.clicked.connect(lambda _=False, i=idx: self._edit_snippet(i))
        header.addWidget(edit_btn)

        del_btn = _icon_btn("×", "Delete")
        del_btn.clicked.connect(lambda _=False, i=idx: self._delete_snippet(i))
        header.addWidget(del_btn)

        v.addLayout(header)

        if is_expanded:
            text = QTextEdit()
            text.setFont(font(13, family="Consolas"))
            text.setReadOnly(True)
            text.setPlainText(snip.get("content", ""))
            text.setMaximumHeight(120)
            text.setStyleSheet(
                f"background: {COLORS['surface']}; border: 1px solid {COLORS['border']}; "
                f"border-radius: {R['md']}px;"
            )
            v.addWidget(text)

        self._snip_layout.addWidget(frame)
        return frame

    def _toggle_snip(self, idx):
        old = self._expanded_snip_idx
        self._expanded_snip_idx = None if old == idx else idx

        for target in (old, self._expanded_snip_idx):
            if target is not None and target in self._snip_frames:
                old_frame, snip = self._snip_frames[target]
                pos = self._snip_layout.indexOf(old_frame)
                old_frame.setParent(None)
                old_frame.deleteLater()
                new_frame = self._build_snip_entry(target, snip, self._expanded_snip_idx == target)
                self._snip_layout.removeWidget(new_frame)
                self._snip_layout.insertWidget(pos, new_frame)
                self._snip_frames[target] = (new_frame, snip)

    def _edit_snippet(self, index):
        if index >= len(self.app.snippets):
            return
        snip = self.app.snippets[index]

        dlg = QDialog(self)
        dlg.setWindowTitle("Edit Snippet")
        dlg.setFixedSize(500, 350)
        dlg.setStyleSheet(f"QDialog {{ background: {COLORS['bg']}; }}")

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(15, 16, 15, 10)

        title = QLabel("Edit Snippet")
        title.setFont(font(15, "bold"))
        layout.addWidget(title)

        layout.addWidget(QLabel("Name:"))
        name_entry = QLineEdit(snip["name"])
        layout.addWidget(name_entry)

        layout.addWidget(QLabel("Content:"))
        content_text = QTextEdit()
        content_text.setFont(font(13, family="Consolas"))
        content_text.setPlainText(snip.get("content", ""))
        layout.addWidget(content_text, stretch=1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel = QPushButton("Cancel")
        cancel.setFixedSize(90, 34)
        cancel.clicked.connect(dlg.reject)
        btn_row.addWidget(cancel)

        save = QPushButton("Save")
        save.setFixedSize(90, 34)
        save.setProperty("accent", True)

        def do_save():
            new_name = name_entry.text().strip()
            if new_name:
                self.app.snippets[index] = {
                    "name": new_name,
                    "content": content_text.toPlainText(),
                    "preview": content_text.toPlainText()[:50],
                }
                self.app.save_snippets()
                self._snip_fingerprint = None
                self.refresh_snippets()
                self.app.set_status(f"Snippet '{new_name}' updated", COLORS["success"])
            dlg.accept()

        save.clicked.connect(do_save)
        btn_row.addWidget(save)
        layout.addLayout(btn_row)

        dlg.exec()

    def _delete_snippet(self, index):
        if 0 <= index < len(self.app.snippets):
            name = self.app.snippets[index].get('name', 'this snippet')
            reply = QMessageBox.question(
                self, "Delete", f"Delete snippet '{name}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.app.snippets.pop(index)
                self.app.save_snippets()
                self._snip_fingerprint = None
                self.refresh_snippets()

    def _new_snippet(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("New Snippet")
        dlg.setFixedSize(500, 350)
        dlg.setStyleSheet(f"QDialog {{ background: {COLORS['bg']}; }}")

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(15, 16, 15, 10)

        title = QLabel("New Snippet")
        title.setFont(font(15, "bold"))
        layout.addWidget(title)

        layout.addWidget(QLabel("Name:"))
        name_entry = QLineEdit()
        name_entry.setFocus()
        layout.addWidget(name_entry)

        layout.addWidget(QLabel("Content:"))
        content_text = QTextEdit()
        content_text.setFont(font(13, family="Consolas"))
        layout.addWidget(content_text, stretch=1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel = QPushButton("Cancel")
        cancel.setFixedSize(90, 34)
        cancel.clicked.connect(dlg.reject)
        btn_row.addWidget(cancel)

        save = QPushButton("Save")
        save.setFixedSize(90, 34)
        save.setProperty("accent", True)

        def do_save():
            name = name_entry.text().strip()
            content = content_text.toPlainText()
            if name and content:
                self.app.snippets.append({
                    "name": name, "content": content,
                    "preview": content[:50],
                })
                self.app.save_snippets()
                self._snip_fingerprint = None
                self.refresh_snippets()
                self.app.set_status(f"Snippet '{name}' saved", COLORS["success"])
            dlg.accept()

        save.clicked.connect(do_save)
        name_entry.returnPressed.connect(do_save)
        btn_row.addWidget(save)
        layout.addLayout(btn_row)

        dlg.exec()


def _clear(layout):
    while layout.count():
        child = layout.takeAt(0)
        if child.widget():
            child.widget().deleteLater()
        elif child.layout():
            _clear(child.layout())
