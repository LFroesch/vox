# Vox

Voice-powered Windows productivity hub built with Python and PyQt6.

Vox combines voice commands, launchers, workflows, reminders, clipboard history, and window layout management in a single desktop app. It is designed for Windows use, but the repo is structured so development can happen from WSL while the app runs on the Windows host.

## Highlights

- Voice-triggered notes, reminders, timers, search, media controls, and app actions
- Saved window layouts with multi-window matching
- Workflows that batch-launch apps, terminals, URLs, or commands
- Floating always-on-top widget for status and quick actions
- Persistent clipboard history and snippets
- System tray support and single-instance behavior
- Optional wake word support with Vosk

## Stack

| Layer | Technologies |
|-------|--------------|
| UI | PyQt6, QSS styling |
| Voice input | SpeechRecognition, Google STT |
| Wake word | Vosk, PyAudio |
| TTS | pyttsx3 |
| Windows control | pywin32, keyboard, psutil |
| Packaging | PyInstaller, Inno Setup |

## Install

This is a Windows-only app.

The easiest path is to download a release build from:

- [GitHub Releases](https://github.com/LFroesch/vox/releases)

Release artifacts:

- `Vox-Setup-vX.Y.Z.exe`: installer build
- `vox-portable-vX.Y.Z.exe`: portable single-file build

## Run from source

Requirements:

- Windows 10 or 11
- Python 3.10+
- Microphone for voice features

Clone and install:

```powershell
git clone https://github.com/LFroesch/vox.git
cd vox
pip install -r requirements.txt
python main.py
```

## Wake word setup

Manual recording with the hotkey works without a wake word model. Wake word support needs the Vosk small English model available at one of these locations:

- `data/models/vosk/`
- `%USERPROFILE%\.vox\models\vosk\`

The expected model is `vosk-model-small-en-us-0.15`. The release workflow downloads and packages it automatically, but source runs need you to place it there yourself if you want wake word mode.

## Usage

Default interaction:

- Hold `F9` to record a command
- Speak naturally
- Vox routes the request through intent parsing, exact matches, fuzzy matching, and launcher/workflow fallbacks

Examples:

- `note call sam tomorrow`
- `remind me to stretch at 3pm`
- `set timer 10 minutes`
- `search for tailwind grid examples`
- `run dev setup`
- `coding layout`

## Main modules

| Module | Purpose |
|--------|---------|
| `modules/voice/` | Speech recognition, wake word, command routing, TTS |
| `modules/windows/` | Window discovery, layout save/restore, matching |
| `modules/launcher/` | Launch apps, terminals, URLs, folders, commands |
| `modules/workflows/` | Batch launch flows with optional linked layouts |
| `modules/reminders/` | Timers, alarms, recurring reminders |
| `modules/clipboard/` | Clipboard monitoring, history, snippets |
| `ui/` | Main app window, pages, widget, styles |

## Data location

Vox stores user data under `~/.vox/`, including:

- `config.json`
- `data/`
- `notes.md`
- `voice_log.txt`

## Development notes

- The project is developed in WSL but should be tested on Windows.
- Launcher args are intentionally passed as a single argument so Windows paths with spaces do not break.
- WSL terminal and project launchers rely on UNC-style paths such as `\\wsl$\Distro\...`.

## Packaging

Build a local executable with:

```powershell
python -m PyInstaller vox.spec --clean
```

Tagged pushes matching `v*` trigger the Windows release workflow in [`.github/workflows/release.yml`](.github/workflows/release.yml), which builds both the installer and portable release assets.

## License

[AGPL-3.0](LICENSE)
