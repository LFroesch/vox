import pyperclip
import json
import threading
import time
from typing import List, Optional, Callable
from dataclasses import dataclass, asdict
from datetime import datetime
from core.config import get_config

@dataclass
class ClipboardEntry:
    """A clipboard history entry"""
    content: str
    timestamp: str
    preview: str  # Truncated preview for display

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'ClipboardEntry':
        return cls(**data)


class ClipboardManager:
    """Manages clipboard history and quick paste"""

    MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

    def __init__(self):
        self.config = get_config()
        self.history: List[ClipboardEntry] = []
        self.max_history = self.config.get('clipboard', 'history_size', default=200)
        self.history_file = self.config.get_data_path("clipboard_history.json")

        self._last_content = ""
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self.on_new_entry: Optional[Callable[[ClipboardEntry], None]] = None

        self._load_history()

    def _load_history(self):
        """Load history from file"""
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.history = [ClipboardEntry.from_dict(entry) for entry in data]
            except Exception as e:
                print(f"Error loading clipboard history: {e}")
                self.history = []

    def _save_history(self):
        """Save history to file, truncating oldest entries if over 5MB"""
        try:
            to_save = list(self.history)
            while to_save:
                data = json.dumps([entry.to_dict() for entry in to_save], indent=2)
                if len(data.encode('utf-8')) <= self.MAX_FILE_SIZE:
                    break
                to_save.pop()  # Remove oldest entry (list is newest-first)
            else:
                data = "[]"
            with open(self.history_file, 'w', encoding='utf-8') as f:
                f.write(data)
        except Exception as e:
            print(f"Error saving clipboard history: {e}")

    def start_monitoring(self):
        """Start monitoring clipboard for changes"""
        if self._monitoring:
            return

        self._monitoring = True
        self._last_content = self._get_current()
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        print("Clipboard monitoring started")

    def stop_monitoring(self):
        """Stop monitoring clipboard"""
        self._monitoring = False

    def _monitor_loop(self):
        """Monitor clipboard for changes"""
        while self._monitoring:
            try:
                current = self._get_current()
                if current and current != self._last_content:
                    self._last_content = current
                    self._add_entry(current)
            except Exception as e:
                pass  # Ignore clipboard access errors
            time.sleep(0.5)

    def _get_current(self) -> str:
        """Get current clipboard content"""
        try:
            return pyperclip.paste()
        except:
            return ""

    def _add_entry(self, content: str):
        """Add a new entry to history"""
        if not content or not content.strip():
            return

        # Create preview (first 100 chars, single line)
        preview = content[:100].replace('\n', ' ').replace('\r', '').strip()
        if len(content) > 100:
            preview += "..."

        entry = ClipboardEntry(
            content=content,
            timestamp=datetime.now().strftime("%Y-%m-%d ") + datetime.now().strftime("%I:%M:%S %p").lstrip("0"),
            preview=preview
        )

        # Remove duplicate if exists
        self.history = [e for e in self.history if e.content != content]

        # Add to front
        self.history.insert(0, entry)

        # Trim to max size
        if len(self.history) > self.max_history:
            self.history = self.history[:self.max_history]

        self._save_history()

        if self.on_new_entry:
            self.on_new_entry(entry)

    def get_history(self, limit: int = 0) -> List[ClipboardEntry]:
        """Get clipboard history"""
        if limit > 0:
            return self.history[:limit]
        return self.history.copy()

    def paste(self, index: int) -> bool:
        """Paste an item from history by index"""
        if 0 <= index < len(self.history):
            try:
                pyperclip.copy(self.history[index].content)
                return True
            except:
                pass
        return False

    def paste_content(self, content: str) -> bool:
        """Paste specific content"""
        try:
            pyperclip.copy(content)
            return True
        except:
            return False

    def clear_history(self):
        """Clear clipboard history"""
        self.history = []
        self._save_history()

    def delete_entry(self, index: int) -> bool:
        """Delete a specific entry"""
        if 0 <= index < len(self.history):
            self.history.pop(index)
            self._save_history()
            return True
        return False

    def search(self, query: str) -> List[ClipboardEntry]:
        """Search clipboard history"""
        query_lower = query.lower()
        return [
            entry for entry in self.history
            if query_lower in entry.content.lower()
        ]
