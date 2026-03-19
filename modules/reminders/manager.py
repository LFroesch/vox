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
    type: str       # "timer" | "reminder"
    fire_at: float  # unix timestamp
    message: str = ""
    active: bool = True
    fired: bool = False
    created: float = field(default_factory=time.time)
    alerts: dict = field(default_factory=lambda: {"sound": False, "tts": False, "tray": False})
    recur: Optional[dict] = None  # None = one-shot; {"type": "daily"|"weekly"|"interval", ...}
    triggered: bool = False  # recurring only: fired but not yet dismissed


class ReminderManager:
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.sounds_dir = self.data_dir.parent / "sounds"
        self._path = self.data_dir / "reminders.json"
        self._entries: List[ReminderEntry] = []
        self._lock = threading.Lock()
        self.on_fire: Optional[Callable[[ReminderEntry], None]] = None
        self.on_batch_fire: Optional[Callable[[List[ReminderEntry]], None]] = None
        self._load()
        self._started = False
        self._last_tick: float = time.time()

    def start(self):
        """Start the reminder check loop. Call after UI is fully initialized."""
        if not self._started:
            self._started = True
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()
            # Notify about reminders that fired while app was closed
            missed = getattr(self, '_missed', [])
            if missed and self.on_batch_fire:
                self.on_batch_fire(list(missed))
                self._save()
            self._missed = []

    # ── Public API ─────────────────────────────────────────────────────────

    def create_timer(self, label: str, seconds: int, alerts: dict = None, message: str = "") -> ReminderEntry:
        entry = ReminderEntry(
            id=str(uuid.uuid4())[:8],
            label=label,
            type="timer",
            fire_at=time.time() + seconds,
            message=message or label,
            alerts=alerts or dict(_DEFAULT_ALERTS),
        )
        with self._lock:
            self._entries.append(entry)
        self._save()
        return entry

    def create_reminder(self, label: str, time_str: str, message: str = "", alerts: dict = None) -> Optional[ReminderEntry]:
        fire_at = self._parse_time(time_str)
        if fire_at is None:
            return None
        entry = ReminderEntry(
            id=str(uuid.uuid4())[:8],
            label=label,
            type="reminder",
            fire_at=fire_at,
            message=message,
            alerts=alerts or dict(_DEFAULT_ALERTS),
        )
        with self._lock:
            self._entries.append(entry)
        self._save()
        return entry

    def create_at(self, label: str, entry_type: str, fire_at: float, message: str = "", alerts: dict = None) -> ReminderEntry:
        entry = ReminderEntry(
            id=str(uuid.uuid4())[:8],
            label=label,
            type=entry_type,
            fire_at=fire_at,
            message=message or label,
            alerts=alerts or dict(_DEFAULT_ALERTS),
        )
        with self._lock:
            self._entries.append(entry)
        self._save()
        return entry

    def create_recurring(self, label: str, message: str, recur: dict, alerts: dict = None) -> ReminderEntry:
        """Create a recurring reminder. recur dict formats:
          {"type": "daily",    "time": "HH:MM"}
          {"type": "weekly",   "days": [0..6], "time": "HH:MM"}  # 0=Mon, 6=Sun
          {"type": "interval", "seconds": N}
        """
        fire_at = self._next_fire(recur)
        entry = ReminderEntry(
            id=str(uuid.uuid4())[:8],
            label=label,
            type="reminder",
            fire_at=fire_at,
            message=message or label,
            alerts=alerts or dict(_DEFAULT_ALERTS),
            recur=recur,
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

    def snooze(self, entry_id: str, seconds: int):
        with self._lock:
            for e in self._entries:
                if e.id == entry_id:
                    e.fired = False
                    e.fire_at = time.time() + seconds
        self._save()

    def clear_fired(self):
        with self._lock:
            for e in self._entries:
                if e.fired:
                    e.active = False
        self._save()

    def dismiss(self, entry_id: str):
        with self._lock:
            for e in self._entries:
                if e.id == entry_id and e.recur:
                    e.triggered = False
        self._save()

    def dismiss_all_triggered(self):
        with self._lock:
            for e in self._entries:
                if e.recur and e.triggered:
                    e.triggered = False
        self._save()

    def reset_recurring(self, entry_id: str):
        with self._lock:
            for e in self._entries:
                if e.id == entry_id and e.recur:
                    e.fire_at = self._next_fire(e.recur)
        self._save()

    def update_entry(self, entry_id: str, **kwargs):
        with self._lock:
            for e in self._entries:
                if e.id == entry_id:
                    for k, v in kwargs.items():
                        if hasattr(e, k):
                            setattr(e, k, v)
        self._save()

    def get_active(self) -> List[ReminderEntry]:
        with self._lock:
            return [e for e in self._entries if e.active]

    # ── Voice parsing ───────────────────────────────────────────────────────

    @staticmethod
    def parse_voice_command(text: str):
        """Parse voice text into a timer or reminder command.
        Returns ('timer', task, seconds) or ('reminder', task, task, time_str)
        or ('recurring', task, recur_dict) or None.

        Flexible approach: strip filler, extract duration/time from anywhere,
        extract task via multiple patterns, word order doesn't matter.
        """
        lower = text.lower().strip()

        # Normalize "a.m."/"p.m." → "am"/"pm"
        lower = re.sub(r'\ba\s*\.\s*m\s*\.?', 'am', lower)
        lower = re.sub(r'\bp\s*\.\s*m\s*\.?', 'pm', lower)

        # Normalize recurring synonyms so they hit the "every" gate
        lower = re.sub(r'\beveryday\b', 'every day', lower)
        lower = re.sub(r'\bdaily\b', 'every day', lower)

        # Must look like a reminder/timer request
        _TRIGGER = (
            r'\b(?:remind|reminder|timer|alarm|set\s+(?:a\s+)?(?:timer|alarm|reminder)'
            r'|wake|notify|alert|ping|don\'?t\s+(?:let\s+me\s+)?forget'
            r'|tell\s+me|heads?\s+up)\b'
        )
        if not re.search(_TRIGGER, lower):
            return None

        # Strip filler words/phrases that interfere with parsing
        _FILLER = [
            r'^(?:hey\s+)?(?:can\s+you|could\s+you|would\s+you|will\s+you)\s+',
            r'^(?:please|hey|ok|okay|yo)\s+',
            r'\s+(?:please|thanks|thank\s+you)$',
            r'\b(?:like|just|maybe|also|actually|go\s+ahead\s+and|i\s+need\s+you\s+to)\b',
            r'\bfor\s+me\b',
        ]
        for pat in _FILLER:
            lower = re.sub(pat, ' ', lower)
        lower = re.sub(r'\s+', ' ', lower).strip()

        # ── Recurring: "every ..." handled separately ────────────────────────
        if re.search(r'\bevery\b', lower):
            result = _parse_recurring_voice(lower)
            if result:
                return result

        # ── Fuzzy number normalization ───────────────────────────────────────
        FUZZY = [
            (r'\b(?:a\s+)?quarter\s+(?:of\s+an?\s+)?hour\b', '15 minutes'),
            (r'\bhalf\s+an?\s+hour\b', '30 minutes'),
            (r'\ban?\s+hour\s+and\s+a\s+half\b', '90 minutes'),
            (r'\ban?\s+hour\s+and\s+', '1 hour '),
            (r'\ban?\s+hour\b', '1 hour'),
            (r'\ba\s+couple(?:\s+of)?\s+hours?\b', '2 hours'),
            (r'\ba\s+few\s+hours?\b', '3 hours'),
            (r'\ba\s+couple(?:\s+of)?\s+minutes?\b', '2 minutes'),
            (r'\ba\s+few\s+minutes?\b', '5 minutes'),
            (r'\ba\s+minute\b', '1 minute'),
            (r'\ba\s+second\b', '1 second'),
        ]
        for pat, repl in FUZZY:
            lower = re.sub(pat, repl, lower)

        # ── Extract duration anywhere in sentence ────────────────────────────
        unit_map = {'hour': 3600, 'hr': 3600, 'minute': 60, 'min': 60, 'second': 1, 'sec': 1}
        unit_pat = r'(?:hour|hr|minute|min|second|sec)s?'

        duration_secs = 0
        duration_spans = []

        # Compound: "1 hour 30 minutes" / "1 hour and 30 minutes"
        m = re.search(rf'(\d+)[\s-]*(hour|hr)s?\s+(?:and\s+)?(\d+)[\s-]*(minute|min)s?', lower)
        if m:
            duration_secs = int(m.group(1)) * 3600 + int(m.group(3)) * 60
            duration_spans.append((m.start(), m.end()))
        else:
            # Simple: "5 minutes", "5-minute", "30 seconds", etc — find all and sum
            for m in re.finditer(rf'(\d+)[\s-]*({unit_pat})', lower):
                n, raw = int(m.group(1)), m.group(2).rstrip('s')
                duration_secs += n * unit_map.get(raw, 60)
                duration_spans.append((m.start(), m.end()))

        # "in N days/weeks"
        m = re.search(r'\b(\d+)[\s-]+(day|week)s?\b', lower)
        if m and not duration_spans:
            n, unit = int(m.group(1)), m.group(2)
            duration_secs = n * (7 * 86400 if 'week' in unit else 86400)
            duration_spans.append((m.start(), m.end()))

        # ── Extract clock time / date anywhere in sentence ───────────────────
        _DAY_NAMES = r'(?:monday|mon|tuesday|tues|tue|wednesday|wed|thursday|thurs|thu|friday|fri|saturday|sat|sunday|sun)'
        _NAMED_TIMES = r'(?:morning|afternoon|evening|tonight|noon|midnight|night)'
        _MONTH_NAMES = (r'(?:january|jan|february|feb|march|mar|april|apr|may|june|jun|'
                        r'july|jul|august|aug|september|sep|sept|october|oct|november|nov|december|dec)')
        _CLOCK = r'\d{1,2}(?::\d{2})?\s*(?:am|pm)'
        _CLOCK_24 = r'\d{1,2}:\d{2}'

        time_parts = []
        time_spans = []

        # "next wednesday", "on friday", "this monday"
        for m in re.finditer(rf'\b(next\s+|this\s+|on\s+)?({_DAY_NAMES})\b', lower):
            prefix = m.group(1).strip() if m.group(1) else ''
            time_parts.append(f"{prefix} {m.group(2)}".strip())
            time_spans.append((m.start(), m.end()))

        # "tomorrow"
        for m in re.finditer(r'\btomorrow\b', lower):
            time_parts.append('tomorrow')
            time_spans.append((m.start(), m.end()))

        # "morning", "afternoon", etc.
        for m in re.finditer(rf'\b(?:this\s+|in\s+the\s+)?({_NAMED_TIMES})\b', lower):
            time_parts.append(m.group(1))
            time_spans.append((m.start(), m.end()))

        # "March 15th", "on March 15"
        for m in re.finditer(rf'\b(?:on\s+)?({_MONTH_NAMES})\s+(\d{{1,2}})(?:st|nd|rd|th)?\b', lower):
            time_parts.append(f"{m.group(1)} {m.group(2)}")
            time_spans.append((m.start(), m.end()))

        # "the 15th"
        for m in re.finditer(r'\b(?:on\s+)?the\s+(\d{1,2})(?:st|nd|rd|th)\b', lower):
            time_parts.append(f"the {m.group(1)}")
            time_spans.append((m.start(), m.end()))

        # "3/15" or "3-15"
        for m in re.finditer(r'\b(\d{1,2})[/-](\d{1,2})\b', lower):
            time_parts.append(f"{m.group(1)}/{m.group(2)}")
            time_spans.append((m.start(), m.end()))

        # "at 3pm", "at 9:30 am", "for 7am" — clock time with preposition
        for m in re.finditer(rf'\b(?:at|for)\s+({_CLOCK}|{_CLOCK_24}|\d{{1,2}})', lower):
            time_parts.append(m.group(1).strip())
            time_spans.append((m.start(), m.end()))

        # Bare clock time not preceded by preposition: "alarm 7am", "reminder 3pm"
        for m in re.finditer(rf'(?<!\d)({_CLOCK})(?!\d)', lower):
            # Skip if already captured by a preposition match above
            if not any(m.start() >= s and m.end() <= e for s, e in time_spans):
                time_parts.append(m.group(1).strip())
                time_spans.append((m.start(), m.end()))

        # ── Extract task from the text ────────────────────────────────────────
        # "called/named" extracts from original (before time blanking eats words)
        task = ''
        called_m = re.search(r'\b(?:called|named|labeled)\s+(.+?)(?:\s+(?:at|in|on|for|tomorrow)\b|$)', lower)
        if called_m:
            task = called_m.group(1).strip()

        # Blank out all matched time/duration spans
        all_spans = sorted(duration_spans + time_spans, key=lambda s: s[0])
        blanked = lower
        for start, end in reversed(all_spans):
            blanked = blanked[:start] + ' ' + blanked[end:]

        # Also blank "in" when it preceded a duration ("remind me in 10 minutes")
        for start, _ in duration_spans:
            pre = blanked[:start].rstrip()
            if pre.endswith(' in') or pre.endswith(' in '):
                blanked = blanked[:pre.rfind(' in')] + ' ' + blanked[start:]

        if not task:
            # Pattern 1: "to [task]" — "remind me to take out the trash"
            task_m = re.search(r'\bto\s+(.+)', blanked)
            if task_m:
                task = task_m.group(1).strip()
                task = re.sub(r'^remind(?:er)?\s+(?:me\s+)?(?:to\s+)?', '', task).strip()

        # Pattern 2: "about [task]" — "remind me about the meeting"
        if not task:
            task_m = re.search(r'\babout\s+(.+)', blanked)
            if task_m:
                task = task_m.group(1).strip()

        # Pattern 3: "for [task]" — "set a reminder for groceries" (not bare "for")
        if not task:
            task_m = re.search(r'\bfor\s+(.+)', blanked)
            if task_m:
                candidate = task_m.group(1).strip()
                # Skip if it's just leftover connectors or duration remnants
                if not re.match(rf'^(\d+\s*{unit_pat}|$)', candidate):
                    cleaned = re.sub(r'\b(?:a|an|the)\b', '', candidate).strip()
                    if cleaned and len(cleaned) > 1:
                        task = candidate

        # Pattern 4: fallback — strip trigger/connector words, use whatever's left
        if not task:
            leftover = blanked
            leftover = re.sub(
                r'\b(?:set|remind|reminder|timer|alarm|wake|notify|alert|ping|tell|'
                r'me|myself|i|my|up|a|an|the|in|on|at|and|with|that|this|for|'
                r'don\'?t|let|forget|heads?)\b', '', leftover
            )
            leftover = re.sub(r'\s+', ' ', leftover).strip()
            if leftover and len(leftover) > 2:
                task = leftover

        # Clean up leading/trailing connectors from task
        if task:
            task = re.sub(r'^(?:that\s+|to\s+|about\s+|for\s+)', '', task).strip()
            task = re.sub(r'(?:\s+(?:in|on|at|for|and|the))+$', '', task).strip()
            task = re.sub(r'\s+', ' ', task).strip()

        # ── Decide: timer (duration) vs reminder (clock/date) ────────────────
        if duration_secs > 0:
            return ('timer', task or "Timer", duration_secs)

        if time_parts:
            time_str = ' '.join(time_parts)
            return ('reminder', task or 'Reminder', task or 'Reminder', time_str)

        # No time/duration given — default to tomorrow at 9am
        if task:
            return ('reminder', task, task, 'tomorrow morning')

        return None

    # ── Internal ────────────────────────────────────────────────────────────

    def _next_fire(self, recur: dict) -> float:
        """Compute next fire timestamp for a recurrence schedule."""
        now = datetime.now()
        rtype = recur.get("type")

        if rtype == "interval":
            return time.time() + recur["seconds"]

        h, m = map(int, recur["time"].split(":"))

        if rtype == "daily":
            target = now.replace(hour=h, minute=m, second=0, microsecond=0)
            if target <= now:
                target += timedelta(days=1)
            return target.timestamp()

        if rtype == "weekly":
            days = recur["days"]  # 0=Mon, 6=Sun
            for delta in range(1, 8):
                candidate = now + timedelta(days=delta)
                if candidate.weekday() in days:
                    target = candidate.replace(hour=h, minute=m, second=0, microsecond=0)
                    return target.timestamp()

        return time.time() + 86400  # fallback

    def _parse_hm(self, s: str):
        """Parse a time expression to (hour, minute) with no date logic. Returns None if unparseable."""
        s = s.strip().lower()
        named_hm = {
            'noon': (12, 0), 'midday': (12, 0), 'midnight': (0, 0),
            'morning': (9, 0), 'afternoon': (14, 0),
            'evening': (18, 0), 'tonight': (20, 0), 'night': (20, 0),
        }
        if s in named_hm:
            return named_hm[s]
        s = re.sub(r'\s*(am|pm)', r' \1', s).strip().upper()
        for fmt in ["%I:%M %p", "%I:%M%p", "%I %p", "%I%p"]:
            try:
                t = datetime.strptime(s, fmt)
                return (t.hour, t.minute)
            except ValueError:
                continue
        try:
            t = datetime.strptime(s, "%H:%M")
            if t.hour >= 13:
                return (t.hour, t.minute)
        except ValueError:
            pass
        for fmt in ["%I:%M", "%I"]:
            try:
                t = datetime.strptime(s, fmt)
                return ((t.hour % 12) + 12, t.minute)  # PM heuristic for bare numbers
            except ValueError:
                continue
        return None

    def _parse_time(self, time_str: str) -> Optional[float]:
        now = datetime.now()
        s = time_str.strip().lower()

        # Extract "tomorrow" modifier
        add_day = bool(re.search(r'\btomorrow\b', s))
        if add_day:
            s = re.sub(r'\btomorrow\b', '', s).strip()

        # Extract "next" / strip "this"/"on" for day name resolution
        force_next_week = bool(re.search(r'\bnext\b', s))
        s = re.sub(r'\b(?:next|this|on)\b', '', s).strip()
        s = re.sub(r'\s+', ' ', s).strip()

        def _ts(target: datetime) -> float:
            """Advance by 1 day if add_day, or if the time has already passed today."""
            if add_day or target <= now:
                return (target + timedelta(days=1)).timestamp()
            return target.timestamp()

        def _next_weekday(weekday: int) -> datetime:
            days_ahead = weekday - now.weekday()
            if days_ahead <= 0 or force_next_week:
                days_ahead += 7
            return now + timedelta(days=days_ahead)

        # ── Default when only a day/tomorrow modifier with no time ──────────
        if not s:
            target = now.replace(hour=9, minute=0, second=0, microsecond=0)
            return _ts(target)

        # ── Day names: "friday", "friday morning", "friday 3pm" ─────────────
        _DAY_MAP = {
            'monday': 0, 'mon': 0,
            'tuesday': 1, 'tue': 1, 'tues': 1,
            'wednesday': 2, 'wed': 2,
            'thursday': 3, 'thu': 3, 'thurs': 3,
            'friday': 4, 'fri': 4,
            'saturday': 5, 'sat': 5,
            'sunday': 6, 'sun': 6,
        }
        day_pat = r'^(' + '|'.join(_DAY_MAP.keys()) + r')(?:\s+(?:at\s+)?(.+))?$'
        dm = re.match(day_pat, s)
        if dm:
            day_dt = _next_weekday(_DAY_MAP[dm.group(1)])
            hm = self._parse_hm(dm.group(2)) if dm.group(2) else None
            h, mn = hm if hm else (9, 0)
            target = day_dt.replace(hour=h, minute=mn, second=0, microsecond=0)
            return target.timestamp()

        # ── Calendar dates ───────────────────────────────────────────────────
        _MONTH_MAP = {
            'january': 1, 'jan': 1, 'february': 2, 'feb': 2,
            'march': 3, 'mar': 3, 'april': 4, 'apr': 4, 'may': 5,
            'june': 6, 'jun': 6, 'july': 7, 'jul': 7,
            'august': 8, 'aug': 8, 'september': 9, 'sep': 9, 'sept': 9,
            'october': 10, 'oct': 10, 'november': 11, 'nov': 11,
            'december': 12, 'dec': 12,
        }
        _month_names = '|'.join(_MONTH_MAP.keys())

        def _date_ts(month: int, day: int, hm) -> Optional[float]:
            h, mn = hm if hm else (9, 0)
            try:
                target = now.replace(year=now.year, month=month, day=day,
                                     hour=h, minute=mn, second=0, microsecond=0)
                if target <= now:
                    target = target.replace(year=now.year + 1)
                return target.timestamp()
            except ValueError:
                return None

        # "march 15" / "march 15th (morning / at 3pm)"
        dm = re.match(rf'^({_month_names})\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:\s+(?:at\s+)?(.+))?$', s)
        if dm:
            hm = self._parse_hm(dm.group(3)) if dm.group(3) else None
            result = _date_ts(_MONTH_MAP[dm.group(1)], int(dm.group(2)), hm)
            if result:
                return result

        # "the 15th (at 3pm)"
        dm = re.match(r'^the\s+(\d{1,2})(?:st|nd|rd|th)?(?:\s+(?:at\s+)?(.+))?$', s)
        if dm:
            day = int(dm.group(1))
            hm = self._parse_hm(dm.group(2)) if dm.group(2) else None
            h, mn = hm if hm else (9, 0)
            try:
                target = now.replace(day=day, hour=h, minute=mn, second=0, microsecond=0)
                if target <= now:
                    mo = now.month % 12 + 1
                    yr = now.year + (1 if now.month == 12 else 0)
                    target = target.replace(year=yr, month=mo)
                return target.timestamp()
            except ValueError:
                pass

        # "3/15" or "3-15 (at 3pm)"
        dm = re.match(r'^(\d{1,2})[/-](\d{1,2})(?:\s+(?:at\s+)?(.+))?$', s)
        if dm:
            hm = self._parse_hm(dm.group(3)) if dm.group(3) else None
            result = _date_ts(int(dm.group(1)), int(dm.group(2)), hm)
            if result:
                return result

        # ── Named times: noon, morning, afternoon, tonight, etc. ────────────
        named = {
            'noon': (12, 0), 'midday': (12, 0), 'midnight': (0, 0),
            'morning': (9, 0), 'afternoon': (14, 0),
            'evening': (18, 0), 'tonight': (20, 0),
        }
        for name, (h, mn) in named.items():
            if s == name or s == f"the {name}" or s == f"in the {name}":
                target = now.replace(hour=h, minute=mn, second=0, microsecond=0)
                return _ts(target)

        # ── Clock time with explicit AM/PM ───────────────────────────────────
        s = re.sub(r'\s*(am|pm)', r' \1', s).strip().upper()
        for fmt in ["%I:%M %p", "%I:%M%p", "%I %p", "%I%p"]:
            try:
                t = datetime.strptime(s, fmt)
                target = now.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
                return _ts(target)
            except ValueError:
                continue

        # %H:%M — only for unambiguous 24h values (hour >= 13)
        try:
            t = datetime.strptime(s, "%H:%M")
            if t.hour >= 13:
                target = now.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
                return _ts(target)
        except ValueError:
            pass

        # ── Bare number: "3" or "3:30" — try PM first ───────────────────────
        for fmt in ["%I:%M", "%I"]:
            try:
                t = datetime.strptime(s, fmt)
                for h_offset in [12, 0]:
                    h = (t.hour + h_offset) % 24
                    target = now.replace(hour=h, minute=t.minute, second=0, microsecond=0)
                    if target > now:
                        return _ts(target)
                # Both past — PM tomorrow
                target = now.replace(hour=(t.hour + 12) % 24, minute=t.minute,
                                     second=0, microsecond=0) + timedelta(days=1)
                return target.timestamp()
            except ValueError:
                continue

        return None

    def _loop(self):
        while True:
            try:
                time.sleep(0.5)
                now = time.time()
                elapsed = now - self._last_tick
                self._last_tick = now
                was_asleep = elapsed > 10  # machine slept if tick gap >> 0.5s
                fired = []
                with self._lock:
                    for entry in self._entries:
                        if entry.active and not entry.fired and entry.fire_at <= now:
                            if entry.recur:
                                entry.triggered = True
                                entry.fire_at = self._next_fire(entry.recur)
                            else:
                                entry.fired = True
                            fired.append(entry)
                if fired:
                    self._save()
                    if was_asleep and len(fired) > 0 and self.on_batch_fire:
                        self.on_batch_fire(fired)
                    else:
                        for entry in fired:
                            self._fire(entry)
            except Exception:
                pass

    def _fire(self, entry: ReminderEntry):
        try:
            if self.on_fire:
                self.on_fire(entry)
        except Exception:
            pass

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
                    e.setdefault("alerts", dict(_DEFAULT_ALERTS))
                    e.setdefault("recur", None)
                    e.setdefault("fired", False)
                    e.setdefault("triggered", False)
                    entries.append(ReminderEntry(**e))
                result = []
                self._missed: List[ReminderEntry] = []
                for e in entries:
                    if not e.active:
                        continue
                    if e.fired:
                        result.append(e)
                        continue
                    if e.recur and e.fire_at <= now:
                        e.fire_at = self._next_fire(e.recur)
                    if not e.recur and e.fire_at <= now:
                        e.fired = True
                        self._missed.append(e)
                    result.append(e)
                self._entries = result
            except Exception:
                self._entries = []

    def _save(self):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        with self._lock:
            data = [asdict(e) for e in self._entries if e.active]
        self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")


# ── Module-level helpers for recurring voice parsing ─────────────────────────

def _extract_at_time(text: str) -> Optional[str]:
    """Extract 'at TIME' clock string from text, or None."""
    m = re.search(r'\bat\s+(\d+(?::\d+)?(?:\s*(?:am|pm))?)', text, re.IGNORECASE)
    return m.group(1).strip() if m else None


def _parse_recurring_voice(text: str):
    """Parse 'every ...' recurring voice patterns.
    Returns ('recurring', label, recur_dict) or None.
    recur_dict: {"type": "interval", "seconds": N}
              | {"type": "daily"|"weekly", "time_str": "9am", ["days": [...]]}
    """
    _DAY_MAP = {
        'monday': 0, 'mon': 0, 'tuesday': 1, 'tue': 1, 'tues': 1,
        'wednesday': 2, 'wed': 2, 'thursday': 3, 'thu': 3, 'thurs': 3,
        'friday': 4, 'fri': 4, 'saturday': 5, 'sat': 5, 'sunday': 6, 'sun': 6,
    }
    _NAMED_HM = {
        'morning': '09:00', 'afternoon': '14:00', 'evening': '18:00',
        'night': '20:00', 'noon': '12:00', 'midnight': '00:00',
    }
    unit_map = {'hour': 3600, 'hr': 3600, 'minute': 60, 'min': 60, 'second': 1, 'sec': 1}
    unit_pat = r'(?:hour|hr|minute|min|second|sec)s?'

    # Extract "to TASK" label from the end
    task_m = re.search(r'\bto\s+(.+)$', text)
    task = task_m.group(1).strip() if task_m else ""
    work = text[:task_m.start()].strip() if task_m else text

    def _resolve_time(work_text):
        """Get time as HH:MM. Parses 'at TIME' or defaults to 09:00."""
        raw = _extract_at_time(work_text)
        if not raw:
            return "09:00"
        # Parse "9am", "3:30pm", etc. into HH:MM
        for name, hhmm in _NAMED_HM.items():
            if raw.strip().lower() == name:
                return hhmm
        raw_up = re.sub(r'\s*(am|pm)', r' \1', raw).strip().upper()
        from datetime import datetime as _dt
        for fmt in ["%I:%M %p", "%I:%M%p", "%I %p", "%I%p"]:
            try:
                t = _dt.strptime(raw_up, fmt)
                return f"{t.hour:02d}:{t.minute:02d}"
            except ValueError:
                continue
        try:
            t = _dt.strptime(raw_up, "%H:%M")
            return f"{t.hour:02d}:{t.minute:02d}"
        except ValueError:
            pass
        return "09:00"

    # "every N unit(s)" → interval
    m = re.search(rf'\bevery\s+(\d+)[\s-]*({unit_pat})', work)
    if m:
        n, raw = int(m.group(1)), m.group(2).rstrip('s')
        secs = n * unit_map.get(raw, 60)
        return ('recurring', task or f"every {n} {raw}", {"type": "interval", "seconds": secs})

    # "every hour" → interval 3600
    if re.search(r'\bevery\s+(?:an?\s+)?hour\b', work):
        return ('recurring', task or "every hour", {"type": "interval", "seconds": 3600})

    # "every morning/afternoon/..." → daily at named time (no "at" needed)
    for name, hhmm in _NAMED_HM.items():
        if re.search(rf'\bevery\s+(?:the\s+)?{name}\b', work):
            return ('recurring', task or f"every {name}", {"type": "daily", "time": hhmm})

    # "every day at TIME" → daily
    if re.search(r'\bevery\s+day\b', work):
        return ('recurring', task or "daily", {"type": "daily", "time": _resolve_time(work)})

    # "every weekday(s) at TIME" → weekdays
    if re.search(r'\bevery\s+weekdays?\b', work):
        return ('recurring', task or "weekdays", {"type": "weekly", "days": [0, 1, 2, 3, 4], "time": _resolve_time(work)})

    # "every weekend(s) at TIME" → weekends
    if re.search(r'\bevery\s+weekends?\b', work):
        return ('recurring', task or "weekends", {"type": "weekly", "days": [5, 6], "time": _resolve_time(work)})

    # "every Monday (and Wednesday) at TIME" → specific days
    day_hits = re.findall(r'\b(' + '|'.join(_DAY_MAP.keys()) + r')\b', work)
    if day_hits:
        days = sorted(set(_DAY_MAP[d] for d in day_hits))
        label = task or ", ".join(day_hits[:2]) + ("..." if len(day_hits) > 2 else "")
        return ('recurring', label, {"type": "weekly", "days": days, "time": _resolve_time(work)})

    return None
