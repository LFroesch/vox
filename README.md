# Vox

A voice-powered Windows productivity hub built with Python and PyQt6. Control your desktop hands-free — manage window layouts, launch apps, run workflows, set reminders, and track clipboard history, all from a single dark-themed interface with an always-on-top floating widget.

![Python](https://img.shields.io/badge/Python-3.10+-3776ab?logo=python&logoColor=white)
![PyQt6](https://img.shields.io/badge/PyQt6-dark%20theme-41cd52)
![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-0078d4?logo=windows)

<!-- TODO: replace with actual screenshot -->
![Vox main window](assets/main-window.png)

## Features

- **Voice Commands** — Google Speech Recognition with multi-candidate transcription and a 5-step matching pipeline (NLP intents → search → exact phrase → fuzzy token overlap → launcher fallback)
- **Window Layouts** — Save and restore multi-monitor window arrangements. Smart matching handles multiple instances of the same app (e.g. 5 VS Code windows). QPainter-based visual preview
- **Workflows** — Batch-launch apps, terminals, URLs, and commands in sequence with optional auto-layout after a configurable delay. Import steps from existing launchers
- **App Launcher** — Launch apps, terminals, URLs, folders, and scripts with per-item voice phrases and args support. Collapsible sections by type
- **Reminders** — Timers, alarms, and reminders with calendar/time picker. Recurring schedules (daily/weekdays/weekly/interval). NLP voice input: "remind me to X at 3pm", "every weekday at 9am check email"
- **Clipboard History** — Persistent tracking with one-click copy and saved snippets
- **Notes** — Voice-powered note-taking ("note [text]") that appends to a notes pad on the Home page
- **Floating Widget** — Compact always-on-top overlay showing voice status, pending reminders with countdown, and favorited quick actions
- **System Tray** — Minimize to tray with restore on double-click
- **Single Instance** — Only one copy runs at a time; re-launching brings the existing window forward

## Screenshots

<details>
<summary>Voice Commands</summary>

<!-- TODO: screenshot or GIF of F9 hold → transcription → command match -->
![Voice command flow](assets/voice-commands.png)

</details>

<details>
<summary>Window Layouts</summary>

<!-- TODO: screenshot of layout preview canvas + saved layouts list -->
![Layout preview](assets/layouts.png)

</details>

<details>
<summary>Workflows</summary>

<!-- TODO: screenshot of workflow editor with steps + linked layout -->
![Workflow editor](assets/workflows.png)

</details>

<details>
<summary>Reminders</summary>

<!-- TODO: screenshot of reminders page — pending, fired, recurring sections -->
![Reminders page](assets/reminders.png)

</details>

<details>
<summary>Floating Widget</summary>

<!-- TODO: screenshot of widget on desktop showing reminders + quick actions -->
![Floating widget](assets/widget.png)

</details>

## Tech Stack

| Layer | Tech |
|-------|------|
| UI | PyQt6, QSS dark theme, sidebar nav + stacked pages |
| Voice | SpeechRecognition (Google STT), pyttsx3 (TTS) |
| Windows | pywin32 (enumerate, move, resize, borderless toggle) |
| Hotkeys | keyboard (global F9 hold-to-record, configurable) |
| Tray | QSystemTrayIcon |
| Build | PyInstaller → single `vox.exe` |

## Setup

```bash
git clone https://github.com/LFroesch/vox.git
cd vox
pip install -r requirements.txt
python main.py
```

### Build standalone exe

```bash
python -m PyInstaller vox.spec --clean
# Output: dist/vox.exe
```

## Usage

### Voice Commands (F9 to record)

| Category | Examples |
|----------|----------|
| Notes | "note [text]", "take a note [text]" |
| Reminders | "remind me to X at 3pm", "remind me to X" (no time = tomorrow 9am) |
| Timers | "set timer 5 minutes", "timer for half an hour", "a couple minutes" |
| Recurring | "every day at 9am check email", "every 30 minutes stretch" |
| Search | "search for X", "what is X", "how to X" |
| Spotify | "play/pause", "next song", "volume up" |
| System | "mute", "screenshot", "volume down" |
| Layouts | "coding layout", "gaming layout" |
| Workflows | "run dev setup", "start X workflow" |
| Launchers | any assigned voice phrase |

Commands are matched in priority order: NLP intents (notes, reminders, timers) are parsed first, then search, exact phrases, fuzzy token matching, and finally launcher phrases.

### Workflows

Workflows batch-launch multiple apps/commands in sequence — e.g. open 5 editor windows, 3 terminals, and a browser, then auto-apply a window layout.

1. Create launchers for each app (Launchers page)
2. Create a workflow (Windows → Workflows → + New), import steps with "From Launcher"
3. Optionally link a saved layout to auto-position windows after launch

### Layouts

Save current window positions and restore them by name or voice. Layouts are pure positioning — use workflows for launching apps.

### WSL Distro Setting

If you use WSL and have launcher items that open terminals or run commands in WSL, Vox needs to know which distro to target. The **WSL Distro** dropdown in Settings auto-detects installed distros. Leave it blank to use your default WSL distro, or pick a specific one (e.g. `Ubuntu`) if you have multiple installed. This controls which distro is used when launching WSL terminal items and building UNC paths (`\\wsl$\<Distro>\...`) for project folders.

## Architecture

```
main.py                 # Entry point (single-instance guard)
core/
  config.py             # ~/.vox/ config singleton (JSON)
  hotkeys.py            # Global hotkey registration
modules/
  voice/                # Google STT, command matching, TTS
  windows/              # Window enumeration, layouts, positioning
  launcher/             # App/terminal/URL/folder launching
  clipboard/            # Clipboard monitoring + history
  reminders/            # Timers, alarms, recurring reminders
  workflows/            # Batch launch + layout linking
sounds/                 # Alert sounds (reminder notifications)
ui/
  app.py                # Main window (sidebar nav, signals, tray)
  widget.py             # Floating always-on-top widget
  styles.py             # Dark theme colors, QSS, font helper
  pages/                # Home, Windows, Launchers, Clipboard, Reminders, Help, Settings
```

## Requirements

- Windows 10/11
- Python 3.10+
- Microphone (for voice commands)

## License

[AGPL-3.0](LICENSE) — Copyright 2026 Lucas Froeschner
