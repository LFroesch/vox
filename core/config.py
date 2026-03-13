import json
import os
from pathlib import Path

class Config:
    """Central configuration management for vox"""

    def __init__(self):
        self.config_dir = Path.home() / ".vox"
        self.config_file = self.config_dir / "config.json"
        self.data_dir = self.config_dir / "data"

        # Ensure directories exist
        self.config_dir.mkdir(exist_ok=True)
        self.data_dir.mkdir(exist_ok=True)

        # Default settings
        self.defaults = {
            "hotkeys": {
                "voice_record": "f9",
                "clipboard_history": "ctrl+shift+v",
                "quick_launcher": "ctrl+space"
            },
            "voice": {
                "energy_threshold": 300,
                "pause_threshold": 1.5,
                "phrase_time_limit": 60
            },
            "windows": {
                "match_threshold": 40
            },
            "clipboard": {
                "history_size": 50
            },
            "launcher": {
                "items": []
            },
            "favorites": {
                "layouts": [],
                "launchers": []
            },
            "general": {
                "editor": "system"
            },
            "ui": {
                "theme": "dark",
                "start_minimized": False,
                "close_behavior": "ask",
                "widget_enabled": True,
                "widget_visible_in_tray": False,
                "ui_scale": "Medium",
                "widget_size": "Medium",
                "voice_response": True
            }
        }

        self.settings = self.load()

    def load(self) -> dict:
        """Load settings from file or return defaults"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    saved = json.load(f)
                # Merge with defaults (saved takes priority)
                return self._deep_merge(self.defaults.copy(), saved)
            except Exception as e:
                print(f"Error loading config: {e}")
        return self.defaults.copy()

    def save(self):
        """Save current settings to file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")

    def get(self, *keys, default=None):
        """Get nested config value: config.get('hotkeys', 'voice_record')"""
        value = self.settings
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value

    def set(self, *keys, value):
        """Set nested config value: config.set('hotkeys', 'voice_record', value='f10')"""
        if len(keys) < 1:
            return

        target = self.settings
        for key in keys[:-1]:
            if key not in target:
                target[key] = {}
            target = target[key]

        target[keys[-1]] = value
        self.save()

    def _deep_merge(self, base: dict, override: dict) -> dict:
        """Deep merge two dictionaries"""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def get_data_path(self, filename: str) -> Path:
        """Get path to a data file"""
        return self.data_dir / filename


# Global config instance
_config = None

def get_config() -> Config:
    global _config
    if _config is None:
        _config = Config()
    return _config
