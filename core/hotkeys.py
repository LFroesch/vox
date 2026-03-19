import keyboard
from typing import Callable, Dict

class HotkeyManager:
    """Manages global hotkeys for vox"""

    def __init__(self):
        self.registered_hotkeys: Dict[str, Callable] = {}

    def register(self, hotkey: str, callback: Callable, description: str = "") -> bool:
        """Register a global hotkey"""
        try:
            # Unregister if already registered
            if hotkey in self.registered_hotkeys:
                self.unregister(hotkey)

            keyboard.add_hotkey(hotkey, callback, suppress=True, trigger_on_release=True)
            self.registered_hotkeys[hotkey] = callback
            print(f"Registered hotkey: {hotkey.upper()} - {description}")
            return True
        except Exception as e:
            print(f"Failed to register hotkey {hotkey}: {e}")
            return False

    def unregister(self, hotkey: str) -> bool:
        """Unregister a hotkey"""
        try:
            if hotkey in self.registered_hotkeys:
                keyboard.remove_hotkey(hotkey)
                del self.registered_hotkeys[hotkey]
                print(f"Unregistered hotkey: {hotkey.upper()}")
                return True
        except Exception as e:
            print(f"Failed to unregister hotkey {hotkey}: {e}")
        return False

    def unregister_all(self):
        """Unregister all hotkeys"""
        for hotkey in list(self.registered_hotkeys.keys()):
            self.unregister(hotkey)

    def update_hotkey(self, old_hotkey: str, new_hotkey: str, callback: Callable = None) -> bool:
        """Update a hotkey binding"""
        if callback is None and old_hotkey in self.registered_hotkeys:
            callback = self.registered_hotkeys[old_hotkey]

        if callback is None:
            return False

        self.unregister(old_hotkey)
        return self.register(new_hotkey, callback)

    def cleanup(self):
        """Cleanup all hotkeys on exit"""
        try:
            keyboard.unhook_all()
            self.registered_hotkeys.clear()
        except:
            pass
