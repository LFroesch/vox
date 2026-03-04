# Vox

A voice-powered productivity hub for Windows. Control your desktop with voice commands — manage window layouts, launch apps, and access clipboard history.

## Features

- **Voice Commands** - Hands-free control with Google Speech Recognition + Vosk offline fallback
- **Window Layouts** - Save and restore window arrangements by name. Voice-activated: say "coding layout" to rearrange your desktop
- **App Launcher** - Launch apps, folders, terminals, and scripts. Voice phrase support for each item
- **Clipboard History** - Persistent clipboard tracking with one-click copy
- **Snippets** - Save and reuse text snippets
- **Floating Widget** - Compact always-on-top widget showing status, TTS response, and last action
- **TTS Feedback** - Spoken confirmation for all commands

## Tech Stack

- Python 3 + PyQt6 (sidebar nav, QSS dark theme)
- SpeechRecognition (Google API)
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

### Vosk Offline Model (Optional)

Download [vosk-model-small-en-us-0.15](https://alphacephei.com/vosk/models) and extract to `~/.vox/models/vosk-model-small-en-us-0.15/`.

## Build

```bash
python -m PyInstaller vox.spec --clean
# Output: dist/vox.exe
```

## Requirements

- Windows 10/11
- Python 3.10+
- Microphone (for voice commands)
