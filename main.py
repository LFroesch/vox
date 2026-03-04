#!/usr/bin/env python3
"""
vox - Voice-powered productivity hub

A unified tool for:
- Voice commands and control
- Window management and layouts
- Quick launcher for apps/scripts
- Clipboard history management

Usage:
    python main.py
"""

import sys
import os
import socket

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

VOX_PORT = 19847


def _signal_existing_instance():
    """Try to signal an already-running vox instance to show itself.
    Returns True if an existing instance was found and signaled."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        sock.connect(("127.0.0.1", VOX_PORT))
        sock.sendall(b"SHOW")
        sock.close()
        return True
    except (ConnectionRefusedError, OSError):
        return False


def main():
    """Main entry point"""
    if _signal_existing_instance():
        print("vox is already running — bringing it to front.")
        sys.exit(0)

    print("Starting vox...")
    from PyQt6.QtWidgets import QApplication
    q_app = QApplication(sys.argv)
    q_app.setApplicationName("vox")

    from ui import VoxApp
    app = VoxApp(q_app)
    app.run()


if __name__ == "__main__":
    main()
