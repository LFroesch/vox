import subprocess
import os
import keyboard
import psutil
from typing import Dict, Any, Optional, Callable

# Command modules configuration
COMMAND_MODULES = {
    "spotify": {
        "description": "Control Spotify music player",
        "commands": {
            "open": {
                "phrases": ["open spotify", "start spotify", "launch spotify"],
                "description": "Opens the Spotify application"
            },
            "close": {
                "phrases": ["close spotify", "quit spotify", "exit spotify"],
                "description": "Closes the Spotify application"
            },
            "play_pause": {
                "phrases": [
                    "play spotify", "pause spotify", "spotify play", "spotify pause",
                    "play song", "pause song", "play music", "pause music", "resume music"
                ],
                "description": "Toggles play/pause for current track"
            },
            "next": {
                "phrases": ["next song", "skip song", "spotify next", "next track"],
                "description": "Skips to the next track"
            },
            "previous": {
                "phrases": ["previous song", "last song", "spotify previous", "previous track"],
                "description": "Goes back to the previous track"
            },
            "like": {
                "phrases": ["like song", "love song", "spotify like", "heart song"],
                "description": "Likes/unlikes the current song"
            }
        }
    },
    "system": {
        "description": "System control commands",
        "commands": {
            "volume_up": {
                "phrases": ["volume up", "increase volume", "louder"],
                "description": "Increases system volume"
            },
            "volume_down": {
                "phrases": ["volume down", "decrease volume", "quieter"],
                "description": "Decreases system volume"
            },
            "mute": {
                "phrases": ["mute", "silence", "turn off sound", "unmute"],
                "description": "Mutes/unmutes system audio"
            },
            "screenshot": {
                "phrases": ["take screenshot", "screenshot", "capture screen"],
                "description": "Takes a screenshot"
            }
        }
    },
    "browser": {
        "description": "Web browser commands",
        "commands": {
            "open_browser": {
                "phrases": ["open browser", "open chrome", "start browser", "open brave", "launch browser"],
                "description": "Opens the web browser"
            },
            "refresh": {
                "phrases": ["refresh", "reload page", "refresh page"],
                "description": "Refreshes the current page"
            },
            "new_tab": {
                "phrases": ["new tab", "open new tab"],
                "description": "Opens a new browser tab"
            },
            "close_tab": {
                "phrases": ["close tab", "close this tab"],
                "description": "Closes current browser tab"
            }
        }
    }
}


COMMAND_RESPONSES = {
    "spotify_open": "Opening Spotify",
    "spotify_close": "Closing Spotify",
    "spotify_play_pause": "Playing music",
    "spotify_next": "Skipping track",
    "spotify_previous": "Previous track",
    "spotify_like": "Liked",
    "system_volume_up": "Volume up",
    "system_volume_down": "Volume down",
    "system_mute": "Muted",
    "system_screenshot": "Taking screenshot",
    "browser_open_browser": "Opening browser",
    "browser_refresh": "Refreshing",
    "browser_new_tab": "New tab",
    "browser_close_tab": "Closing tab",
}


class CommandManager:
    """Manages voice command execution"""

    def __init__(self):
        self.command_map = self._build_command_map()
        self.custom_commands: Dict[str, Callable] = {}
        self.on_command_executed: Optional[Callable[[str, bool], None]] = None
        self.responses = COMMAND_RESPONSES

    def _build_command_map(self) -> Dict[str, str]:
        """Build phrase -> handler mapping"""
        command_map = {}
        for module_name, module_info in COMMAND_MODULES.items():
            for command_name, command_info in module_info["commands"].items():
                handler_name = f"{module_name}_{command_name}"
                for phrase in command_info["phrases"]:
                    command_map[phrase.lower()] = handler_name
        return command_map

    def register_custom_command(self, phrase: str, callback: Callable):
        """Register a custom voice command"""
        self.custom_commands[phrase.lower()] = callback
        print(f"Registered custom command: {phrase}")

    def execute(self, text: str) -> Dict[str, Any]:
        """Execute a voice command. Returns response to speak."""
        text_lower = text.lower().strip()

        # Check custom commands first
        if text_lower in self.custom_commands:
            try:
                self.custom_commands[text_lower]()
                self._notify_executed(text, True)
                return {"executed": True, "success": True, "type": "custom", "response": f"Loading {text}"}
            except Exception as e:
                print(f"Custom command error: {e}")
                self._notify_executed(text, False)
                return {"executed": True, "success": False, "type": "custom", "response": "Sorry, that failed"}

        # Check built-in commands
        if text_lower in self.command_map:
            handler_name = self.command_map[text_lower]
            handler = getattr(self, handler_name, None)

            if handler:
                try:
                    response = self.responses.get(handler_name, "Done")
                    success = handler()
                    self._notify_executed(text, success)
                    return {"executed": True, "success": success, "type": "builtin", "response": response}
                except Exception as e:
                    print(f"Command error ({handler_name}): {e}")
                    self._notify_executed(text, False)
                    return {"executed": True, "success": False, "type": "builtin", "response": "Sorry, that failed"}

        return {"executed": False, "success": False, "type": None, "response": None}

    def _notify_executed(self, command: str, success: bool):
        if self.on_command_executed:
            self.on_command_executed(command, success)

    # === Spotify Commands ===
    def spotify_open(self) -> bool:
        try:
            subprocess.run(["start", "spotify:"], shell=True, check=True)
            return True
        except:
            paths = [
                os.path.expanduser("~\\AppData\\Roaming\\Spotify\\Spotify.exe"),
                "C:\\Program Files\\Spotify\\Spotify.exe",
            ]
            for path in paths:
                if os.path.exists(path):
                    subprocess.run([path])
                    return True
        return False

    def spotify_close(self) -> bool:
        try:
            subprocess.run(['taskkill', '/f', '/im', 'Spotify.exe'],
                         capture_output=True)
            return True
        except:
            return False

    def spotify_play_pause(self) -> bool:
        keyboard.send('play/pause media')
        return True

    def spotify_next(self) -> bool:
        keyboard.send('next track')
        return True

    def spotify_previous(self) -> bool:
        keyboard.send('previous track')
        return True

    def spotify_like(self) -> bool:
        keyboard.send('alt+shift+b')
        return True

    # === System Commands ===
    def system_volume_up(self) -> bool:
        keyboard.send('volume up')
        return True

    def system_volume_down(self) -> bool:
        keyboard.send('volume down')
        return True

    def system_mute(self) -> bool:
        keyboard.send('volume mute')
        return True

    def system_screenshot(self) -> bool:
        keyboard.send('win+shift+s')
        return True

    # === Browser Commands ===
    def browser_open_browser(self) -> bool:
        try:
            paths = [
                "C:\\Program Files\\BraveSoftware\\Brave-Browser\\Application\\brave.exe",
                os.path.expanduser("~\\AppData\\Local\\BraveSoftware\\Brave-Browser\\Application\\brave.exe"),
                "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
            ]
            for path in paths:
                if os.path.exists(path):
                    subprocess.run([path])
                    return True
            subprocess.run(["start", "http://"], shell=True)
            return True
        except:
            return False

    def browser_refresh(self) -> bool:
        keyboard.send('f5')
        return True

    def browser_new_tab(self) -> bool:
        keyboard.send('ctrl+t')
        return True

    def browser_close_tab(self) -> bool:
        keyboard.send('ctrl+w')
        return True

    # === Layout Commands ===
    def register_layout_commands(self, layout_manager, on_load_callback=None):
        """Register voice commands for all saved layouts"""
        self.layout_manager = layout_manager
        self.layout_load_callback = on_load_callback
        self._refresh_layout_commands()

    def _refresh_layout_commands(self):
        """Refresh layout voice commands from saved layouts"""
        if not hasattr(self, 'layout_manager'):
            return
        # Remove old layout commands
        self.custom_commands = {k: v for k, v in self.custom_commands.items()
                               if not getattr(v, '_is_layout_cmd', False)}
        # Add new ones
        for name in self.layout_manager.get_layout_names():
            def make_loader(layout_name):
                def load():
                    result = self.layout_manager.load_layout(layout_name)
                    if self.layout_load_callback:
                        self.layout_load_callback(layout_name, result)
                load._is_layout_cmd = True
                return load
            loader = make_loader(name)
            self.custom_commands[f"{name} layout".lower()] = loader
            self.custom_commands[name.lower()] = loader
