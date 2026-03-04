import time
import uuid
import json
import threading
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Callable, List

_DEFAULT_ALERTS = {"sound": False, "tts": False, "tray": False}


@dataclass
class ReminderEntry:
    id: str
    label: str
    type: str       # "timer" | "alarm" | "reminder"
    fire_at: float  # unix timestamp
    message: str = ""
    active: bool = True
    created: float = field(default_factory=time.time)
    alerts: dict = field(default_factory=lambda: {"sound": False, "tts": False, "tray": False})


class ReminderManager:
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.sounds_dir = self.data_dir.parent / "sounds"
        self._path = self.data_dir / "reminders.json"
        self._entries: List[ReminderEntry] = []
        self._lock = threading.Lock()
        self.on_fire: Optional[Callable[[ReminderEntry], None]] = None
        self._load()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    # ── Public API ─────────────────────────────────────────────────────────

    def create_timer(self, label: str, seconds: int, alerts: dict = None) -> ReminderEntry:
        entry = ReminderEntry(
            id=str(uuid.uuid4())[:8],
            label=label,
            type="timer",
            fire_at=time.time() + seconds,
            message=f"Timer done: {label}",
            alerts=alerts or dict(_DEFAULT_ALERTS),
        )
        with self._lock:
            self._entries.append(entry)
        self._save()
        return entry

    def create_alarm(self, label: str, time_str: str, alerts: dict = None) -> Optional[ReminderEntry]:
        fire_at = self._parse_time(time_str)
        if fire_at is None:
            return None
        entry = ReminderEntry(
            id=str(uuid.uuid4())[:8],
            label=label,
            type="alarm",
            fire_at=fire_at,
            message=f"Alarm: {label}",
            alerts=alerts or dict(_DEFAULT_ALERTS),
        )
        with self._lock:
            self._entries.append(entry)
        self._save()
        return entry

    def create_reminder(self, label: str, message: str, time_str: str, alerts: dict = None) -> Optional[ReminderEntry]:
        fire_at = self._parse_time(time_str)
        if fire_at is None:
            return None
        entry = ReminderEntry(
            id=str(uuid.uuid4())[:8],
            label=label,
            type="reminder",
            fire_at=fire_at,
            message=message or label,
            alerts=alerts or dict(_DEFAULT_ALERTS),
        )
        with self._lock:
            self._entries.append(entry)
        self._save()
        return entry

    def cancel(self, entry_id: str):
        with self._lock:
            for e in self._entries:
                if e.id == entry_id:
                    e.active = False
        self._save()

    def get_active(self) -> List[ReminderEntry]:
        with self._lock:
            return [e for e in self._entries if e.active]

    # ── Voice parsing ───────────────────────────────────────────────────────

    @staticmethod
    def parse_voice_command(text: str):
        """Parse voice text. Returns (type, args) tuple or None.
        Types: 'timer' -> ('timer', label, seconds)
               'reminder' -> ('reminder', label, message, time_str)
        """
        lower = text.lower().strip()

        unit_map = {'hour': 3600, 'hr': 3600, 'minute': 60, 'min': 60, 'second': 1, 'sec': 1}
        unit_pat = r'(?:hour|hr|minute|min|second|sec)s?'

        def _resolve(n: int, raw: str):
            base = raw.rstrip('s')
            secs = n * unit_map.get(base, 60)
            if 'hour' in base or base == 'hr':
                lbl = f"{n} {'hour' if n == 1 else 'hours'}"
            elif 'min' in base:
                lbl = f"{n} {'minute' if n == 1 else 'minutes'}"
            else:
                lbl = f"{n} {'second' if n == 1 else 'seconds'}"
            return secs, lbl

        # Compound: "N hours M minutes" anywhere in utterance
        m = re.search(rf'(\d+)\s*(hour|hr)s?\s+(?:and\s+)?(\d+)\s*(minute|min)s?', lower)
        if m:
            h, mins = int(m.group(1)), int(m.group(3))
            return ('timer', f"{h}h {mins}m", h * 3600 + mins * 60)

        # "set timer / timer / start timer / start a timer" + optional "for" + N unit
        m = re.search(rf'(?:set\s+|start\s+)?(?:a\s+)?timer\s+(?:for\s+)?(\d+)\s*({unit_pat})', lower)
        if m:
            secs, lbl = _resolve(int(m.group(1)), m.group(2))
            return ('timer', lbl, secs)

        # "N unit timer" / "start N unit timer"
        m = re.search(rf'(?:start\s+)?(?:a\s+)?(\d+)\s*({unit_pat})\s+timer', lower)
        if m:
            secs, lbl = _resolve(int(m.group(1)), m.group(2))
            return ('timer', lbl, secs)

        # "remind me in N unit" → countdown (timer)
        m = re.search(rf'remind(?:er)?\s+(?:me\s+)?in\s+(\d+)\s*({unit_pat})', lower)
        if m:
            secs, lbl = _resolve(int(m.group(1)), m.group(2))
            return ('timer', f"Reminder in {lbl}", secs)

        # "remind me to X at Y" → clock-time reminder
        m = re.search(r'remind(?:er)?\s+(?:me\s+)?(?:to\s+)?(.+?)\s+at\s+(.+)', lower)
        if m:
            task = m.group(1).strip()
            time_str = m.group(2).strip()
            return ('reminder', task, task, time_str)

        return None

    # ── Internal ────────────────────────────────────────────────────────────

    def _parse_time(self, time_str: str) -> Optional[float]:
        now = datetime.now()
        s = time_str.strip().lower()

        # Named times
        named = {
            "noon": (12, 0), "midday": (12, 0),
            "midnight": (0, 0),
            "morning": (9, 0),
            "afternoon": (14, 0),
            "evening": (18, 0), "tonight": (20, 0),
        }
        for name, (h, mn) in named.items():
            if s == name or s == f"the {name}" or s == f"in the {name}":
                target = now.replace(hour=h, minute=mn, second=0, microsecond=0)
                if target <= now:
                    target += timedelta(days=1)
                return target.timestamp()

        # Normalize spacing around AM/PM
        s = re.sub(r'\s*(am|pm)', r' \1', s).strip().upper()

        formats = ["%I:%M %p", "%I:%M%p", "%I %p", "%I%p", "%H:%M"]
        for fmt in formats:
            try:
                t = datetime.strptime(s, fmt)
                target = now.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
                if target <= now:
                    target += timedelta(days=1)
                return target.timestamp()
            except ValueError:
                continue

        # Bare number e.g. "3" or "3:30" — no AM/PM: pick nearest future (check PM then AM)
        for fmt in ["%I:%M", "%I"]:
            try:
                t = datetime.strptime(s, fmt)
                # Try PM first (more common for reminders during daytime)
                for h_offset in [12, 0]:
                    h = (t.hour + h_offset) % 24
                    target = now.replace(hour=h, minute=t.minute, second=0, microsecond=0)
                    if target > now:
                        return target.timestamp()
                # Both past — use PM tomorrow
                target = now.replace(hour=(t.hour + 12) % 24, minute=t.minute,
                                     second=0, microsecond=0) + timedelta(days=1)
                return target.timestamp()
            except ValueError:
                continue

        return None

    def _loop(self):
        while True:
            time.sleep(0.5)
            now = time.time()
            fired = []
            with self._lock:
                for entry in self._entries:
                    if entry.active and entry.fire_at <= now:
                        entry.active = False
                        fired.append(entry)
            if fired:
                self._save()
                for entry in fired:
                    self._fire(entry)

    def _fire(self, entry: ReminderEntry):
        alerts = entry.alerts if isinstance(entry.alerts, dict) else {}
        if alerts.get("sound", False):
            self._play_audio()
        if self.on_fire:
            self.on_fire(entry)

    def _play_audio(self):
        """Play first .mp3 in sounds_dir, or system beep as fallback."""
        try:
            self.sounds_dir.mkdir(parents=True, exist_ok=True)
            mp3s = sorted(self.sounds_dir.glob("*.mp3"))
            if mp3s:
                self._play_mp3(str(mp3s[0]))
                return
        except Exception:
            pass
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        except Exception:
            pass

    def _play_mp3(self, path: str):
        def _do():
            try:
                import ctypes
                winmm = ctypes.windll.winmm
                alias = f"vox_{int(time.time() * 1000) % 99999}"
                winmm.mciSendStringW(f'open "{path}" type mpegvideo alias {alias}', None, 0, None)
                winmm.mciSendStringW(f'play {alias} wait', None, 0, None)
                winmm.mciSendStringW(f'close {alias}', None, 0, None)
            except Exception:
                pass
        threading.Thread(target=_do, daemon=True).start()

    def _load(self):
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text(encoding="utf-8"))
                now = time.time()
                entries = []
                for e in data:
                    # backward compat: fill missing alerts field
                    e.setdefault("alerts", dict(_DEFAULT_ALERTS))
                    entries.append(ReminderEntry(**e))
                self._entries = [e for e in entries if e.active and e.fire_at > now]
            except Exception:
                self._entries = []

    def _save(self):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        with self._lock:
            data = [asdict(e) for e in self._entries if e.active]
        self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")
