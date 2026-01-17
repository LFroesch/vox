import subprocess
import os
import time
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, asdict
from pathlib import Path
from core.config import get_config

try:
    import pyautogui
    pyautogui.FAILSAFE = False  # Don't abort if mouse in corner
except ImportError:
    pyautogui = None

try:
    import win32gui
    import win32con
except ImportError:
    win32gui = None
    win32con = None

@dataclass
class LaunchItem:
    """A launchable item (app, script, URL, etc.)"""
    name: str
    path: str
    item_type: str  # "app", "script", "url", "folder", "command", "terminal"
    voice_phrase: Optional[str] = None
    hotkey: Optional[str] = None
    args: str = ""
    icon: str = ""
    terminal_type: Optional[str] = None  # "powershell" or "wsl" (for item_type="terminal")
    new_tab: bool = False  # Always open in new terminal tab

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'LaunchItem':
        return cls(**data)


class Launcher:
    """Quick launcher for apps, scripts, and commands"""

    def __init__(self):
        self.config = get_config()
        self.items: List[LaunchItem] = []
        self._load_items()

    def _load_items(self):
        """Load saved launch items"""
        items_data = self.config.get('launcher', 'items', default=[])
        self.items = [LaunchItem.from_dict(item) for item in items_data]

    def _save_items(self):
        """Save launch items to config"""
        items_data = [item.to_dict() for item in self.items]
        self.config.set('launcher', 'items', value=items_data)

    def add_item(self, item: LaunchItem) -> bool:
        """Add a new launch item"""
        # Check for duplicates
        if any(i.name.lower() == item.name.lower() for i in self.items):
            return False
        self.items.append(item)
        self._save_items()
        return True

    def remove_item(self, name: str) -> bool:
        """Remove a launch item by name"""
        for i, item in enumerate(self.items):
            if item.name.lower() == name.lower():
                self.items.pop(i)
                self._save_items()
                return True
        return False

    def get_item(self, name: str) -> Optional[LaunchItem]:
        """Get a launch item by name"""
        for item in self.items:
            if item.name.lower() == name.lower():
                return item
        return None

    def get_by_voice_phrase(self, phrase: str) -> Optional[LaunchItem]:
        """Get a launch item by its voice phrase"""
        phrase_lower = phrase.lower().strip()
        for item in self.items:
            if item.voice_phrase and item.voice_phrase.lower() == phrase_lower:
                return item
        return None

    def launch(self, item: LaunchItem) -> bool:
        """Launch an item"""
        try:
            if item.item_type == "app":
                return self._launch_app(item)
            elif item.item_type == "script":
                return self._launch_script(item)
            elif item.item_type == "url":
                return self._launch_url(item)
            elif item.item_type == "folder":
                return self._launch_folder(item)
            elif item.item_type == "command":
                return self._launch_command(item)
            elif item.item_type == "terminal":
                return self._launch_terminal_command(item)
            return False
        except Exception as e:
            print(f"Launch error: {e}")
            return False

    def launch_by_name(self, name: str) -> bool:
        """Launch an item by name"""
        item = self.get_item(name)
        if item:
            return self.launch(item)
        return False

    def _launch_app(self, item: LaunchItem) -> bool:
        """Launch an application"""
        path = os.path.expandvars(os.path.expanduser(item.path))
        if os.path.exists(path):
            args = item.args.split() if item.args else []
            subprocess.Popen([path] + args)
            return True
        # Try via start command
        subprocess.run(["start", "", item.path], shell=True)
        return True

    def _launch_script(self, item: LaunchItem) -> bool:
        """Launch a script"""
        path = os.path.expandvars(os.path.expanduser(item.path))
        if not os.path.exists(path):
            return False

        ext = Path(path).suffix.lower()
        args = item.args.split() if item.args else []

        if ext == '.py':
            subprocess.Popen(['python', path] + args)
        elif ext == '.ps1':
            subprocess.Popen(['powershell', '-ExecutionPolicy', 'Bypass', '-File', path] + args)
        elif ext == '.bat' or ext == '.cmd':
            subprocess.Popen([path] + args, shell=True)
        else:
            subprocess.Popen([path] + args)
        return True

    def _launch_url(self, item: LaunchItem) -> bool:
        """Open a URL in browser"""
        import webbrowser
        webbrowser.open(item.path)
        return True

    def _launch_folder(self, item: LaunchItem) -> bool:
        """Open a folder in explorer"""
        path = os.path.normpath(os.path.expandvars(os.path.expanduser(item.path)))
        if os.path.isdir(path):
            subprocess.Popen(['explorer', path])
            return True
        return False

    def _launch_command(self, item: LaunchItem) -> bool:
        """Execute a shell command"""
        subprocess.Popen(item.path, shell=True)
        return True

    def _launch_terminal_command(self, item: LaunchItem) -> bool:
        """Execute a command in an existing or new terminal"""
        if not pyautogui or not win32gui:
            print("pyautogui or win32gui not available")
            return False

        terminal_type = item.terminal_type or "powershell"
        command = item.path

        # If new_tab requested, always open new tab
        if item.new_tab:
            return self._open_new_terminal_tab(terminal_type, command)

        # Try to find existing terminal window
        terminal_hwnd = self._find_terminal_window(terminal_type)

        if terminal_hwnd:
            # Focus existing terminal and type command
            self._focus_window(terminal_hwnd)
            time.sleep(0.15)
            pyautogui.typewrite(command, interval=0.01) if command.isascii() else pyautogui.write(command)
            pyautogui.press('enter')
            return True
        else:
            return self._open_new_terminal_tab(terminal_type, command)

    def _open_new_terminal_tab(self, terminal_type: str, command: str) -> bool:
        """Open a new terminal tab and run command"""
        try:
            if terminal_type == "powershell":
                subprocess.Popen(['wt.exe', '-w', '0', 'nt', 'powershell.exe'])
            elif terminal_type == "wsl":
                subprocess.Popen(['wt.exe', '-w', '0', 'nt', '-p', 'Ubuntu'])
        except FileNotFoundError:
            # Fallback if wt.exe not found
            if terminal_type == "powershell":
                subprocess.Popen(['powershell'])
            elif terminal_type == "wsl":
                subprocess.Popen(['wsl'])

        time.sleep(0.8)
        if command:
            pyautogui.typewrite(command, interval=0.01) if command.isascii() else pyautogui.write(command)
            pyautogui.press('enter')
        return True

    def _find_terminal_window(self, terminal_type: str) -> Optional[int]:
        """Find an existing terminal window by type"""
        if not win32gui:
            return None

        found_hwnd = None

        def enum_callback(hwnd, _):
            nonlocal found_hwnd
            if not win32gui.IsWindowVisible(hwnd):
                return True

            class_name = win32gui.GetClassName(hwnd)
            title = win32gui.GetWindowText(hwnd).lower()

            # Windows Terminal (CASCADIA) - check title carefully
            if "CASCADIA" in class_name:
                if terminal_type == "wsl":
                    # WSL titles contain: ubuntu, wsl, bash, or distro name
                    if any(x in title for x in ["ubuntu", "wsl", "debian", "kali", "bash", "zsh"]):
                        # Make sure it's NOT powershell
                        if "powershell" not in title and "pwsh" not in title:
                            found_hwnd = hwnd
                            return False
                elif terminal_type == "powershell":
                    if "powershell" in title or "pwsh" in title:
                        found_hwnd = hwnd
                        return False
            # Legacy console windows
            elif class_name == "ConsoleWindowClass":
                if terminal_type == "wsl" and any(x in title for x in ["ubuntu", "wsl", "bash"]):
                    found_hwnd = hwnd
                    return False
                elif terminal_type == "powershell" and "powershell" in title:
                    found_hwnd = hwnd
                    return False
            return True

        try:
            win32gui.EnumWindows(enum_callback, None)
        except Exception:
            pass

        return found_hwnd

    def _focus_window(self, hwnd: int):
        """Focus a window by its handle"""
        if not win32gui or not win32con:
            return
        try:
            # Restore if minimized
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            # Bring to front
            win32gui.SetForegroundWindow(hwnd)
        except Exception as e:
            print(f"Focus error: {e}")

    def get_all_items(self) -> List[LaunchItem]:
        """Get all launch items"""
        return self.items.copy()

    def get_voice_commands(self) -> Dict[str, LaunchItem]:
        """Get mapping of voice phrases to items"""
        return {
            item.voice_phrase.lower(): item
            for item in self.items
            if item.voice_phrase
        }
