import re
import subprocess
import os
import keyboard
import psutil
import webbrowser
import urllib.parse
from difflib import SequenceMatcher
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
    "browser_search": "Searching",
}


class CommandManager:
    """Manages voice command execution"""

    def __init__(self):
        self.command_map = self._build_command_map()
        self.custom_commands: Dict[str, Callable] = {}
        self.custom_responses: Dict[str, str] = {}
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

    def register_custom_command(self, phrase: str, callback: Callable, response: str = None):
        """Register a custom voice command with optional TTS response"""
        self.custom_commands[phrase.lower()] = callback
        if response:
            self.custom_responses[phrase.lower()] = response
        print(f"Registered custom command: {phrase}")

    def execute(self, text: str) -> Dict[str, Any]:
        """Execute a voice command. Returns response to speak."""
        text_lower = text.lower().strip()

        # Check for search query before phrase matching
        search_query = self._extract_search_query(text_lower)
        if search_query is not None:
            success = self.browser_search(search_query)
            self._notify_executed(text, success)
            return {"executed": True, "success": success, "type": "builtin", "response": f"Searching for {search_query}"}

        # Check custom commands first
        if text_lower in self.custom_commands:
            try:
                self.custom_commands[text_lower]()
                response = self.custom_responses.get(text_lower, "Done")
                self._notify_executed(text, True)
                return {"executed": True, "success": True, "type": "custom", "response": response}
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

        # Fuzzy match built-in commands
        match = self._fuzzy_match(text_lower)
        if match:
            handler_name, source = match
            if source == "custom":
                try:
                    self.custom_commands[handler_name]()
                    response = self.custom_responses.get(handler_name, "Done")
                    self._notify_executed(text, True)
                    return {"executed": True, "success": True, "type": "custom", "response": response}
                except Exception as e:
                    print(f"Custom command error: {e}")
                    self._notify_executed(text, False)
                    return {"executed": True, "success": False, "type": "custom", "response": "Sorry, that failed"}
            else:
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

    def _fuzzy_match(self, text: str):
        """Find best matching phrase via token overlap when exact match fails.
        Returns (handler_name, source) or None. source is 'builtin' or 'custom'."""
        STOP_WORDS = {"the", "a", "an", "this", "that", "some", "my", "please", "can", "you", "to", "do", "it", "is"}
        input_tokens = set(text.lower().split()) - STOP_WORDS
        if not input_tokens:
            return None

        best_score = 0.0
        best_match = None

        # Score built-in commands
        for phrase, handler_name in self.command_map.items():
            phrase_tokens = set(phrase.split()) - STOP_WORDS
            if not phrase_tokens:
                continue
            overlap = len(input_tokens & phrase_tokens)
            score = overlap / len(phrase_tokens)
            if score > best_score:
                best_score = score
                best_match = (handler_name, "builtin")

        # Score custom commands
        for phrase in self.custom_commands:
            phrase_tokens = set(phrase.split()) - STOP_WORDS
            if not phrase_tokens:
                continue
            overlap = len(input_tokens & phrase_tokens)
            score = overlap / len(phrase_tokens)
            if score > best_score:
                best_score = score
                best_match = (phrase, "custom")

        # Require all key tokens of the phrase to be present (score == 1.0)
        # or at least 0.75 for longer phrases (3+ tokens)
        if best_match:
            if best_score >= 1.0:
                return best_match
            if best_score >= 0.75:
                # Only allow partial match for phrases with 3+ key tokens
                phrase = None
                if best_match[1] == "builtin":
                    for p, h in self.command_map.items():
                        if h == best_match[0]:
                            phrase = p
                            break
                else:
                    phrase = best_match[0]
                if phrase and len(set(phrase.split()) - STOP_WORDS) >= 3:
                    return best_match

        # Phonetic/similarity fallback — catches near-misses like "necks song" → "next song"
        best_sim = 0.0
        best_sim_match = None
        for phrase, handler_name in self.command_map.items():
            ratio = SequenceMatcher(None, text, phrase).ratio()
            if ratio > best_sim:
                best_sim = ratio
                best_sim_match = (handler_name, "builtin")
        for phrase in self.custom_commands:
            ratio = SequenceMatcher(None, text, phrase).ratio()
            if ratio > best_sim:
                best_sim = ratio
                best_sim_match = (phrase, "custom")
        if best_sim >= 0.8:
            return best_sim_match

        return None

    def _notify_executed(self, command: str, success: bool):
        if self.on_command_executed:
            self.on_command_executed(command, success)

    def _extract_search_query(self, text: str) -> Optional[str]:
        """Extract search query from natural language, or None if not a search request."""
        strip_prefixes = [
            "search for ", "search ", "google ", "look up ",
            "find me ", "find ",
            "define ", "definition of ",
        ]
        keep_prefixes = [
            "what is ", "what are ", "who is ", "who are ",
            "where is ", "where are ", "when is ", "when are ",
            "how to ", "how do ", "how does ", "why is ", "why does ",
            "what is the meaning of ",
        ]
        # Wrap-around patterns: trigger words surround the query
        wrap_patterns = [
            r"^what (?:does|do) (.+?) mean$",
            r"^what (?:does|do) (.+?) stand for$",
            r"^what(?:'s| is) the (?:meaning|definition) of (.+)$",
        ]
        for prefix in strip_prefixes:
            if text.startswith(prefix):
                query = text[len(prefix):].strip()
                if query:
                    return query
        for prefix in keep_prefixes:
            if text.startswith(prefix):
                return text.strip()
        for pattern in wrap_patterns:
            m = re.match(pattern, text)
            if m:
                return f"what does {m.group(1)} mean"
        return None

    def browser_search(self, query: str) -> bool:
        url = f"https://www.google.com/search?q={urllib.parse.quote_plus(query)}"
        webbrowser.open(url)
        return True

    # === Spotify Commands ===
    _NO_WINDOW = 0x08000000 if os.name == "nt" else 0

    def spotify_open(self) -> bool:
        try:
            subprocess.run(["start", "spotify:"], shell=True, check=True, creationflags=self._NO_WINDOW)
            return True
        except Exception:
            paths = [
                os.path.expanduser("~\\AppData\\Roaming\\Spotify\\Spotify.exe"),
                "C:\\Program Files\\Spotify\\Spotify.exe",
            ]
            for path in paths:
                if os.path.exists(path):
                    subprocess.Popen([path], creationflags=self._NO_WINDOW)
                    return True
        return False

    def spotify_close(self) -> bool:
        try:
            subprocess.run(['taskkill', '/f', '/im', 'Spotify.exe'],
                         capture_output=True, creationflags=self._NO_WINDOW)
            return True
        except Exception:
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
                    subprocess.Popen([path])
                    return True
            subprocess.run(["start", "http://"], shell=True, creationflags=self._NO_WINDOW)
            return True
        except Exception:
            return False

    # === Launcher Commands ===
    def register_launcher_commands(self, launcher):
        """Register voice commands for all launcher items"""
        self.launcher = launcher
        self._refresh_launcher_commands()

    def _refresh_launcher_commands(self):
        """Refresh launcher voice commands from saved items"""
        if not hasattr(self, 'launcher'):
            return
        # Remove old launcher commands
        old_keys = [k for k, v in self.custom_commands.items() if getattr(v, '_is_launcher_cmd', False)]
        for k in old_keys:
            del self.custom_commands[k]
            self.custom_responses.pop(k, None)
        # Add current ones
        for item in self.launcher.get_all_items():
            if item.voice_phrase:
                resp = f"Launching {item.name}" if item.item_type in ("app", "terminal") else f"Opening {item.name}"
                def make_launcher(i):
                    def launch():
                        self.launcher.launch(i)
                    launch._is_launcher_cmd = True
                    return launch
                callback = make_launcher(item)
                # Register exact voice phrase + prefix variants (like layouts)
                phrases = [item.voice_phrase.lower()]
                name_lower = item.name.lower()
                for prefix in ("open", "launch", "start", "run"):
                    phrases.append(f"{prefix} {name_lower}")
                for phrase in set(phrases):
                    self.custom_commands[phrase] = callback
                    self.custom_responses[phrase] = resp

    # === Workflow Commands ===
    def register_workflow_commands(self, workflow_manager, on_run_callback=None):
        """Register voice commands for all saved workflows"""
        self.workflow_manager = workflow_manager
        self.workflow_run_callback = on_run_callback
        self._refresh_workflow_commands()

    def _refresh_workflow_commands(self):
        """Refresh workflow voice commands from saved workflows"""
        if not hasattr(self, 'workflow_manager'):
            return
        # Remove old workflow commands
        old_keys = [k for k, v in self.custom_commands.items() if getattr(v, '_is_workflow_cmd', False)]
        for k in old_keys:
            del self.custom_commands[k]
            self.custom_responses.pop(k, None)
        # Add current ones
        for name in self.workflow_manager.get_names():
            wf = self.workflow_manager.get(name)
            if not wf:
                continue
            response = f"Running {name} workflow"
            def make_runner(wf_name):
                def run():
                    if self.workflow_run_callback:
                        self.workflow_run_callback(wf_name)
                run._is_workflow_cmd = True
                return run
            runner = make_runner(name)
            # Register phrases: name, "X workflow", voice_phrase, + prefixes
            phrases = [name.lower(), f"{name} workflow".lower()]
            if wf.voice_phrase:
                phrases.append(wf.voice_phrase.lower())
            for prefix in ("run", "start", "launch", "execute"):
                phrases.append(f"{prefix} {name}".lower())
            for phrase in set(phrases):
                self.custom_commands[phrase] = runner
                self.custom_responses[phrase] = response

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
        old_keys = [k for k, v in self.custom_commands.items() if getattr(v, '_is_layout_cmd', False)]
        for k in old_keys:
            del self.custom_commands[k]
            self.custom_responses.pop(k, None)
        # Add new ones
        for name in self.layout_manager.get_layout_names():
            layout_data = self.layout_manager.layouts.get(name, {})
            meta = layout_data.get('_meta', {})
            voice_phrase = meta.get('voice_phrase', '').strip()
            response = f"Swapping to {name} layout"
            def make_loader(layout_name):
                def load():
                    result = self.layout_manager.load_layout(layout_name)
                    if self.layout_load_callback:
                        self.layout_load_callback(layout_name, result)
                load._is_layout_cmd = True
                return load
            loader = make_loader(name)
            # Register: "coding", "coding layout", "swap coding", "launch coding", etc.
            base = voice_phrase.lower() if voice_phrase else name.lower()
            phrases = [base, f"{base} layout"]
            for prefix in ("swap", "launch", "load", "switch to", "open"):
                phrases.append(f"{prefix} {base}")
            # Also register the name itself if voice phrase differs
            if voice_phrase and voice_phrase.lower() != name.lower():
                phrases.append(name.lower())
            for phrase in phrases:
                self.custom_commands[phrase] = loader
                self.custom_responses[phrase] = response
