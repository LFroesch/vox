# -*- mode: python ; coding: utf-8 -*-
# vox.spec - PyInstaller spec file for vox (PyQt6)

import sys
import os
from pathlib import Path

block_cipher = None

# Get vosk path for DLLs
try:
    import vosk
    vosk_path = Path(vosk.__file__).parent
except ImportError:
    vosk_path = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[(str(vosk_path), 'vosk')] if vosk_path else [],
    datas=[
        # Include icon
        ('myicon.ico', '.'),
        # Vosk wake word model
        ('data/models/vosk', 'data/models/vosk'),
    ],
    hiddenimports=[
        # PyQt6
        'PyQt6',
        'PyQt6.QtWidgets',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.sip',
        # Windows APIs
        'win32api',
        'win32con',
        'win32gui',
        'win32process',
        'pywintypes',
        'pythoncom',
        # Speech Recognition
        'speech_recognition',
        # Vosk
        'vosk',
        # TTS
        'pyttsx3',
        'comtypes',
        # Other deps
        'keyboard',
        'pyperclip',
        'psutil',
        # Standard library that might be missed
        'json',
        'threading',
        'queue',
        'dataclasses',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'customtkinter',
        'PIL',
        'pystray',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='vox',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='myicon.ico',
)
