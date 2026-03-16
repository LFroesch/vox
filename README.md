# Vox

A voice-powered Windows productivity hub built with Python and PyQt6. Control your desktop hands-free — manage window layouts, launch apps, run workflows, set reminders, and track clipboard history, all from a single dark-themed interface with an always-on-top floating widget.

![Python](https://img.shields.io/badge/Python-3.10+-3776ab?logo=python&logoColor=white)
![PyQt6](https://img.shields.io/badge/PyQt6-dark%20theme-41cd52)
![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-0078d4?logo=windows)

## Features

- **Voice Commands** — Google Speech Recognition with multi-candidate transcription and a fuzzy matching pipeline (search intent → exact phrase → token overlap → phonetic similarity → launcher fallback)
- **Window Layouts** — Save and restore multi-monitor window arrangements. Smart matching handles multiple instances of the same app (e.g. 5 VS Code windows). QPainter-based visual preview
- **Workflows** — Batch-launch apps, terminals, URLs, and commands in sequence with optional auto-layout after a configurable delay. Import steps from existing launchers
- **App Launcher** — Launch apps, terminals, URLs, folders, and scripts with per-item voice phrases and args support. Collapsible sections by type
- **Reminders** — Timers, alarms, and reminders with calendar/time picker. Recurring schedules (daily/weekdays/weekly/interval). NLP voice input: "remind me to X at 3pm", "every weekday at 9am check email"
- **Clipboard History** — Persistent tracking with one-click copy and saved snippets
- **Floating Widget** — Compact always-on-top overlay showing voice status, pending reminders with countdown, and favorited quick actions
- **System Tray** — Minimize to tray with restore on double-click

## Tech Stack

| Layer | Tech |
|-------|------|
| UI | PyQt6, QSS dark theme, sidebar nav + stacked pages |
| Voice | SpeechRecognition (Google STT), pyttsx3 (TTS) |
| Windows | pywin32 (enumerate, move, resize, borderless toggle) |
| Hotkeys | keyboard (global F9 toggle) |
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
| Spotify | "play/pause", "next song", "volume up" |
| Layouts | "coding layout", "gaming layout" |
| Workflows | "run dev setup", "start X workflow" |
| Launchers | any assigned voice phrase |
| Search | "search for X", "what is X", "how to X" |
| Notes | "note [text]", "take a note [text]" |
| Timers | "set timer 5 minutes", "remind me to X at 3pm" |
| Recurring | "every day at 9am check email", "every 30 minutes stretch" |

### Workflows

Workflows batch-launch multiple apps/commands in sequence — e.g. open 5 editor windows, 3 terminals, and a browser, then auto-apply a window layout.

1. Create launchers for each app (Launchers page)
2. Create a workflow (Windows → Workflows → + New), import steps with "From Launcher"
3. Optionally link a saved layout to auto-position windows after launch

### Layouts

Save current window positions and restore them by name or voice. Layouts are pure positioning — use workflows for launching apps.

## Architecture

```
main.py                 # Entry point
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
ui/
  app.py                # Main window (sidebar nav, signals, tray)
  widget.py             # Floating always-on-top widget
  styles.py             # Dark theme colors, QSS, font helper
  pages/                # Home, Windows, Launchers, Clipboard, Reminders, Voice, Settings
```

## Requirements

- Windows 10/11
- Python 3.10+
- Microphone (for voice commands)
