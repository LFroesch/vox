# Vox

A voice-powered productivity hub for Windows. Control your desktop with voice commands — manage window layouts, launch apps, set reminders, and access clipboard history.

## Features

- **Voice Commands** — Hands-free control with Google Speech Recognition. Multi-candidate transcription (tries alternative STT results). Matching pipeline: search intent → exact phrase → fuzzy token overlap → phonetic similarity (SequenceMatcher ≥0.8) → launcher phrase. Graceful degradation when mic/internet unavailable
- **Window Layouts** — Save and restore window arrangements by name, with auto-launch and QPainter preview
- **App Launcher** — Launch apps, folders, terminals, URLs, and scripts. Per-item voice phrase support
- **Reminders** — Timers, alarms, and reminders with full date/time picker UI. Recurring reminders (daily/weekdays/weekends/weekly/interval). Fired reminders persist with snooze (+5m/+15m), edit (📝), and dismiss (🗑️). Quick-add timer row (+5m/+15m/+30m/+1h). Timer urgency coloring
- **Clipboard History** — Persistent clipboard tracking with one-click copy
- **Snippets** — Save and reuse text snippets
- **Floating Widget** — Compact always-on-top widget showing status, TTS response, and last action. Favorited layouts/launchers as quick actions
- **TTS Feedback** — Spoken confirmation for all commands

## Tech Stack

- Python 3 + PyQt6 (sidebar nav, QSS dark theme)
- SpeechRecognition (Google STT)
- pyttsx3 (text-to-speech)
- pywin32 (window management)
- keyboard (global hotkeys)
- QSystemTrayIcon (system tray)

## Setup

```bash
git clone https://github.com/LFroesch/vox.git
cd vox
pip install -r requirements.txt
python main.py
```

## Build

```bash
python -m PyInstaller vox.spec --clean
# Output: dist/vox.exe
```

## Requirements

- Windows 10/11
- Python 3.10+
- Microphone (for voice commands)
