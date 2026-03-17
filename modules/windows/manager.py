import win32gui
import win32con
import win32api
import win32process
import psutil
import re
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

@dataclass
class WindowInfo:
    """Information about a window"""
    hwnd: int
    title: str
    class_name: str
    process_name: str
    exe_path: str
    pid: int
    x: int
    y: int
    width: int
    height: int
    is_borderless: bool = False
    is_maximized: bool = False

    @property
    def rect(self) -> Tuple[int, int, int, int]:
        return (self.x, self.y, self.x + self.width, self.y + self.height)


class WindowManager:
    """Manages windows - enumeration, positioning, and smart matching"""

    # Background/system processes to hide from window list
    HIDDEN_PROCESSES = {
        'systemsettings.exe', 'applicationframehost.exe', 'textinputhost.exe',
        'shellexperiencehost.exe', 'searchhost.exe', 'startmenuexperiencehost.exe',
        'lockapp.exe', 'widgetservice.exe', 'widgets.exe', 'gamebar.exe',
        'gamebarpresencewriter.exe', 'runtimebroker.exe', 'dwm.exe',
    }

    # App type identifiers for smart matching
    APP_IDENTIFIERS = {
        'brave': ['brave', 'brave-browser'],
        'chrome': ['chrome', 'google chrome'],
        'firefox': ['firefox', 'mozilla'],
        'code': ['visual studio code', 'code', 'vscode'],
        'notepad': ['notepad'],
        'notepad++': ['notepad++', 'npp'],
        'explorer': ['file explorer', 'windows explorer'],
        'cmd': ['command prompt', 'cmd'],
        'powershell': ['powershell'],
        'terminal': ['terminal', 'windows terminal'],
        'discord': ['discord'],
        'spotify': ['spotify'],
        'steam': ['steam'],
        'obs': ['obs studio', 'obs'],
        'slack': ['slack'],
        'teams': ['microsoft teams', 'teams'],
    }

    APP_DISPLAY_NAMES = {
        'brave': 'Brave Browser',
        'chrome': 'Google Chrome',
        'firefox': 'Firefox',
        'code': 'VS Code',
        'notepad': 'Notepad',
        'explorer': 'File Explorer',
        'cmd': 'Command Prompt',
        'powershell': 'PowerShell',
        'terminal': 'Terminal',
        'discord': 'Discord',
        'spotify': 'Spotify',
        'steam': 'Steam',
        'obs': 'OBS Studio',
        'slack': 'Slack',
        'teams': 'Microsoft Teams',
    }

    def __init__(self):
        self.screen_width = win32api.GetSystemMetrics(0)
        self.screen_height = win32api.GetSystemMetrics(1)

    def get_all_windows(self) -> List[WindowInfo]:
        """Get all visible windows"""
        windows = []

        def callback(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                info = self._get_window_info(hwnd)
                if info and info.title and info.title != "Program Manager":
                    if info.process_name.lower() not in self.HIDDEN_PROCESSES:
                        windows.append(info)
            return True

        win32gui.EnumWindows(callback, None)
        return windows

    def get_all_windows_with_minimized(self) -> List[WindowInfo]:
        """Get all windows including minimized ones"""
        windows = []

        def callback(hwnd, _):
            if win32gui.IsWindowVisible(hwnd) or win32gui.IsIconic(hwnd):
                info = self._get_window_info(hwnd)
                if info and info.title and info.title != "Program Manager":
                    if info.process_name.lower() not in self.HIDDEN_PROCESSES:
                        windows.append(info)
            return True

        win32gui.EnumWindows(callback, None)
        return windows

    def is_minimized(self, hwnd: int) -> bool:
        """Check if window is minimized"""
        try:
            return win32gui.IsIconic(hwnd)
        except:
            return False

    def _get_window_info(self, hwnd: int) -> Optional[WindowInfo]:
        """Get detailed info about a window"""
        try:
            title = win32gui.GetWindowText(hwnd)
            class_name = win32gui.GetClassName(hwnd)

            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            try:
                process = psutil.Process(pid)
                process_name = process.name()
                exe_path = process.exe()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                process_name = "Unknown"
                exe_path = ""

            rect = win32gui.GetWindowRect(hwnd)

            style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
            is_borderless = not (style & win32con.WS_CAPTION)
            try:
                is_maximized = bool(win32gui.IsZoomed(hwnd))
            except Exception:
                is_maximized = False

            return WindowInfo(
                hwnd=hwnd,
                title=title,
                class_name=class_name,
                process_name=process_name,
                exe_path=exe_path,
                pid=pid,
                x=rect[0],
                y=rect[1],
                width=rect[2] - rect[0],
                height=rect[3] - rect[1],
                is_borderless=is_borderless,
                is_maximized=is_maximized
            )
        except Exception:
            return None

    def get_app_type(self, window: WindowInfo) -> str:
        """Identify the application type for a window"""
        process_base = window.process_name.lower().replace('.exe', '')

        for app_key, keywords in self.APP_IDENTIFIERS.items():
            if any(kw in process_base for kw in keywords):
                return app_key
            if any(kw in window.title.lower() for kw in keywords):
                return app_key

        return process_base

    def get_app_display_name(self, app_type: str) -> str:
        """Get display name for an app type"""
        return self.APP_DISPLAY_NAMES.get(app_type, app_type.title())

    def group_by_app(self, windows: List[WindowInfo]) -> Dict[str, List[WindowInfo]]:
        """Group windows by application type"""
        groups: Dict[str, List[WindowInfo]] = {}
        for window in windows:
            app_type = self.get_app_type(window)
            if app_type not in groups:
                groups[app_type] = []
            groups[app_type].append(window)
        return groups

    def move_window(self, hwnd: int, x: int, y: int, width: int, height: int) -> bool:
        """Move and resize a window"""
        try:
            win32gui.SetWindowPos(hwnd, win32con.HWND_TOP, x, y, width, height, 0)
            return True
        except Exception as e:
            print(f"Failed to move window: {e}")
            return False

    def minimize_window(self, hwnd: int) -> bool:
        """Minimize a window"""
        try:
            win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
            return True
        except:
            return False

    def maximize_window(self, hwnd: int) -> bool:
        """Maximize a window"""
        try:
            win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
            return True
        except:
            return False

    def restore_window(self, hwnd: int) -> bool:
        """Restore a window from minimized or maximized state"""
        try:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            return True
        except:
            return False

    def is_borderless(self, hwnd: int) -> bool:
        """Check if window is borderless (no caption/frame)"""
        try:
            style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
            return not (style & win32con.WS_CAPTION)
        except:
            return False

    def set_borderless(self, hwnd: int, borderless: bool) -> bool:
        """Set window borderless state"""
        try:
            style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
            if borderless:
                new_style = (style & ~(win32con.WS_CAPTION | win32con.WS_THICKFRAME)) | win32con.WS_POPUP
            else:
                new_style = (style | win32con.WS_CAPTION | win32con.WS_THICKFRAME) & ~win32con.WS_POPUP
            win32gui.SetWindowLong(hwnd, win32con.GWL_STYLE, new_style)
            win32gui.SetWindowPos(hwnd, None, 0, 0, 0, 0,
                win32con.SWP_FRAMECHANGED | win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOZORDER)
            return True
        except Exception as e:
            print(f"Failed to set borderless: {e}")
            return False

    def apply_preset(self, hwnd: int, preset: str) -> bool:
        """Apply a position preset to a window"""
        presets = {
            "left_half": (0, 0, self.screen_width // 2, self.screen_height),
            "right_half": (self.screen_width // 2, 0, self.screen_width // 2, self.screen_height),
            "top_half": (0, 0, self.screen_width, self.screen_height // 2),
            "bottom_half": (0, self.screen_height // 2, self.screen_width, self.screen_height // 2),
            "top_left": (0, 0, self.screen_width // 2, self.screen_height // 2),
            "top_right": (self.screen_width // 2, 0, self.screen_width // 2, self.screen_height // 2),
            "bottom_left": (0, self.screen_height // 2, self.screen_width // 2, self.screen_height // 2),
            "bottom_right": (self.screen_width // 2, self.screen_height // 2,
                           self.screen_width // 2, self.screen_height // 2),
            "center": (self.screen_width // 4, self.screen_height // 4,
                      self.screen_width // 2, self.screen_height // 2),
            "maximize": (0, 0, self.screen_width, self.screen_height),
        }

        if preset == "minimize":
            return self.minimize_window(hwnd)
        elif preset == "restore":
            return self.restore_window(hwnd)
        elif preset in presets:
            x, y, w, h = presets[preset]
            return self.move_window(hwnd, x, y, w, h)
        return False

    def create_smart_identifier(self, window: WindowInfo) -> Dict[str, Any]:
        """Create identifier for smart window matching"""
        app_type = self.get_app_type(window)

        # Clean title for matching
        clean_title = window.title
        clean_title = re.sub(r' - (Google Chrome|Mozilla Firefox|Brave|Microsoft Edge)$', '', clean_title)
        clean_title = re.sub(r' - Visual Studio Code$', '', clean_title)

        return {
            'app_type': app_type,
            'process_name': window.process_name,
            'class_name': window.class_name,
            'title_keywords': re.findall(r'\b\w+\b', clean_title.lower())[:5],
            'clean_title': clean_title,
            'original_title': window.title,
            'exe_path': window.exe_path,
            'position_x': window.x,
            'position_y': window.y
        }

    def match_window(self, identifier: Dict, windows: List[WindowInfo], threshold: int = 40) -> Tuple[Optional[WindowInfo], int]:
        """Find best matching window using smart matching"""
        best_match = None
        best_score = 0

        for window in windows:
            score = 0
            current_id = self.create_smart_identifier(window)

            # Process name match (high priority)
            if identifier.get('process_name') == window.process_name:
                score += 60

            # App type match
            if identifier.get('app_type') == current_id['app_type']:
                score += 50

            # Class name match
            if identifier.get('class_name') == window.class_name:
                score += 40

            # Clean title match
            if identifier.get('clean_title') and current_id.get('clean_title'):
                if identifier['clean_title'].lower() == current_id['clean_title'].lower():
                    score += 45
                elif identifier['clean_title'].lower() in current_id['clean_title'].lower():
                    score += 25

            # Keyword matching
            if identifier.get('title_keywords') and current_id.get('title_keywords'):
                matches = set(identifier['title_keywords']) & set(current_id['title_keywords'])
                score += len(matches) * 8

            # Exact title match bonus
            if identifier.get('original_title') == window.title:
                score += 100

            if score > best_score:
                best_score = score
                best_match = window

        if best_score >= threshold:
            return best_match, best_score
        return None, 0
