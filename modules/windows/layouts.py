import json
import subprocess
import threading
import time
from typing import Dict, List, Optional, Any
from pathlib import Path
from core.config import get_config
from .manager import WindowManager, WindowInfo

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

    def save_layout(self, name: str, windows: List[WindowInfo], auto_launch_config: Dict[int, bool] = None) -> bool:
        """Save current window positions as a layout"""
        if not windows:
            return False

        if auto_launch_config is None:
            auto_launch_config = {}

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
                "auto_launch": auto_launch_config.get(window.hwnd, False),
                "is_borderless": window.is_borderless
            }

        self.layouts[name] = layout_data
        self._save_layouts()
        return True

    def load_layout(self, name: str, threshold: int = 40) -> Dict[str, Any]:
        """Load and apply a saved layout"""
        if name not in self.layouts:
            return {"success": False, "error": "Layout not found"}

        layout_data = self.layouts[name]
        current_windows = self.wm.get_all_windows_with_minimized()

        # Snapshot all existing hwnds so launched apps can be distinguished
        existing_hwnds = {w.hwnd for w in current_windows}

        windows_by_app: Dict[str, List] = {}
        for w in current_windows:
            app_type = self.wm.get_app_type(w)
            if app_type not in windows_by_app:
                windows_by_app[app_type] = []
            windows_by_app[app_type].append(w)

        applied = 0
        failed = []
        launched = []

        for window_key, window_data in layout_data.items():
            if 'identifier' not in window_data:
                continue

            app_type = window_data['identifier'].get('app_type', '')

            if app_type in windows_by_app and windows_by_app[app_type]:
                match = windows_by_app[app_type].pop(0)
                # Always restore to normal state before repositioning
                self.wm.restore_window(match.hwnd)
                # Set borderless state if specified
                saved_borderless = window_data.get('is_borderless', False)
                if self.wm.is_borderless(match.hwnd) != saved_borderless:
                    self.wm.set_borderless(match.hwnd, saved_borderless)
                pos = window_data['position']
                if self.wm.move_window(match.hwnd, pos['x'], pos['y'], pos['width'], pos['height']):
                    applied += 1
            else:
                # Try to launch if auto_launch enabled
                if window_data.get('auto_launch') and window_data.get('exe_path'):
                    try:
                        subprocess.Popen([window_data['exe_path']])
                        launched.append(app_type)
                        # Background thread: wait for window to appear then position it
                        pos = window_data['position']
                        saved_borderless = window_data.get('is_borderless', False)
                        t = threading.Thread(
                            target=self._wait_and_position,
                            args=(app_type, pos, saved_borderless, existing_hwnds),
                            daemon=True,
                        )
                        t.start()
                    except Exception:
                        failed.append(f"{app_type} (launch failed)")
                else:
                    failed.append(f"{app_type} window")

        return {
            "success": True,
            "applied": applied,
            "total": len(layout_data),
            "failed": failed,
            "launched": launched
        }

    def _wait_and_position(self, app_type: str, pos: dict, borderless: bool,
                           existing_hwnds: set, timeout: float = 12.0):
        """Poll for a newly launched window by app_type and reposition it."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            time.sleep(0.5)
            for w in self.wm.get_all_windows_with_minimized():
                if self.wm.get_app_type(w) == app_type and w.hwnd not in existing_hwnds:
                    self.wm.restore_window(w.hwnd)
                    if self.wm.is_borderless(w.hwnd) != borderless:
                        self.wm.set_borderless(w.hwnd, borderless)
                    self.wm.move_window(w.hwnd, pos['x'], pos['y'], pos['width'], pos['height'])
                    return
        print(f"[layouts] Timed out waiting for {app_type} window")

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
