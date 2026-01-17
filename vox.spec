# -*- mode: python ; coding: utf-8 -*-
# vox.spec - PyInstaller spec file for vox

import sys
from pathlib import Path

block_cipher = None

# Get customtkinter path for assets
import customtkinter
ctk_path = Path(customtkinter.__file__).parent

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
        # Include customtkinter assets
        (str(ctk_path), 'customtkinter'),
        # Include icon
        ('myicon.ico', '.'),
    ],
    hiddenimports=[
        # CustomTkinter
        'customtkinter',
        'PIL',
        'PIL._tkinter_finder',
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
    excludes=[],
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
