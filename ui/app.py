import customtkinter as ctk
from tkinter import messagebox, filedialog, simpledialog
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

from core.config import get_config
from core.hotkeys import HotkeyManager
from modules.voice import VoiceRecognizer, CommandManager, COMMAND_MODULES
from modules.windows import WindowManager, LayoutManager
from modules.launcher import Launcher, LaunchItem
from modules.clipboard import ClipboardManager
from modules.voice.tts import TextToSpeech
import subprocess
import sys

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

COLORS = {
    "bg": "#121212",
    "surface": "#1e1e1e",
    "surface_light": "#2d2d2d",
    "accent": "#ffffff",
    "accent_hover": "#e0e0e0",
    "success": "#4ade80",
    "warning": "#fbbf24",
    "error": "#f87171",
    "text": "#ffffff",
    "text_dim": "#888888",
}


class FloatingWidget(ctk.CTkToplevel):
    """Always-on-top floating widget showing mic status and last command"""

    def __init__(self, parent, voice_toggle_callback, show_main_callback):
        super().__init__(parent)
        self.voice_toggle = voice_toggle_callback
        self.show_main = show_main_callback

        # Window setup
        self.title("vox")
        self.geometry("280x45")
        self.attributes("-topmost", True)
        self.overrideredirect(True)  # No window decorations
        self.configure(fg_color=COLORS["surface"])

        # Position at top-right of screen
        self.update_idletasks()
        screen_w = self.winfo_screenwidth()
        self.geometry(f"280x45+{screen_w - 300}+10")

        # Make draggable
        self._drag_data = {"x": 0, "y": 0}
        self.bind("<Button-1>", self._start_drag)
        self.bind("<B1-Motion>", self._drag)
        self.bind("<Double-Button-1>", lambda e: self.show_main())

        # Layout
        self.grid_columnconfigure(1, weight=1)

        # Mic indicator button
        self.mic_btn = ctk.CTkButton(
            self, text="🎤", width=35, height=35,
            font=ctk.CTkFont(size=16),
            fg_color=COLORS["surface_light"],
            hover_color=COLORS["accent"],
            command=self.voice_toggle
        )
        self.mic_btn.grid(row=0, column=0, padx=5, pady=5)

        # Status text
        self.status_label = ctk.CTkLabel(
            self, text="Ready - F9 to speak",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_dim"],
            anchor="w"
        )
        self.status_label.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        # Close button
        close_btn = ctk.CTkButton(
            self, text="×", width=25, height=25,
            font=ctk.CTkFont(size=14),
            fg_color="transparent",
            hover_color=COLORS["error"],
            command=self.withdraw
        )
        close_btn.grid(row=0, column=2, padx=2, pady=5)

    def _start_drag(self, event):
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y

    def _drag(self, event):
        x = self.winfo_x() + event.x - self._drag_data["x"]
        y = self.winfo_y() + event.y - self._drag_data["y"]
        self.geometry(f"+{x}+{y}")

    def set_recording(self, is_recording: bool):
        if is_recording:
            self.mic_btn.configure(fg_color=COLORS["error"], text="⏺")
        else:
            self.mic_btn.configure(fg_color=COLORS["surface_light"], text="🎤")

    def set_status(self, text: str, color: str = None):
        self.status_label.configure(
            text=text[:40],
            text_color=color or COLORS["text_dim"]
        )


class VoxApp:
    """Main vox application"""

    def __init__(self):
        self.root = ctk.CTk()
        self.root.title("vox")
        self.root.geometry("900x650")
        self.root.minsize(700, 500)
        self.root.configure(fg_color=COLORS["bg"])

        # Set window icon (handle PyInstaller bundled path)
        if getattr(sys, 'frozen', False):
            icon_path = Path(sys._MEIPASS) / "myicon.ico"
        else:
            icon_path = Path(__file__).parent.parent / "myicon.ico"
        if icon_path.exists():
            try:
                self.root.iconbitmap(default=str(icon_path))
                self.root.after(100, lambda: self.root.iconbitmap(str(icon_path)))
            except Exception:
                pass

        # Initialize core
        self.config = get_config()
        self.hotkey_manager = HotkeyManager()

        # Initialize modules
        self.tts = TextToSpeech()
        self.voice = VoiceRecognizer()
        self.commands = CommandManager()
        self.window_manager = WindowManager()
        self.layout_manager = LayoutManager(self.window_manager)
        self.launcher = Launcher()
        self.clipboard = ClipboardManager()

        # Register layout voice commands
        self.commands.register_layout_commands(
            self.layout_manager,
            on_load_callback=self._on_layout_loaded
        )

        # Register launcher voice commands from config
        for item in self.launcher.get_all_items():
            if item.voice_phrase:
                self.commands.register_custom_command(
                    item.voice_phrase,
                    lambda i=item: self.launcher.launch(i)
                )

        # State
        self.windows: List = []
        self.selected_windows: List[int] = []
        self.window_checkboxes: Dict = {}
        self.auto_launch_vars: Dict[int, ctk.BooleanVar] = {}
        self.last_command: str = ""
        self.snippets: List[Dict] = []
        self._load_snippets()

        # Accordion state for clipboard/snippets (only one expanded at a time)
        self._expanded_clipboard_idx: Optional[int] = None
        self._expanded_snippet_idx: Optional[int] = None

        # Setup
        self._setup_callbacks()
        self._create_ui()
        self._setup_hotkeys()

        # Create floating widget
        self.widget = FloatingWidget(
            self.root,
            self.voice.toggle_recording,
            self._show_main_window
        )

        # Start clipboard monitoring
        self.clipboard.start_monitoring()

        # Handle close
        self.root.protocol("WM_DELETE_WINDOW", self._quit_app)

    def _load_snippets(self):
        """Load saved snippets from config"""
        self.snippets = self.config.get('clipboard', 'snippets', default=[])

    def _save_snippets(self):
        """Save snippets to config"""
        self.config.set('clipboard', 'snippets', value=self.snippets)

    def _setup_callbacks(self):
        self.voice.on_result = self._on_voice_result
        self.voice.on_status = self._on_voice_status
        self.voice.on_error = self._on_voice_error
        self.commands.on_command_executed = self._on_command_executed
        self.clipboard.on_new_entry = self._on_clipboard_entry

    def _setup_hotkeys(self):
        voice_key = self.config.get('hotkeys', 'voice_record', default='f9')
        self.hotkey_manager.register(voice_key, self._toggle_voice, "Voice recording")

    def _toggle_voice(self):
        self.root.after(0, self.voice.toggle_recording)

    def _show_main_window(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def _on_close(self):
        self.root.withdraw()  # Hide instead of close
        self.widget.deiconify()  # Show widget

    def _quit_app(self):
        """Actually quit the application"""
        self.root.quit()

    # === UI Creation ===
    def _create_ui(self):
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        # Main container
        main = ctk.CTkFrame(self.root, fg_color=COLORS["bg"])
        main.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        main.grid_rowconfigure(1, weight=1)
        main.grid_columnconfigure(0, weight=1)

        # Header
        self._create_header(main)

        # Tabs
        self.tabs = ctk.CTkTabview(main, fg_color=COLORS["surface"])
        self.tabs.grid(row=1, column=0, sticky="nsew", pady=(8, 0))

        self.home_tab = self.tabs.add("Home")
        self.voice_tab = self.tabs.add("Voice")
        self.windows_tab = self.tabs.add("Windows")
        self.tools_tab = self.tabs.add("Tools")
        self.clipboard_tab = self.tabs.add("Clipboard")
        self.snippets_tab = self.tabs.add("Snippets")
        self.inbox_tab = self.tabs.add("Inbox")

        self._create_home_tab()
        self._create_voice_tab()
        self._create_windows_tab()
        self._create_tools_tab()
        self._create_clipboard_tab()
        self._create_snippets_tab()
        self._create_inbox_tab()

        self.tabs.configure(command=self._on_tab_change)

    def _create_header(self, parent):
        header = ctk.CTkFrame(parent, fg_color=COLORS["surface"], height=50)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(1, weight=1)

        # Title
        ctk.CTkLabel(
            header, text="vox",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=COLORS["accent"]
        ).grid(row=0, column=0, padx=15, pady=10)

        # Status
        self.status_label = ctk.CTkLabel(
            header,
            text=f"Press {self.config.get('hotkeys', 'voice_record', default='F9').upper()} to speak",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text_dim"]
        )
        self.status_label.grid(row=0, column=1, padx=10, pady=10, sticky="w")

        # Record button
        voice_key = self.config.get('hotkeys', 'voice_record', default='F9').upper()
        self.record_btn = ctk.CTkButton(
            header,
            text=f"🎤 Record [{voice_key}]",
            command=self.voice.toggle_recording,
            width=130,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            text_color=COLORS["bg"]
        )
        self.record_btn.grid(row=0, column=2, padx=10, pady=10)

        # Open config button
        ctk.CTkButton(
            header, text="⚙",
            command=self._open_config_folder,
            width=32,
            fg_color=COLORS["surface_light"],
            hover_color=COLORS["accent"]
        ).grid(row=0, column=3, padx=2, pady=10)

        # Open inbox button
        ctk.CTkButton(
            header, text="📥",
            command=self._open_inbox_file,
            width=32,
            fg_color=COLORS["surface_light"],
            hover_color=COLORS["accent"]
        ).grid(row=0, column=4, padx=2, pady=10)

        # Minimize to widget button
        ctk.CTkButton(
            header, text="▼ Widget",
            command=self._on_close,
            width=80,
            fg_color=COLORS["surface_light"],
            hover_color=COLORS["accent"]
        ).grid(row=0, column=5, padx=5, pady=10)

    # === HOME TAB ===
    def _create_home_tab(self):
        self.home_tab.grid_rowconfigure(1, weight=1)
        self.home_tab.grid_columnconfigure(0, weight=1)
        self.home_tab.grid_columnconfigure(1, weight=1)

        # Voice Log (left column)
        log_frame = ctk.CTkFrame(self.home_tab, fg_color=COLORS["surface_light"])
        log_frame.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=5, pady=5)
        log_frame.grid_rowconfigure(1, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            log_frame, text="Voice Log",
            font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=0, column=0, padx=10, pady=8, sticky="w")

        self.voice_log_text = ctk.CTkTextbox(
            log_frame, font=ctk.CTkFont(size=11),
            fg_color=COLORS["surface"]
        )
        self.voice_log_text.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))

        # Right column - Quick Actions
        actions_frame = ctk.CTkFrame(self.home_tab, fg_color=COLORS["surface_light"])
        actions_frame.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=5, pady=5)
        actions_frame.grid_rowconfigure(1, weight=1)
        actions_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            actions_frame, text="Quick Actions",
            font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=0, column=0, padx=10, pady=8, sticky="w")

        self.quick_actions_container = ctk.CTkScrollableFrame(
            actions_frame,
            fg_color=COLORS["surface"]
        )
        self.quick_actions_container.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self._refresh_quick_actions()

    def _refresh_quick_actions(self):
        for w in self.quick_actions_container.winfo_children():
            w.destroy()

        row_frame = None
        count = 0

        # Layouts
        layouts = self.layout_manager.get_layout_names()
        for name in layouts:
            if count % 4 == 0:
                row_frame = ctk.CTkFrame(self.quick_actions_container, fg_color="transparent")
                row_frame.pack(fill="x", pady=2)
            ctk.CTkButton(
                row_frame, text=f"📐 {name}", width=100,
                fg_color=COLORS["surface_light"],
                hover_color=COLORS["accent"],
                command=lambda n=name: self._quick_load_layout(n)
            ).pack(side="left", padx=2)
            count += 1

        # Voice-enabled launchers
        for item in self.launcher.get_all_items():
            if item.voice_phrase:
                if count % 4 == 0:
                    row_frame = ctk.CTkFrame(self.quick_actions_container, fg_color="transparent")
                    row_frame.pack(fill="x", pady=2)
                ctk.CTkButton(
                    row_frame, text=f"🚀 {item.name}", width=100,
                    fg_color=COLORS["surface_light"],
                    hover_color=COLORS["accent"],
                    command=lambda i=item: self.launcher.launch(i)
                ).pack(side="left", padx=2)
                count += 1

        if count == 0:
            ctk.CTkLabel(
                self.quick_actions_container,
                text="No quick actions yet. Add layouts or voice launchers.",
                text_color=COLORS["text_dim"]
            ).pack(pady=10)

    # === VOICE TAB ===
    def _create_voice_tab(self):
        self.voice_tab.grid_rowconfigure(0, weight=1)
        self.voice_tab.grid_columnconfigure(0, weight=1)

        # Scrollable container for all commands
        self.voice_commands_list = ctk.CTkScrollableFrame(
            self.voice_tab, fg_color=COLORS["surface_light"]
        )
        self.voice_commands_list.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.voice_commands_list.grid_columnconfigure(0, weight=1)

        self._refresh_voice_commands()

    def _refresh_voice_commands(self):
        for w in self.voice_commands_list.winfo_children():
            w.destroy()

        # Special commands section
        self._add_voice_section("Special", [
            ("note [text]", "Save quick note to ~/inbox.md")
        ])

        # Layout commands
        layouts = self.layout_manager.get_layout_names()
        if layouts:
            layout_cmds = [(f'"{name}" or "{name} layout"', "Apply window layout") for name in layouts]
            self._add_voice_section("Layouts", layout_cmds)

        # Launcher commands
        launcher_cmds = []
        for item in self.launcher.get_all_items():
            if item.voice_phrase:
                launcher_cmds.append((f'"{item.voice_phrase}"', f"Launch {item.name}"))
        if launcher_cmds:
            self._add_voice_section("Launchers", launcher_cmds)

        # Built-in commands by module
        for module_name, module_info in COMMAND_MODULES.items():
            cmds = []
            for cmd_name, cmd_info in module_info["commands"].items():
                phrases = cmd_info["phrases"][:2]  # Show first 2 phrases
                phrase_str = " / ".join(f'"{p}"' for p in phrases)
                if len(cmd_info["phrases"]) > 2:
                    phrase_str += " ..."
                cmds.append((phrase_str, cmd_info["description"]))
            self._add_voice_section(module_name.title(), cmds)

    def _add_voice_section(self, title: str, commands: list):
        # Section header
        header = ctk.CTkFrame(self.voice_commands_list, fg_color=COLORS["surface"])
        header.pack(fill="x", pady=(10, 5), padx=5)

        ctk.CTkLabel(
            header, text=title,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COLORS["text"]
        ).pack(side="left", padx=10, pady=6)

        # Commands
        for phrase, description in commands:
            row = ctk.CTkFrame(self.voice_commands_list, fg_color="transparent")
            row.pack(fill="x", padx=15, pady=1)

            ctk.CTkLabel(
                row, text=phrase,
                font=ctk.CTkFont(size=11),
                text_color=COLORS["success"],
                anchor="w", width=280
            ).pack(side="left", padx=5)

            ctk.CTkLabel(
                row, text=description,
                font=ctk.CTkFont(size=11),
                text_color=COLORS["text_dim"],
                anchor="w"
            ).pack(side="left", padx=5, fill="x", expand=True)

    # === WINDOWS TAB ===
    def _create_windows_tab(self):
        self.windows_tab.grid_rowconfigure(2, weight=1)  # Window list gets most space
        self.windows_tab.grid_columnconfigure(0, weight=1)

        # Track collapse states
        self._layouts_expanded = True
        self._create_expanded = False

        # === Saved Layouts Section (collapsible, expanded by default) ===
        self.layouts_section = ctk.CTkFrame(self.windows_tab, fg_color=COLORS["surface_light"])
        self.layouts_section.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.layouts_section.grid_columnconfigure(0, weight=1)

        layouts_header = ctk.CTkFrame(self.layouts_section, fg_color="transparent")
        layouts_header.pack(fill="x")

        self.layouts_toggle_btn = ctk.CTkButton(
            layouts_header, text="▼ Saved Layouts",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="transparent", hover_color=COLORS["surface"],
            anchor="w", command=self._toggle_layouts_section
        )
        self.layouts_toggle_btn.pack(side="left", fill="x", expand=True, padx=5, pady=6)

        self.saved_layouts_container = ctk.CTkScrollableFrame(
            self.layouts_section, fg_color=COLORS["surface"], height=140
        )
        self.saved_layouts_container.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.saved_layouts_container.grid_columnconfigure(0, weight=1)
        self._refresh_saved_layouts()

        # === Create Layout Section (collapsible, collapsed by default) ===
        self.create_section = ctk.CTkFrame(self.windows_tab, fg_color=COLORS["surface_light"])
        self.create_section.grid(row=1, column=0, sticky="ew", padx=5, pady=(0, 5))

        create_header = ctk.CTkFrame(self.create_section, fg_color="transparent")
        create_header.pack(fill="x")

        self.create_toggle_btn = ctk.CTkButton(
            create_header, text="▶ Create New Layout",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="transparent", hover_color=COLORS["surface"],
            anchor="w", command=self._toggle_create_section
        )
        self.create_toggle_btn.pack(side="left", fill="x", expand=True, padx=5, pady=6)

        self.create_content = ctk.CTkFrame(self.create_section, fg_color="transparent")
        # Start collapsed - don't pack

        ctk.CTkLabel(self.create_content, text="1. Select windows below", text_color=COLORS["text_dim"]).pack(anchor="w", padx=10, pady=(5, 2))

        form_row = ctk.CTkFrame(self.create_content, fg_color="transparent")
        form_row.pack(fill="x", padx=10, pady=(0, 8))

        ctk.CTkLabel(form_row, text="2. Name:").pack(side="left")
        self.layout_name_entry = ctk.CTkEntry(form_row, placeholder_text="e.g. coding", width=140)
        self.layout_name_entry.pack(side="left", padx=8)

        ctk.CTkButton(
            form_row, text="Save Layout", command=self._save_layout, width=100,
            fg_color=COLORS["accent"], text_color=COLORS["bg"]
        ).pack(side="left", padx=5)

        # === Window List (always visible) ===
        window_frame = ctk.CTkFrame(self.windows_tab, fg_color=COLORS["surface_light"])
        window_frame.grid(row=2, column=0, sticky="nsew", padx=5, pady=(0, 5))
        window_frame.grid_rowconfigure(1, weight=1)
        window_frame.grid_columnconfigure(0, weight=1)

        win_header = ctk.CTkFrame(window_frame, fg_color="transparent")
        win_header.pack(fill="x")

        ctk.CTkLabel(
            win_header, text="Open Windows",
            font=ctk.CTkFont(size=13, weight="bold")
        ).pack(side="left", padx=10, pady=6)

        ctk.CTkButton(
            win_header, text="↻", width=28,
            fg_color=COLORS["surface"], hover_color=COLORS["accent"],
            command=self._refresh_windows
        ).pack(side="right", padx=8)

        self.window_list = ctk.CTkScrollableFrame(window_frame, fg_color=COLORS["surface"])
        self.window_list.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self._refresh_windows()

    def _toggle_layouts_section(self):
        self._layouts_expanded = not self._layouts_expanded
        if self._layouts_expanded:
            self.layouts_toggle_btn.configure(text="▼ Saved Layouts")
            self.saved_layouts_container.pack(fill="both", expand=True, padx=8, pady=(0, 8))
            self.windows_tab.grid_rowconfigure(0, weight=1)
        else:
            self.layouts_toggle_btn.configure(text="▶ Saved Layouts")
            self.saved_layouts_container.pack_forget()
            self.windows_tab.grid_rowconfigure(0, weight=0)

    def _toggle_create_section(self):
        self._create_expanded = not self._create_expanded
        if self._create_expanded:
            self.create_toggle_btn.configure(text="▼ Create New Layout")
            self.create_content.pack(fill="x")
        else:
            self.create_toggle_btn.configure(text="▶ Create New Layout")
            self.create_content.pack_forget()

    def _refresh_saved_layouts(self):
        for w in self.saved_layouts_container.winfo_children():
            w.destroy()

        layouts = self.layout_manager.get_layout_names()
        if not layouts:
            ctk.CTkLabel(
                self.saved_layouts_container,
                text="No saved layouts yet. Select windows below and save.",
                text_color=COLORS["text_dim"]
            ).pack(pady=20)
            return

        for name in layouts:
            info = self.layout_manager.get_layout_info(name)
            self._create_layout_card(name, info)

    def _create_layout_card(self, name: str, info: dict):
        """Create a card for a saved layout"""
        card = ctk.CTkFrame(self.saved_layouts_container, fg_color=COLORS["surface_light"])
        card.pack(fill="x", pady=3, padx=2)
        card.grid_columnconfigure(1, weight=1)

        # Layout name (clickable to load)
        name_btn = ctk.CTkButton(
            card, text=f"📐 {name}",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="transparent",
            hover_color=COLORS["surface"],
            anchor="w",
            command=lambda: self._quick_load_layout(name)
        )
        name_btn.grid(row=0, column=0, padx=8, pady=(8, 2), sticky="w")

        # Preview info (windows in layout)
        layout_data = self.layout_manager.layouts.get(name, {})
        apps = []
        for wd in layout_data.values():
            if 'identifier' in wd:
                app = wd['identifier'].get('app_type', 'unknown')
                apps.append(self.window_manager.get_app_display_name(app))
        preview_text = ", ".join(apps[:4])
        if len(apps) > 4:
            preview_text += f" +{len(apps) - 4} more"

        ctk.CTkLabel(
            card, text=preview_text or "Empty layout",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_dim"],
            anchor="w"
        ).grid(row=1, column=0, columnspan=2, padx=12, pady=(0, 8), sticky="w")

        # Match indicator
        matches = info.get('matches', 0) if info else 0
        total = info.get('window_count', 0) if info else 0
        match_color = COLORS["success"] if matches == total else COLORS["warning"] if matches > 0 else COLORS["text_dim"]
        ctk.CTkLabel(
            card, text=f"{matches}/{total}",
            font=ctk.CTkFont(size=11),
            text_color=match_color
        ).grid(row=0, column=1, padx=5, sticky="e")

        # Action buttons
        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.grid(row=0, column=2, rowspan=2, padx=5, pady=5)

        ctk.CTkButton(
            actions, text="▶", width=28,
            fg_color=COLORS["surface"],
            hover_color=COLORS["success"],
            command=lambda: self._quick_load_layout(name)
        ).pack(side="left", padx=1)

        ctk.CTkButton(
            actions, text="✏", width=28,
            fg_color="transparent",
            hover_color=COLORS["warning"],
            command=lambda: self._edit_layout(name)
        ).pack(side="left", padx=1)

        ctk.CTkButton(
            actions, text="⚙", width=28,
            fg_color="transparent",
            hover_color=COLORS["accent"],
            command=lambda: self._edit_layout_contents(name)
        ).pack(side="left", padx=1)

        ctk.CTkButton(
            actions, text="⧉", width=28,
            fg_color="transparent",
            hover_color=COLORS["accent"],
            command=lambda: self._duplicate_layout(name)
        ).pack(side="left", padx=1)

        ctk.CTkButton(
            actions, text="×", width=28,
            fg_color="transparent",
            hover_color=COLORS["error"],
            command=lambda: self._delete_layout(name)
        ).pack(side="left", padx=1)

    def _quick_load_layout(self, name: str):
        result = self.layout_manager.load_layout(name)
        color = COLORS["success"] if result['applied'] > 0 else COLORS["warning"]
        self._set_status(f"Layout '{name}': {result['applied']}/{result['total']}", color)

    def _edit_layout(self, name: str):
        dialog = ctk.CTkToplevel(self.root)
        dialog.title("Rename Layout")
        dialog.geometry("300x120")
        dialog.attributes("-topmost", True)
        dialog.configure(fg_color=COLORS["surface"])
        dialog.resizable(False, False)

        # Center on parent
        dialog.transient(self.root)
        dialog.grab_set()

        ctk.CTkLabel(
            dialog, text=f"Rename '{name}':",
            font=ctk.CTkFont(size=12)
        ).pack(pady=(15, 5))

        entry = ctk.CTkEntry(dialog, width=200)
        entry.pack(pady=5)
        entry.insert(0, name)
        entry.select_range(0, "end")
        entry.focus()

        def do_rename():
            new_name = entry.get().strip()
            if new_name and new_name != name:
                if self.layout_manager.rename_layout(name, new_name):
                    self.commands._refresh_layout_commands()
                    self._refresh_saved_layouts()
                    self._refresh_quick_actions()
                    self._set_status(f"Renamed '{name}' to '{new_name}'", COLORS["success"])
            dialog.destroy()

        entry.bind("<Return>", lambda e: do_rename())

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=10)

        ctk.CTkButton(
            btn_frame, text="Cancel", width=80,
            fg_color=COLORS["surface_light"],
            command=dialog.destroy
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame, text="Rename", width=80,
            fg_color=COLORS["accent"],
            text_color=COLORS["bg"],
            command=do_rename
        ).pack(side="left", padx=5)

    def _edit_layout_contents(self, name: str):
        """Dialog to edit which windows are in the layout"""
        if name not in self.layout_manager.layouts:
            return

        layout_data = self.layout_manager.layouts[name]

        dialog = ctk.CTkToplevel(self.root)
        dialog.title(f"Edit Layout: {name}")
        dialog.geometry("500x500")
        dialog.attributes("-topmost", True)
        dialog.configure(fg_color=COLORS["surface"])
        dialog.transient(self.root)
        dialog.grab_set()

        dialog.grid_rowconfigure(1, weight=1)
        dialog.grid_rowconfigure(3, weight=1)
        dialog.grid_columnconfigure(0, weight=1)

        # === Current windows in layout ===
        ctk.CTkLabel(
            dialog, text=f"In Layout '{name}'",
            font=ctk.CTkFont(size=13, weight="bold")
        ).grid(row=0, column=0, padx=15, pady=(10, 5), sticky="w")

        existing_list = ctk.CTkScrollableFrame(dialog, fg_color=COLORS["surface_light"], height=150)
        existing_list.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)

        window_vars = {}  # key -> BooleanVar
        auto_launch_edit_vars = {}  # key -> BooleanVar

        for key, wd in layout_data.items():
            if 'identifier' not in wd:
                continue

            app_type = wd['identifier'].get('app_type', 'unknown')
            display_name = self.window_manager.get_app_display_name(app_type)
            pos = wd.get('position', {})
            pos_str = f"{pos.get('width', '?')}x{pos.get('height', '?')}"

            row = ctk.CTkFrame(existing_list, fg_color=COLORS["surface"])
            row.pack(fill="x", pady=2, padx=5)

            var = ctk.BooleanVar(value=True)
            window_vars[key] = var

            ctk.CTkCheckBox(row, text="", variable=var, width=20).pack(side="left", padx=5)
            ctk.CTkLabel(row, text=display_name, font=ctk.CTkFont(weight="bold")).pack(side="left", padx=5)
            ctk.CTkLabel(row, text=pos_str, text_color=COLORS["text_dim"]).pack(side="left", padx=10)

            auto_var = ctk.BooleanVar(value=wd.get('auto_launch', False))
            auto_launch_edit_vars[key] = auto_var
            ctk.CTkCheckBox(row, text="Auto-launch", variable=auto_var, width=90).pack(side="right", padx=5)

        if not layout_data:
            ctk.CTkLabel(existing_list, text="(empty)", text_color=COLORS["text_dim"]).pack(pady=10)

        # === Available windows to add ===
        ctk.CTkLabel(
            dialog, text="Add from Open Windows",
            font=ctk.CTkFont(size=13, weight="bold")
        ).grid(row=2, column=0, padx=15, pady=(10, 5), sticky="w")

        available_list = ctk.CTkScrollableFrame(dialog, fg_color=COLORS["surface_light"], height=150)
        available_list.grid(row=3, column=0, sticky="nsew", padx=10, pady=5)

        current_windows = self.window_manager.get_all_windows()
        add_window_vars = {}  # hwnd -> (BooleanVar, WindowInfo, auto_launch_var)

        if not current_windows:
            ctk.CTkLabel(available_list, text="No windows open", text_color=COLORS["text_dim"]).pack(pady=10)
        else:
            for window in current_windows:
                display_name = self.window_manager.get_app_display_name(self.window_manager.get_app_type(window))
                title = window.title[:35] + "..." if len(window.title) > 35 else window.title

                row = ctk.CTkFrame(available_list, fg_color=COLORS["surface"])
                row.pack(fill="x", pady=2, padx=5)

                var = ctk.BooleanVar(value=False)
                auto_var = ctk.BooleanVar(value=False)
                add_window_vars[window.hwnd] = (var, window, auto_var)

                ctk.CTkCheckBox(row, text="", variable=var, width=20).pack(side="left", padx=5)
                ctk.CTkLabel(row, text=display_name, font=ctk.CTkFont(weight="bold")).pack(side="left", padx=5)
                ctk.CTkLabel(row, text=title, text_color=COLORS["text_dim"], font=ctk.CTkFont(size=10)).pack(side="left", padx=5)
                ctk.CTkCheckBox(row, text="Auto-launch", variable=auto_var, width=90).pack(side="right", padx=5)

        # Buttons
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.grid(row=4, column=0, pady=10)

        def do_save():
            # Keep checked existing windows
            new_layout = {}
            for key, wd in layout_data.items():
                if key in window_vars and window_vars[key].get():
                    new_layout[key] = wd.copy()
                    if key in auto_launch_edit_vars:
                        new_layout[key]['auto_launch'] = auto_launch_edit_vars[key].get()

            # Add newly checked windows
            next_idx = len(new_layout)
            for hwnd, (var, window, auto_var) in add_window_vars.items():
                if var.get():
                    identifier = self.window_manager.create_smart_identifier(window)
                    new_layout[f"window_{next_idx}"] = {
                        "identifier": identifier,
                        "position": {"x": window.x, "y": window.y, "width": window.width, "height": window.height},
                        "exe_path": window.exe_path,
                        "auto_launch": auto_var.get(),
                        "is_borderless": window.is_borderless
                    }
                    next_idx += 1

            self.layout_manager.layouts[name] = new_layout
            self.layout_manager._save_layouts()
            self._refresh_saved_layouts()
            self._set_status(f"Layout '{name}' updated", COLORS["success"])
            dialog.destroy()

        ctk.CTkButton(btn_frame, text="Cancel", width=80, fg_color=COLORS["surface_light"], command=dialog.destroy).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Save", width=80, fg_color=COLORS["accent"], text_color=COLORS["bg"], command=do_save).pack(side="left", padx=5)

    def _duplicate_layout(self, name: str):
        """Duplicate a layout with a new name"""
        if name not in self.layout_manager.layouts:
            return

        dialog = ctk.CTkToplevel(self.root)
        dialog.title("Duplicate Layout")
        dialog.geometry("300x120")
        dialog.attributes("-topmost", True)
        dialog.configure(fg_color=COLORS["surface"])
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        ctk.CTkLabel(
            dialog, text=f"New name for copy of '{name}':",
            font=ctk.CTkFont(size=12)
        ).pack(pady=(15, 5))

        entry = ctk.CTkEntry(dialog, width=200)
        entry.pack(pady=5)
        entry.insert(0, f"{name} copy")
        entry.select_range(0, "end")
        entry.focus()

        def do_duplicate():
            new_name = entry.get().strip()
            if new_name and new_name != name and new_name not in self.layout_manager.layouts:
                import copy
                self.layout_manager.layouts[new_name] = copy.deepcopy(self.layout_manager.layouts[name])
                self.layout_manager._save_layouts()
                self.commands._refresh_layout_commands()
                self._refresh_saved_layouts()
                self._refresh_quick_actions()
                self._set_status(f"Duplicated '{name}' as '{new_name}'", COLORS["success"])
            elif new_name in self.layout_manager.layouts:
                self._set_status(f"Layout '{new_name}' already exists", COLORS["error"])
            dialog.destroy()

        entry.bind("<Return>", lambda e: do_duplicate())

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=10)

        ctk.CTkButton(
            btn_frame, text="Cancel", width=80,
            fg_color=COLORS["surface_light"],
            command=dialog.destroy
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame, text="Duplicate", width=80,
            fg_color=COLORS["accent"],
            text_color=COLORS["bg"],
            command=do_duplicate
        ).pack(side="left", padx=5)

    def _refresh_windows(self):
        for w in self.window_list.winfo_children():
            w.destroy()

        self.windows = self.window_manager.get_all_windows()
        current_hwnds = {w.hwnd for w in self.windows}
        self.selected_windows = [h for h in self.selected_windows if h in current_hwnds]

        self.window_checkboxes = {}
        self.auto_launch_vars = {}
        grouped = self.window_manager.group_by_app(self.windows)

        for app_type, app_windows in sorted(grouped.items()):
            header = ctk.CTkFrame(self.window_list, fg_color="transparent")
            header.pack(fill="x", padx=5, pady=(10, 5))

            display_name = self.window_manager.get_app_display_name(app_type)
            ctk.CTkLabel(
                header, text=f"{display_name} ({len(app_windows)})",
                font=ctk.CTkFont(weight="bold")
            ).pack(side="left", padx=10)

            for window in app_windows:
                self._create_window_entry(window)

    def _create_window_entry(self, window):
        is_selected = window.hwnd in self.selected_windows
        entry = ctk.CTkFrame(
            self.window_list,
            fg_color=COLORS["accent"] if is_selected else COLORS["surface"],
            corner_radius=8
        )
        entry.pack(fill="x", padx=10, pady=3)

        # Make whole row clickable
        entry.bind("<Button-1>", lambda e, h=window.hwnd: self._toggle_window_select(h))

        # Left side: checkbox + info
        left = ctk.CTkFrame(entry, fg_color="transparent")
        left.pack(side="left", fill="both", expand=True, padx=10, pady=8)
        left.bind("<Button-1>", lambda e, h=window.hwnd: self._toggle_window_select(h))

        cb = ctk.CTkCheckBox(entry, text="", width=24, command=lambda h=window.hwnd: self._toggle_window_select(h))
        cb.pack(side="left", padx=(10, 0))
        self.window_checkboxes[window.hwnd] = cb
        if is_selected:
            cb.select()

        # Title
        title = window.title[:45] + "..." if len(window.title) > 45 else window.title
        title_color = COLORS["bg"] if is_selected else COLORS["text"]
        ctk.CTkLabel(
            left, text=title, anchor="w",
            text_color=title_color,
            font=ctk.CTkFont(size=13)
        ).pack(anchor="w")
        left.winfo_children()[-1].bind("<Button-1>", lambda e, h=window.hwnd: self._toggle_window_select(h))

        # Process name + dimensions (subtle)
        dim_color = COLORS["surface"] if is_selected else COLORS["text_dim"]
        ctk.CTkLabel(
            left, text=f"{window.process_name}  •  {window.width}×{window.height}",
            text_color=dim_color,
            font=ctk.CTkFont(size=11)
        ).pack(anchor="w")
        left.winfo_children()[-1].bind("<Button-1>", lambda e, h=window.hwnd: self._toggle_window_select(h))

        # Auto-launch (only visible when selected)
        auto_var = ctk.BooleanVar(value=False)
        self.auto_launch_vars[window.hwnd] = auto_var
        if is_selected:
            ctk.CTkCheckBox(
                entry, text="Auto", variable=auto_var, width=60,
                font=ctk.CTkFont(size=11)
            ).pack(side="right", padx=10)

    def _toggle_window_select(self, hwnd: int):
        if hwnd in self.selected_windows:
            self.selected_windows.remove(hwnd)
        else:
            self.selected_windows.append(hwnd)
        self._refresh_windows()

    def _save_layout(self):
        name = self.layout_name_entry.get().strip()
        if not name:
            messagebox.showwarning("No Name", "Enter a layout name")
            return
        if not self.selected_windows:
            messagebox.showwarning("No Selection", "Select windows to save")
            return

        current_windows = {w.hwnd: w for w in self.window_manager.get_all_windows()}
        windows = [current_windows[hwnd] for hwnd in self.selected_windows if hwnd in current_windows]

        if not windows:
            messagebox.showwarning("Windows Gone", "Selected windows no longer exist")
            return

        auto_launch_config = {hwnd: var.get() for hwnd, var in self.auto_launch_vars.items()}
        if self.layout_manager.save_layout(name, windows, auto_launch_config):
            self.commands._refresh_layout_commands()
            self._refresh_saved_layouts()
            self._refresh_quick_actions()
            self.layout_name_entry.delete(0, "end")
            self._set_status(f"Layout '{name}' saved", COLORS["success"])

    def _delete_layout(self, name: str):
        if messagebox.askyesno("Delete Layout", f"Delete layout '{name}'?"):
            if self.layout_manager.delete_layout(name):
                self.commands._refresh_layout_commands()
                self._refresh_saved_layouts()
                self._refresh_quick_actions()

    # === TOOLS TAB ===
    def _create_tools_tab(self):
        self.tools_tab.grid_rowconfigure(0, weight=1)
        self.tools_tab.grid_columnconfigure(0, weight=1)

        # Launcher (full width now)
        launcher_frame = ctk.CTkFrame(self.tools_tab, fg_color=COLORS["surface_light"])
        launcher_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        launcher_frame.grid_rowconfigure(2, weight=1)
        launcher_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            launcher_frame, text="Launcher",
            font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=0, column=0, padx=10, pady=8, sticky="w")

        # Add form - clean single row
        form = ctk.CTkFrame(launcher_frame, fg_color=COLORS["surface"])
        form.grid(row=1, column=0, sticky="ew", padx=8, pady=4)

        self.launcher_type = ctk.CTkComboBox(
            form, values=["app", "terminal", "url", "folder"], width=85,
            command=self._on_launcher_type_change
        )
        self.launcher_type.pack(side="left", padx=4, pady=6)

        self.launcher_terminal_type = ctk.CTkComboBox(form, values=["powershell", "wsl"], width=85)
        self.launcher_terminal_type.set("powershell")
        # Initially hidden - shown when type=terminal

        self.launcher_name = ctk.CTkEntry(form, width=100, placeholder_text="Name")
        self.launcher_name.pack(side="left", padx=4, pady=6)

        self.launcher_path = ctk.CTkEntry(form, width=160, placeholder_text="Path / Command / URL")
        self.launcher_path.pack(side="left", padx=4, pady=6)

        self.launcher_browse_btn = ctk.CTkButton(form, text="...", width=28, command=self._browse_launcher_path)
        self.launcher_browse_btn.pack(side="left", padx=2, pady=6)

        self.launcher_voice = ctk.CTkEntry(form, width=90, placeholder_text="Voice (opt)")
        self.launcher_voice.pack(side="left", padx=4, pady=6)

        ctk.CTkButton(
            form, text="+", width=32,
            fg_color=COLORS["accent"], text_color=COLORS["bg"],
            command=self._add_launcher_item
        ).pack(side="left", padx=4, pady=6)

        # Items list
        self.launcher_list = ctk.CTkScrollableFrame(launcher_frame, fg_color=COLORS["surface"])
        self.launcher_list.grid(row=2, column=0, sticky="nsew", padx=8, pady=(4, 8))
        self._refresh_launcher()

    # === CLIPBOARD TAB ===
    def _create_clipboard_tab(self):
        self.clipboard_tab.grid_rowconfigure(0, weight=1)
        self.clipboard_tab.grid_columnconfigure(0, weight=1)

        main_frame = ctk.CTkFrame(self.clipboard_tab, fg_color=COLORS["surface_light"])
        main_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        main_frame.grid_rowconfigure(1, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)

        # Header
        clip_header = ctk.CTkFrame(main_frame, fg_color="transparent")
        clip_header.grid(row=0, column=0, sticky="ew", padx=8, pady=8)

        ctk.CTkLabel(
            clip_header, text="Clipboard History",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(side="left")

        ctk.CTkButton(
            clip_header, text="Clear", width=50,
            fg_color=COLORS["surface"],
            hover_color=COLORS["error"],
            command=self._clear_clipboard
        ).pack(side="right", padx=2)

        self.clipboard_list = ctk.CTkScrollableFrame(main_frame, fg_color=COLORS["surface"])
        self.clipboard_list.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self._refresh_clipboard()

    # === SNIPPETS TAB ===
    def _create_snippets_tab(self):
        self.snippets_tab.grid_rowconfigure(0, weight=1)
        self.snippets_tab.grid_columnconfigure(0, weight=1)

        main_frame = ctk.CTkFrame(self.snippets_tab, fg_color=COLORS["surface_light"])
        main_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        main_frame.grid_rowconfigure(1, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)

        # Header
        snip_header = ctk.CTkFrame(main_frame, fg_color="transparent")
        snip_header.grid(row=0, column=0, sticky="ew", padx=8, pady=8)

        ctk.CTkLabel(
            snip_header, text="Saved Snippets",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(side="left")

        self.snippets_list = ctk.CTkScrollableFrame(main_frame, fg_color=COLORS["surface"])
        self.snippets_list.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self._refresh_snippets()

    # === INBOX TAB ===
    def _create_inbox_tab(self):
        self.inbox_tab.grid_rowconfigure(0, weight=1)
        self.inbox_tab.grid_columnconfigure(0, weight=1)

        main_frame = ctk.CTkFrame(self.inbox_tab, fg_color=COLORS["surface_light"])
        main_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        main_frame.grid_rowconfigure(1, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)

        # Header
        inbox_header = ctk.CTkFrame(main_frame, fg_color="transparent")
        inbox_header.grid(row=0, column=0, sticky="ew", padx=8, pady=8)

        ctk.CTkLabel(
            inbox_header, text="~/inbox.md",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(side="left")

        ctk.CTkButton(
            inbox_header, text="↻ Reload", width=70,
            fg_color=COLORS["surface"],
            hover_color=COLORS["accent"],
            command=self._reload_inbox
        ).pack(side="right", padx=2)

        ctk.CTkButton(
            inbox_header, text="💾 Save", width=60,
            fg_color=COLORS["accent"],
            text_color=COLORS["bg"],
            command=self._save_inbox
        ).pack(side="right", padx=2)

        # Editable text area
        self.inbox_text = ctk.CTkTextbox(main_frame, font=ctk.CTkFont(size=12))
        self.inbox_text.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self._reload_inbox()

    def _reload_inbox(self):
        """Load inbox.md content into the text area"""
        inbox_path = Path.home() / "inbox.md"
        self.inbox_text.delete("1.0", "end")
        if inbox_path.exists():
            try:
                content = inbox_path.read_text(encoding="utf-8")
                self.inbox_text.insert("1.0", content)
            except Exception as e:
                self.inbox_text.insert("1.0", f"Error loading inbox.md: {e}")
        else:
            self.inbox_text.insert("1.0", "# Inbox\n\nNo inbox.md found. Start typing to create one.")

    def _save_inbox(self):
        """Save the text area content to inbox.md"""
        inbox_path = Path.home() / "inbox.md"
        try:
            content = self.inbox_text.get("1.0", "end-1c")
            inbox_path.write_text(content, encoding="utf-8")
            self._set_status("Inbox saved", COLORS["success"])
        except Exception as e:
            self._set_status(f"Error saving inbox: {e}", COLORS["error"])

    def _open_config_folder(self):
        """Open the config folder in file explorer"""
        config_dir = self.config.config_dir
        if sys.platform == "win32":
            subprocess.run(["explorer", str(config_dir)])
        else:
            subprocess.run(["xdg-open", str(config_dir)])

    def _open_inbox_file(self):
        """Open inbox.md in default editor"""
        inbox_path = Path.home() / "inbox.md"
        # Create if doesn't exist
        if not inbox_path.exists():
            inbox_path.write_text("# Inbox\n\n", encoding="utf-8")
        if sys.platform == "win32":
            subprocess.run(["notepad", str(inbox_path)])
        else:
            subprocess.run(["xdg-open", str(inbox_path)])

    def _refresh_launcher(self):
        for w in self.launcher_list.winfo_children():
            w.destroy()

        for item in self.launcher.get_all_items():
            entry = ctk.CTkFrame(self.launcher_list, fg_color=COLORS["surface_light"])
            entry.pack(fill="x", pady=2)

            ctk.CTkLabel(
                entry, text=item.name,
                font=ctk.CTkFont(weight="bold")
            ).pack(side="left", padx=8)

            type_text = f"[{item.item_type}]"
            if item.item_type == "terminal" and item.terminal_type:
                type_text = f"[{item.terminal_type}]"
            ctk.CTkLabel(
                entry, text=type_text,
                text_color=COLORS["text_dim"]
            ).pack(side="left", padx=4)

            if item.voice_phrase:
                ctk.CTkLabel(
                    entry, text=f'"{item.voice_phrase}"',
                    text_color=COLORS["success"]
                ).pack(side="left", padx=4)

            ctk.CTkButton(
                entry, text="×", width=25,
                fg_color="transparent",
                hover_color=COLORS["error"],
                command=lambda n=item.name: self._delete_launcher_item(n)
            ).pack(side="right", padx=2)

            ctk.CTkButton(
                entry, text="✏", width=25,
                fg_color="transparent",
                hover_color=COLORS["warning"],
                command=lambda i=item: self._edit_launcher_item(i)
            ).pack(side="right", padx=2)

            ctk.CTkButton(
                entry, text="▶", width=25,
                fg_color="transparent",
                hover_color=COLORS["accent"],
                command=lambda i=item: self.launcher.launch(i)
            ).pack(side="right", padx=2)

    def _on_launcher_type_change(self, value):
        """Show/hide elements based on type selection"""
        # Shell dropdown - only for terminal
        if value == "terminal":
            self.launcher_terminal_type.pack(side="left", padx=4, pady=6, after=self.launcher_type)
        else:
            self.launcher_terminal_type.pack_forget()

        # Browse button - only for app/folder
        if value in ["app", "folder"]:
            self.launcher_browse_btn.pack(side="left", padx=2, pady=6, after=self.launcher_path)
        else:
            self.launcher_browse_btn.pack_forget()

        # Update placeholder text
        if value == "terminal":
            self.launcher_path.configure(placeholder_text="Command")
        elif value == "url":
            self.launcher_path.configure(placeholder_text="URL")
        else:
            self.launcher_path.configure(placeholder_text="Path")

    def _add_launcher_item(self):
        name = self.launcher_name.get().strip()
        path = self.launcher_path.get().strip()
        item_type = self.launcher_type.get()
        voice = self.launcher_voice.get().strip() or None
        terminal_type = self.launcher_terminal_type.get() if item_type == "terminal" else None

        if not name or not path:
            label = "Name and command required" if item_type == "terminal" else "Name and path required"
            messagebox.showwarning("Missing Info", label)
            return

        item = LaunchItem(name=name, path=path, item_type=item_type, voice_phrase=voice, terminal_type=terminal_type)

        if self.launcher.add_item(item):
            if voice:
                self.commands.register_custom_command(voice, lambda i=item: self.launcher.launch(i))
            self._refresh_launcher()
            self._refresh_quick_actions()
            self.launcher_name.delete(0, "end")
            self.launcher_path.delete(0, "end")
            self.launcher_voice.delete(0, "end")
            # Hide terminal type dropdown after adding
            self._on_launcher_type_change(self.launcher_type.get())
        else:
            messagebox.showwarning("Exists", "Item with that name already exists")

    def _edit_launcher_item(self, item: LaunchItem):
        # Simple edit dialog - update voice phrase
        new_voice = simpledialog.askstring(
            "Edit Voice Phrase",
            f"Voice phrase for '{item.name}':",
            initialvalue=item.voice_phrase or ""
        )
        if new_voice is not None:
            item.voice_phrase = new_voice if new_voice else None
            self.launcher._save_items()
            self._refresh_launcher()
            self._refresh_quick_actions()

    def _delete_launcher_item(self, name: str):
        if self.launcher.remove_item(name):
            self._refresh_launcher()
            self._refresh_quick_actions()

    def _browse_launcher_path(self):
        if self.launcher_type.get() == "folder":
            path = filedialog.askdirectory(title="Select folder")
        else:
            path = filedialog.askopenfilename(
                title="Select executable",
                filetypes=[("Executables", "*.exe"), ("All files", "*.*")]
            )
        if path:
            self.launcher_path.delete(0, "end")
            self.launcher_path.insert(0, path)

    def _refresh_clipboard(self):
        for w in self.clipboard_list.winfo_children():
            w.destroy()

        history = self.clipboard.get_history(limit=20)  # 20 entry limit
        if not history:
            ctk.CTkLabel(
                self.clipboard_list,
                text="No clipboard history",
                text_color=COLORS["text_dim"]
            ).pack(pady=10)
            return

        for i, entry in enumerate(history):
            self._create_clipboard_entry(i, entry)

    def _create_clipboard_entry(self, idx: int, entry):
        """Create a clipboard entry with accordion behavior"""
        is_expanded = self._expanded_clipboard_idx == idx

        frame = ctk.CTkFrame(self.clipboard_list, fg_color=COLORS["surface_light"])
        frame.pack(fill="x", pady=2)

        # Header row
        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x")

        # Timestamp
        ctk.CTkLabel(
            header, text=entry.timestamp.split()[1] if ' ' in entry.timestamp else entry.timestamp,
            text_color=COLORS["text_dim"],
            font=ctk.CTkFont(size=10)
        ).pack(side="left", padx=4)

        # Preview (clickable to expand/collapse)
        toggle_text = "▼" if is_expanded else "▶"
        preview_btn = ctk.CTkButton(
            header, text=f"{toggle_text} {entry.preview}",
            font=ctk.CTkFont(size=11),
            fg_color="transparent",
            hover_color=COLORS["surface"],
            anchor="w",
            command=lambda i=idx: self._toggle_clipboard_expand(i)
        )
        preview_btn.pack(side="left", fill="x", expand=True, padx=4)

        # Actions
        ctk.CTkButton(
            header, text="💾", width=25,
            fg_color="transparent",
            hover_color=COLORS["success"],
            command=lambda e=entry: self._save_as_snippet(e)
        ).pack(side="right", padx=1)

        ctk.CTkButton(
            header, text="📋", width=25,
            fg_color="transparent",
            hover_color=COLORS["accent"],
            command=lambda i=idx: self._paste_clipboard(i)
        ).pack(side="right", padx=1)

        # Expanded content
        if is_expanded:
            content_frame = ctk.CTkFrame(frame, fg_color=COLORS["surface"])
            content_frame.pack(fill="x", padx=8, pady=(4, 8))

            text = ctk.CTkTextbox(content_frame, font=ctk.CTkFont(size=11), height=120)
            text.pack(fill="x", padx=5, pady=5)
            text.insert("1.0", entry.content)
            text.configure(state="disabled")

    def _toggle_clipboard_expand(self, idx: int):
        """Toggle clipboard entry expansion (accordion - only one open)"""
        if self._expanded_clipboard_idx == idx:
            self._expanded_clipboard_idx = None
        else:
            self._expanded_clipboard_idx = idx
        self._refresh_clipboard()

    def _show_full_clipboard(self, entry):
        """Show full clipboard content in a dialog"""
        dialog = ctk.CTkToplevel(self.root)
        dialog.title("Clipboard Content")
        dialog.geometry("500x300")
        dialog.attributes("-topmost", True)

        text = ctk.CTkTextbox(dialog, font=ctk.CTkFont(size=12))
        text.pack(fill="both", expand=True, padx=10, pady=10)
        text.insert("1.0", entry.content)
        text.configure(state="disabled")

        ctk.CTkButton(
            dialog, text="Copy",
            command=lambda: [self.clipboard.paste_content(entry.content), dialog.destroy()]
        ).pack(pady=10)

    def _save_as_snippet(self, entry):
        """Save clipboard entry as named snippet"""
        dialog = ctk.CTkToplevel(self.root)
        dialog.title("Save Snippet")
        dialog.geometry("400x200")
        dialog.attributes("-topmost", True)
        dialog.configure(fg_color=COLORS["surface"])
        dialog.transient(self.root)
        dialog.grab_set()

        ctk.CTkLabel(
            dialog, text="Save as Snippet",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=(15, 10))

        ctk.CTkLabel(dialog, text="Name:").pack(anchor="w", padx=20)
        name_entry = ctk.CTkEntry(dialog, width=300)
        name_entry.pack(padx=20, pady=5)
        name_entry.focus()

        # Preview of content
        preview_text = entry.content[:100] + "..." if len(entry.content) > 100 else entry.content
        ctk.CTkLabel(
            dialog, text=f"Content: {preview_text}",
            font=ctk.CTkFont(size=10),
            text_color=COLORS["text_dim"],
            wraplength=360
        ).pack(padx=20, pady=5, anchor="w")

        def do_save():
            name = name_entry.get().strip()
            if name:
                self.snippets.append({
                    "name": name,
                    "content": entry.content,
                    "preview": entry.preview
                })
                self._save_snippets()
                self._refresh_snippets()
                self._set_status(f"Snippet '{name}' saved", COLORS["success"])
            dialog.destroy()

        name_entry.bind("<Return>", lambda e: do_save())

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=15)

        ctk.CTkButton(
            btn_frame, text="Cancel", width=80,
            fg_color=COLORS["surface_light"],
            command=dialog.destroy
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame, text="Save", width=80,
            fg_color=COLORS["accent"],
            text_color=COLORS["bg"],
            command=do_save
        ).pack(side="left", padx=5)

    def _refresh_snippets(self):
        for w in self.snippets_list.winfo_children():
            w.destroy()

        if not self.snippets:
            ctk.CTkLabel(
                self.snippets_list,
                text="No saved snippets. Click 💾 on clipboard items to save.",
                text_color=COLORS["text_dim"]
            ).pack(pady=10)
            return

        for i, snip in enumerate(self.snippets):
            self._create_snippet_entry(i, snip)

    def _create_snippet_entry(self, idx: int, snip: dict):
        """Create a snippet entry with accordion behavior"""
        is_expanded = self._expanded_snippet_idx == idx

        card = ctk.CTkFrame(self.snippets_list, fg_color=COLORS["surface_light"])
        card.pack(fill="x", pady=3, padx=2)

        # Header row: name + actions
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=8, pady=(6, 2))

        # Toggle + name (clickable to expand/collapse)
        toggle_text = "▼" if is_expanded else "▶"
        name_btn = ctk.CTkButton(
            header, text=f"{toggle_text} {snip['name']}",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="transparent",
            hover_color=COLORS["surface"],
            anchor="w",
            command=lambda i=idx: self._toggle_snippet_expand(i)
        )
        name_btn.pack(side="left", fill="x", expand=True)

        # Actions
        ctk.CTkButton(
            header, text="×", width=25,
            fg_color="transparent",
            hover_color=COLORS["error"],
            command=lambda i=idx: self._delete_snippet(i)
        ).pack(side="right", padx=1)

        ctk.CTkButton(
            header, text="✏", width=25,
            fg_color="transparent",
            hover_color=COLORS["warning"],
            command=lambda i=idx: self._edit_snippet(i)
        ).pack(side="right", padx=1)

        ctk.CTkButton(
            header, text="📋", width=25,
            fg_color="transparent",
            hover_color=COLORS["accent"],
            command=lambda s=snip: self.clipboard.paste_content(s["content"])
        ).pack(side="right", padx=1)

        # Content preview (collapsed) or full content (expanded)
        if is_expanded:
            content_frame = ctk.CTkFrame(card, fg_color=COLORS["surface"])
            content_frame.pack(fill="x", padx=8, pady=(4, 8))

            text = ctk.CTkTextbox(content_frame, font=ctk.CTkFont(size=11), height=120)
            text.pack(fill="x", padx=5, pady=5)
            text.insert("1.0", snip.get("content", ""))
            text.configure(state="disabled")
        else:
            # Short preview when collapsed
            preview = snip.get("content", snip.get("preview", ""))[:80]
            if len(snip.get("content", "")) > 80:
                preview += "..."

            ctk.CTkLabel(
                card, text=preview,
                font=ctk.CTkFont(size=11),
                text_color=COLORS["text_dim"],
                anchor="w"
            ).pack(fill="x", padx=12, pady=(0, 6))

    def _toggle_snippet_expand(self, idx: int):
        """Toggle snippet expansion (accordion - only one open)"""
        if self._expanded_snippet_idx == idx:
            self._expanded_snippet_idx = None
        else:
            self._expanded_snippet_idx = idx
        self._refresh_snippets()

    def _show_snippet(self, index: int):
        """Show full snippet content in a dialog"""
        if index >= len(self.snippets):
            return
        snip = self.snippets[index]

        dialog = ctk.CTkToplevel(self.root)
        dialog.title(f"Snippet: {snip['name']}")
        dialog.geometry("500x300")
        dialog.attributes("-topmost", True)
        dialog.configure(fg_color=COLORS["surface"])

        text = ctk.CTkTextbox(dialog, font=ctk.CTkFont(size=12))
        text.pack(fill="both", expand=True, padx=10, pady=10)
        text.insert("1.0", snip.get("content", ""))
        text.configure(state="disabled")

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=10)

        ctk.CTkButton(
            btn_frame, text="Copy",
            fg_color=COLORS["accent"],
            text_color=COLORS["bg"],
            command=lambda: [self.clipboard.paste_content(snip["content"]), dialog.destroy()]
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame, text="Close",
            fg_color=COLORS["surface_light"],
            command=dialog.destroy
        ).pack(side="left", padx=5)

    def _edit_snippet(self, index: int):
        """Edit snippet name and content"""
        if index >= len(self.snippets):
            return
        snip = self.snippets[index]

        dialog = ctk.CTkToplevel(self.root)
        dialog.title(f"Edit Snippet")
        dialog.geometry("500x350")
        dialog.attributes("-topmost", True)
        dialog.configure(fg_color=COLORS["surface"])
        dialog.transient(self.root)
        dialog.grab_set()

        dialog.grid_rowconfigure(2, weight=1)
        dialog.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            dialog, text="Edit Snippet",
            font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=0, column=0, padx=15, pady=(15, 10), sticky="w")

        # Name
        name_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        name_frame.grid(row=1, column=0, sticky="ew", padx=15, pady=5)

        ctk.CTkLabel(name_frame, text="Name:").pack(side="left")
        name_entry = ctk.CTkEntry(name_frame, width=300)
        name_entry.pack(side="left", padx=10)
        name_entry.insert(0, snip["name"])

        # Content
        ctk.CTkLabel(dialog, text="Content:").grid(row=2, column=0, sticky="nw", padx=15, pady=(10, 0))
        content_text = ctk.CTkTextbox(dialog, font=ctk.CTkFont(size=11))
        content_text.grid(row=2, column=0, sticky="nsew", padx=15, pady=(25, 10))
        content_text.insert("1.0", snip.get("content", ""))

        # Buttons
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.grid(row=3, column=0, pady=10)

        def do_save():
            new_name = name_entry.get().strip()
            new_content = content_text.get("1.0", "end-1c")
            if new_name:
                self.snippets[index] = {
                    "name": new_name,
                    "content": new_content,
                    "preview": new_content[:50]
                }
                self._save_snippets()
                self._refresh_snippets()
                self._set_status(f"Snippet '{new_name}' updated", COLORS["success"])
            dialog.destroy()

        ctk.CTkButton(
            btn_frame, text="Cancel", width=80,
            fg_color=COLORS["surface_light"],
            command=dialog.destroy
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame, text="Save", width=80,
            fg_color=COLORS["accent"],
            text_color=COLORS["bg"],
            command=do_save
        ).pack(side="left", padx=5)

    def _delete_snippet(self, index: int):
        if 0 <= index < len(self.snippets):
            self.snippets.pop(index)
            self._save_snippets()
            self._refresh_snippets()

    def _paste_clipboard(self, index: int):
        if self.clipboard.paste(index):
            self._set_status("Copied to clipboard", COLORS["success"])

    def _clear_clipboard(self):
        if messagebox.askyesno("Clear", "Clear all clipboard history?"):
            self.clipboard.clear_history()
            self._refresh_clipboard()

    # === Tab Change ===
    def _on_tab_change(self):
        current = self.tabs.get()
        if current == "Windows":
            self._refresh_windows()
        elif current == "Home":
            self._refresh_quick_actions()
        elif current == "Voice":
            self._refresh_voice_commands()
        elif current == "Clipboard":
            self._refresh_clipboard()
        elif current == "Snippets":
            self._refresh_snippets()
        elif current == "Inbox":
            self._reload_inbox()

    # === Callbacks ===
    def _set_status(self, text: str, color: str = None):
        self.status_label.configure(text=text, text_color=color or COLORS["text"])
        self.widget.set_status(text, color)

    def _on_voice_result(self, text: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.last_command = text
        response_to_speak = None

        # Try commands
        result = self.commands.execute(text)
        if result["executed"]:
            response_to_speak = result.get("response")

        # Try launcher
        if not result["executed"]:
            item = self.launcher.get_by_voice_phrase(text)
            if item:
                self.launcher.launch(item)
                result = {"executed": True, "success": True, "type": "launcher"}
                response_to_speak = f"Launching {item.name}"

        # Check for quick note command
        if not result["executed"] and text.lower().startswith("note "):
            note_text = text[5:].strip()
            if note_text:
                self._save_quick_note(note_text, speak=False)
                result = {"executed": True, "success": True, "type": "note"}
                response_to_speak = "Note saved"

        # If nothing matched, say so
        if not result["executed"]:
            response_to_speak = "Didn't catch that"

        # Speak response
        self.tts.speak(response_to_speak)

        # Log
        status = "✓" if result["executed"] else "?"
        log_entry = f"[{timestamp}] {status} {text}\n"

        self.root.after(0, lambda: self._update_voice_log(log_entry))

        if result["executed"]:
            self.root.after(0, lambda: self._set_status(f"✓ {text}", COLORS["success"]))
        else:
            self.root.after(0, lambda: self._set_status(f"? {text}", COLORS["warning"]))

    def _save_quick_note(self, text: str, speak: bool = True):
        """Save quick note to ~/inbox.md"""
        inbox_path = Path.home() / "inbox.md"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = f"\n- [{timestamp}] {text}"

        with open(inbox_path, "a", encoding="utf-8") as f:
            f.write(entry)

        if speak:
            self.tts.speak("Note saved")
        self._set_status(f"Note saved: {text[:30]}...", COLORS["success"])

    def _update_voice_log(self, entry: str):
        self.voice_log_text.insert("end", entry)
        self.voice_log_text.see("end")

    def _on_voice_status(self, status: str):
        self.root.after(0, lambda: self._set_status(status, COLORS["text_dim"]))

        voice_key = self.config.get('hotkeys', 'voice_record', default='F9').upper()
        is_recording = "Listening" in status

        self.root.after(0, lambda: self.widget.set_recording(is_recording))

        if is_recording:
            self.root.after(0, lambda: self.record_btn.configure(
                text="⏺ Recording...",
                fg_color=COLORS["error"],
                hover_color=COLORS["error"]
            ))
        else:
            self.root.after(0, lambda: self.record_btn.configure(
                text=f"🎤 Record [{voice_key}]",
                fg_color=COLORS["accent"],
                hover_color=COLORS["accent_hover"]
            ))

    def _on_voice_error(self, error: str):
        self.root.after(0, lambda: self._set_status(error, COLORS["error"]))

    def _on_command_executed(self, command: str, success: bool):
        pass

    def _on_layout_loaded(self, name: str, result: dict):
        msg = f"Layout '{name}': {result['applied']}/{result['total']}"
        color = COLORS["success"] if result['applied'] > 0 else COLORS["warning"]
        self.root.after(0, lambda: self._set_status(msg, color))
        # TTS handled in _on_voice_result

    def _on_clipboard_entry(self, entry):
        self.root.after(0, self._refresh_clipboard)

    def run(self):
        try:
            self.root.mainloop()
        finally:
            self.hotkey_manager.cleanup()
            self.clipboard.stop_monitoring()
            self.widget.destroy()
