"""Floating widget — always-on-top, frameless, draggable, collapsible sections."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QApplication,
)
from PyQt6.QtCore import Qt, QPoint

from ui.styles import COLORS, font, R, WIDGET_WIDTHS


class FloatingWidget(QWidget):
    MAX_H = 500

    def __init__(self, voice_toggle_cb, show_main_cb, get_actions_cb=None,
                 widget_size="Medium"):
        super().__init__()
        self.voice_toggle = voice_toggle_cb
        self.show_main = show_main_cb
        self.get_actions = get_actions_cb
        self._width = WIDGET_WIDTHS.get(widget_size, 320)

        self._status_expanded = False
        self._layouts_expanded = False
        self._launchers_expanded = False
        self._drag_pos = None

        # Window flags
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(self._width)
        self.setMinimumHeight(300)

        # Position top-right
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            self.move(geo.right() - self._width - 20, geo.top() + 10)

        self._build_ui()
        self._update_size()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)

        # Container with rounded border
        self.container = QFrame()
        self.container.setStyleSheet(
            f"QFrame#widget_container {{ background: {COLORS['surface']}; "
            f"border: 1px solid {COLORS['border']}; border-radius: 14px; }}"
        )
        self.container.setObjectName("widget_container")
        c_layout = QVBoxLayout(self.container)
        c_layout.setContentsMargins(6, 6, 6, 10)
        c_layout.setSpacing(2)
        outer.addWidget(self.container)

        # Top bar
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)

        self.mic_btn = QPushButton("MIC")
        self.mic_btn.setFixedSize(42, 26)
        self.mic_btn.setFont(font(11, "bold"))
        self.mic_btn.setStyleSheet(
            f"background: {COLORS['surface_light']}; color: {COLORS['text']}; "
            f"border-radius: {R['md']}px; border: none;"
        )
        self.mic_btn.clicked.connect(self.voice_toggle)
        top_bar.addWidget(self.mic_btn)

        title = QLabel("vox")
        title.setFont(font(12, "bold"))
        title.setStyleSheet(f"color: {COLORS['text_dim']};")
        top_bar.addWidget(title)

        top_bar.addStretch()

        show_btn = QPushButton("⊞")
        show_btn.setFixedSize(24, 24)
        show_btn.setFont(font(12))
        show_btn.setStyleSheet(
            f"background: transparent; border: none; color: {COLORS['text_dim']};"
        )
        show_btn.clicked.connect(self.show_main)
        top_bar.addWidget(show_btn)

        close_btn = QPushButton("×")
        close_btn.setFixedSize(24, 24)
        close_btn.setFont(font(12))
        close_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none; color: {COLORS['text_dim']}; border-radius: 4px; }}"
            f"QPushButton:hover {{ background: {COLORS['error']}; color: {COLORS['text']}; }}"
        )
        close_btn.clicked.connect(self.hide)
        top_bar.addWidget(close_btn)

        c_layout.addLayout(top_bar)

        # Separator
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {COLORS['border']};")
        c_layout.addWidget(sep)

        # Scrollable body
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._body = QWidget()
        self._body_layout = QVBoxLayout(self._body)
        self._body_layout.setContentsMargins(2, 0, 2, 0)
        self._body_layout.setSpacing(0)
        scroll.setWidget(self._body)
        c_layout.addWidget(scroll, stretch=1)

        # -- Status section --
        self._status_header = self._section_header("Status", "status")
        self._body_layout.addWidget(self._status_header)
        self._status_content = QWidget()
        sc_layout = QVBoxLayout(self._status_content)
        sc_layout.setContentsMargins(4, 0, 4, 2)
        sc_layout.setSpacing(0)
        self.status_label = QLabel("Ready")
        self.status_label.setFont(font(12))
        self.status_label.setStyleSheet(f"color: {COLORS['text_dim']};")
        sc_layout.addWidget(self.status_label)
        self.tts_label = QLabel("")
        self.tts_label.setFont(font(11))
        self.tts_label.setStyleSheet(f"color: {COLORS['success']};")
        self.tts_label.hide()
        sc_layout.addWidget(self.tts_label)
        self.action_label = QLabel("")
        self.action_label.setFont(font(11))
        self.action_label.setStyleSheet(f"color: {COLORS['text_muted']};")
        self.action_label.hide()
        sc_layout.addWidget(self.action_label)
        self._status_content.hide()
        self._body_layout.addWidget(self._status_content)

        # -- Layouts section --
        self._layouts_header = self._section_header("Layouts", "layouts")
        self._body_layout.addWidget(self._layouts_header)
        self._layouts_content = QWidget()
        self._layouts_content_layout = QGridLayout(self._layouts_content)
        self._layouts_content_layout.setContentsMargins(2, 0, 2, 4)
        self._layouts_content_layout.setSpacing(2)
        self._layouts_content_layout.setColumnStretch(0, 1)
        self._layouts_content_layout.setColumnStretch(1, 1)
        self._layouts_content.hide()
        self._body_layout.addWidget(self._layouts_content)

        # -- Launchers section --
        self._launchers_header = self._section_header("Launchers", "launchers")
        self._body_layout.addWidget(self._launchers_header)
        self._launchers_content = QWidget()
        self._launchers_content_layout = QGridLayout(self._launchers_content)
        self._launchers_content_layout.setContentsMargins(2, 0, 2, 4)
        self._launchers_content_layout.setSpacing(2)
        self._launchers_content_layout.setColumnStretch(0, 1)
        self._launchers_content_layout.setColumnStretch(1, 1)
        self._launchers_content.hide()
        self._body_layout.addWidget(self._launchers_content)

        self._body_layout.addStretch()

    def _section_header(self, label, section):
        btn = QPushButton(f"▸  {label}")
        btn.setFont(font(12))
        btn.setStyleSheet(
            f"text-align: left; background: transparent; border: none; "
            f"color: {COLORS['text_dim']}; padding: 4px 4px;"
        )
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedHeight(28)
        btn.clicked.connect(lambda: self._toggle_section(section))
        return btn

    # ── Sections ──

    def _toggle_section(self, section):
        attr = f"_{section}_expanded"
        header = getattr(self, f"_{section}_header")
        content = getattr(self, f"_{section}_content")
        label = {"status": "Status", "layouts": "Layouts", "launchers": "Launchers"}[section]

        expanded = not getattr(self, attr)
        setattr(self, attr, expanded)
        header.setText(f"{'▾' if expanded else '▸'}  {label}")
        content.setVisible(expanded)

        if expanded:
            if section == "layouts":
                self._refresh_layouts()
            elif section == "launchers":
                self._refresh_launchers()

        self._update_size()

    def _update_size(self):
        self.setMaximumHeight(self.MAX_H)
        self.adjustSize()

    # ── Action lists ──

    def _build_action_list(self, parent_layout, items, empty_msg):
        _clear(parent_layout)
        if not items:
            lbl = QLabel(empty_msg)
            lbl.setFont(font(11))
            lbl.setStyleSheet(f"color: {COLORS['text_muted']};")
            parent_layout.addWidget(lbl, 0, 0, 1, 2)
        else:
            for i, (name, callback) in enumerate(items):
                btn = QPushButton(name)
                btn.setFixedHeight(28)
                btn.setFont(font(11))
                btn.setStyleSheet(
                    f"text-align: left; background: {COLORS['surface_light']}; "
                    f"color: {COLORS['text']}; border-radius: {R['md']}px; "
                    f"padding: 2px 8px; border: none;"
                )
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.clicked.connect(lambda _, cb=callback: cb())
                parent_layout.addWidget(btn, i // 2, i % 2)
        self._update_size()

    def _refresh_layouts(self):
        if not self.get_actions:
            return
        actions = self.get_actions()
        self._build_action_list(
            self._layouts_content_layout,
            actions.get("layouts", []),
            "No favorited layouts"
        )

    def _refresh_launchers(self):
        if not self.get_actions:
            return
        actions = self.get_actions()
        self._build_action_list(
            self._launchers_content_layout,
            actions.get("launchers", []),
            "No favorited launchers"
        )

    def refresh_actions(self):
        if self._layouts_expanded:
            self._refresh_layouts()
        if self._launchers_expanded:
            self._refresh_launchers()

    # ── Status updates ──

    def set_recording(self, is_recording: bool):
        if is_recording:
            self.mic_btn.setStyleSheet(
                f"background: {COLORS['error']}; color: {COLORS['text']}; "
                f"border-radius: {R['md']}px; border: none;"
            )
            self.mic_btn.setText("REC")
        else:
            self.mic_btn.setStyleSheet(
                f"background: {COLORS['surface_light']}; color: {COLORS['text']}; "
                f"border-radius: {R['md']}px; border: none;"
            )
            self.mic_btn.setText("MIC")

    def set_status(self, text: str, color: str = None):
        self.status_label.setText(text[:40])
        self.status_label.setStyleSheet(f"color: {color or COLORS['text_dim']};")

    def set_tts_response(self, text: str):
        if text:
            self.tts_label.setText(text[:40])
            self.tts_label.show()
        else:
            self.tts_label.hide()

    def set_action(self, text: str):
        if text:
            self.action_label.setText(text[:40])
            self.action_label.show()
        else:
            self.action_label.hide()

    # ── Drag ──

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def mouseDoubleClickEvent(self, event):
        self.show_main()


def _clear(layout):
    while layout.count():
        child = layout.takeAt(0)
        if child.widget():
            child.widget().deleteLater()
        elif child.layout():
            _clear(child.layout())
