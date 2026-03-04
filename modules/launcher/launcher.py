import subprocess
import os
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, asdict
from pathlib import Path
from core.config import get_config


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
    terminal_type: Optional[str] = None  # "powershell", "wsl", or "cmd" (for item_type="terminal")
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
        # .lnk shortcuts and non-exe files need os.startfile or start command
        ext = Path(path).suffix.lower()
        if ext in ('.lnk', '.url', '.appref-ms'):
            os.startfile(path)
            return True
        if os.path.exists(path):
            args = item.args.split() if item.args else []
            subprocess.Popen([path] + args)
            return True
        # Try via start command (quote path for spaces)
        subprocess.run(f'start "" "{item.path}"', shell=True)
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
        """Execute a command in a new terminal tab via shell arguments"""
        terminal_type = item.terminal_type or "powershell"
        command = item.path

        # Support multi-line commands (split and chain with &&)
        if '\n' in command:
            lines = [line.strip() for line in command.split('\n') if line.strip()]
            if terminal_type == "powershell":
                command = '; '.join(lines)  # PowerShell uses semicolon
            else:
                command = ' && '.join(lines)  # Bash/cmd use &&

        return self._open_new_terminal_tab(terminal_type, command)

    def _open_new_terminal_tab(self, terminal_type: str, command: str) -> bool:
        """Open a new terminal tab with command passed as shell arguments"""
        try:
            if terminal_type == "powershell":
                if command:
                    subprocess.Popen(['wt.exe', '-w', '0', 'nt', '--', 'powershell.exe', '-NoExit', '-Command', command])
                else:
                    subprocess.Popen(['wt.exe', '-w', '0', 'nt', '--', 'powershell.exe'])
            elif terminal_type == "wsl":
                if command:
                    # Can't use ; in wt.exe args (it's a tab separator) — use && with fallback
                    subprocess.Popen(['wt.exe', '-w', '0', 'nt', '--', 'wsl.exe', 'bash', '-lic',
                                      f'{command} && exec bash -l || exec bash -l'])
                else:
                    subprocess.Popen(['wt.exe', '-w', '0', 'nt', '--', 'wsl.exe'])
            elif terminal_type == "cmd":
                if command:
                    subprocess.Popen(['wt.exe', '-w', '0', 'nt', '--', 'cmd.exe', '/k', command])
                else:
                    subprocess.Popen(['wt.exe', '-w', '0', 'nt', '--', 'cmd.exe'])
            else:
                return False
        except FileNotFoundError:
            # Fallback if wt.exe not found
            if terminal_type == "powershell":
                if command:
                    subprocess.Popen(['powershell.exe', '-NoExit', '-Command', command])
                else:
                    subprocess.Popen(['powershell.exe'])
            elif terminal_type == "wsl":
                if command:
                    subprocess.Popen(['wsl.exe', 'bash', '-lic', f'{command}; exec bash -l'])
                else:
                    subprocess.Popen(['wsl.exe'])
            elif terminal_type == "cmd":
                if command:
                    subprocess.Popen(['cmd.exe', '/k', command])
                else:
                    subprocess.Popen(['cmd.exe'])
        return True

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
