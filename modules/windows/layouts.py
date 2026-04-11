import json
import time
import threading
from typing import Dict, List, Optional, Any
from pathlib import Path
from core.config import get_config
from .manager import WindowManager, WindowInfo

_BROWSER_TYPES = {'brave', 'chrome', 'firefox', 'edge'}

def _deferred_move(wm: WindowManager, hwnd: int, x: int, y: int, w: int, h: int, delay: float = 0.35):
    """Move window again after a short delay — fixes browser race on restore."""
    def _do():
        time.sleep(delay)
        wm.move_window(hwnd, x, y, w, h)
    threading.Thread(target=_do, daemon=True).start()


def _prime_browser_monitor(wm: WindowManager, hwnd: int, x: int, y: int, w: int, h: int):
    """Pre-position browser mostly on the target monitor before final placement."""
    seed_w = max(700, min(w, 1300))
    seed_h = max(500, min(h, 900))
    wm.move_window(hwnd, x + 40, y + 40, seed_w, seed_h)


def _staged_browser_move(wm: WindowManager, hwnd: int, x: int, y: int, w: int, h: int):
    """Apply immediate + delayed moves for browsers that drift after restore."""
    _prime_browser_monitor(wm, hwnd, x, y, w, h)
    wm.move_window(hwnd, x, y, w, h)
    _deferred_move(wm, hwnd, x, y, w, h, delay=0.25)
    _deferred_move(wm, hwnd, x, y, w, h, delay=0.60)


def _deferred_browser_maximize(wm: WindowManager, hwnd: int, x: int, y: int, w: int, h: int, delay: float = 0.35):
    """Re-prime monitor then maximize to keep browsers on the intended screen."""
    def _do():
        time.sleep(delay)
        _prime_browser_monitor(wm, hwnd, x, y, w, h)
        wm.maximize_window(hwnd)
    threading.Thread(target=_do, daemon=True).start()

class LayoutManager:
    """Manages window layout saving and restoration"""

    def __init__(self, window_manager: WindowManager):
        self.wm = window_manager
        self.config = get_config()
        self.layouts_file = self.config.get_data_path("window_layouts.json")
        self.layouts = self._load_layouts()

    def _load_layouts(self) -> Dict[str, Any]:
        """Load layouts from file"""
        if self.layouts_file.exists():
            try:
                with open(self.layouts_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading layouts: {e}")
        return {}

    def _save_layouts(self):
        """Save layouts to file"""
        try:
            with open(self.layouts_file, 'w') as f:
                json.dump(self.layouts, f, indent=2)
        except Exception as e:
            print(f"Error saving layouts: {e}")

    def get_layout_names(self) -> List[str]:
        """Get list of saved layout names"""
        return list(self.layouts.keys())

    def save_layout(self, name: str, windows: List[WindowInfo]) -> bool:
        """Save current window positions as a layout"""
        if not windows:
            return False

        layout_data = {}
        for i, window in enumerate(windows):
            identifier = self.wm.create_smart_identifier(window)
            layout_data[f"window_{i}"] = {
                "identifier": identifier,
                "position": {
                    "x": window.x,
                    "y": window.y,
                    "width": window.width,
                    "height": window.height
                },
                "exe_path": window.exe_path,
                "is_borderless": window.is_borderless,
                "is_maximized": window.is_maximized
            }

        self.layouts[name] = layout_data
        self._save_layouts()
        return True

    def load_layout(self, name: str, threshold: int = 40) -> Dict[str, Any]:
        """Load and apply a saved layout (pure positioning, no auto-launch)."""
        if name not in self.layouts:
            return {"success": False, "error": "Layout not found"}

        layout_data = self.layouts[name]
        current_windows = self.wm.get_all_windows_with_minimized()

        windows_by_app: Dict[str, List] = {}
        for w in current_windows:
            app_type = self.wm.get_app_type(w)
            if app_type not in windows_by_app:
                windows_by_app[app_type] = []
            windows_by_app[app_type].append(w)

        applied = 0
        failed = []

        for window_key, window_data in layout_data.items():
            if 'identifier' not in window_data:
                continue

            identifier = window_data['identifier']
            app_type = identifier.get('app_type', '')

            if app_type in windows_by_app and windows_by_app[app_type]:
                candidates = windows_by_app[app_type]
                # Use smart matching when multiple windows share same app_type
                if len(candidates) > 1:
                    match, _score = self.wm.match_window(identifier, candidates, threshold)
                    if match:
                        candidates.remove(match)
                    else:
                        match = candidates.pop(0)
                else:
                    match = candidates.pop(0)

                # Restore from minimized, maximized, or fullscreen before repositioning
                self.wm.restore_window(match.hwnd)
                saved_borderless = window_data.get('is_borderless', False)
                if self.wm.is_borderless(match.hwnd) != saved_borderless:
                    self.wm.set_borderless(match.hwnd, saved_borderless)
                pos = window_data.get('position', {})
                px = pos.get('x', 0)
                py = pos.get('y', 0)
                pw = pos.get('width', 1200)
                ph = pos.get('height', 800)
                if window_data.get('is_maximized', False):
                    # Always prime monitor position first so maximize lands on the right screen
                    _prime_browser_monitor(self.wm, match.hwnd, px, py, pw, ph)
                    self.wm.maximize_window(match.hwnd)
                    if app_type in _BROWSER_TYPES:
                        _deferred_browser_maximize(self.wm, match.hwnd, px, py, pw, ph)
                    applied += 1
                else:
                    sw, sh = self.wm.screen_width, self.wm.screen_height
                    # If saved size is >= 95% of screen, maximize rather than
                    # hard-placing (avoids DWM extended-frame overflow)
                    if pw >= sw * 0.95 and ph >= sh * 0.95:
                        _prime_browser_monitor(self.wm, match.hwnd, px, py, pw, ph)
                        self.wm.maximize_window(match.hwnd)
                        if app_type in _BROWSER_TYPES:
                            _deferred_browser_maximize(self.wm, match.hwnd, px, py, pw, ph)
                        applied += 1
                    elif self.wm.move_window(match.hwnd, px, py, pw, ph):
                        applied += 1
                        # Browsers need a second nudge — they often drift back after restore
                        if app_type in _BROWSER_TYPES:
                            _staged_browser_move(self.wm, match.hwnd, px, py, pw, ph)
            else:
                failed.append(f"{app_type} window")

        return {
            "success": True,
            "applied": applied,
            "total": len(layout_data),
            "failed": failed,
        }

    def delete_layout(self, name: str) -> bool:
        """Delete a saved layout"""
        if name in self.layouts:
            del self.layouts[name]
            self._save_layouts()
            return True
        return False

    def rename_layout(self, old_name: str, new_name: str) -> bool:
        """Rename a saved layout"""
        if old_name not in self.layouts or new_name in self.layouts:
            return False
        self.layouts[new_name] = self.layouts.pop(old_name)
        self._save_layouts()
        return True

    def get_layout_info(self, name: str) -> Optional[Dict[str, Any]]:
        """Get info about a layout"""
        if name not in self.layouts:
            return None

        layout = self.layouts[name]
        current_windows = self.wm.get_all_windows()

        # Count available windows by app type
        available_by_app: Dict[str, int] = {}
        for w in current_windows:
            app_type = self.wm.get_app_type(w)
            available_by_app[app_type] = available_by_app.get(app_type, 0) + 1

        matches = 0
        for window_data in layout.values():
            if 'identifier' in window_data:
                app_type = window_data['identifier'].get('app_type', '')
                if available_by_app.get(app_type, 0) > 0:
                    matches += 1
                    available_by_app[app_type] -= 1

        return {
            "name": name,
            "window_count": len(layout),
            "matches": matches
        }
