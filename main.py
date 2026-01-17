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

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ui import VoxApp


def main():
    """Main entry point"""
    print("Starting vox...")
    app = VoxApp()
    app.run()


if __name__ == "__main__":
    main()
