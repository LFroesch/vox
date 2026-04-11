## DevLog

### 2026-04-10: Reminder false-positives, fullscreen monitor, launch-to-front

- **Reminder false-positives**: `_handle_reminder_voice` was called before wake word check and immediately creates entries as a side effect. Restructured `_handle_voice_result` to check wake word and notes first, only call reminder parsing in the else branch. Also tightened `_TRIGGER` regex: `|wake|` → `|wake\s+(?:me|up)|` so "wake word" no longer triggers reminder parsing. Additionally, `_TRIGGER` now only matches in the first 6 words — prevents meta-statements like "everything is being treated as a reminder" from creating spurious reminders. (`app.py`, `manager.py`)
- **PIP windows filtered**: Added `HIDDEN_TITLES` set to `WindowManager` and `_is_hidden_window()` helper. "Picture in Picture" (Chrome/Brave/Firefox/Edge PIP overlay) is now excluded from all window listings. (`manager.py`)
- **Fullscreen on wrong monitor**: Non-browser maximized windows were calling `maximize_window` without first moving to the target monitor. Extended `_prime_browser_monitor` call to all app types (not just browsers) before maximizing. (`layouts.py`)
- **Launches now come to front**: Added `AllowSetForegroundWindow(ASFW_ANY)` call before every launch so the new process can steal focus from Vox. (`launcher.py`)

### 2026-04-09: Widget/voice/settings polish

- **Widget always-on-top**: Added 15s `QTimer` that calls `raise_()` when visible — fixes widget getting buried after sleep/wake or busy sessions. (`widget.py`)
- **Wake word indicator**: Replaced 👂 ear emoji with a small green dot `●` — less intrusive, clearer as a status indicator. (`widget.py`)
- **Wake word hint**: Added hint text in settings — "listens always-on — may trigger on similar sounds". (`settings.py`)
- **Wake word voice toggle**: "wake word on/off", "enable/disable wake word", "turn on/off wake word" commands added — toggles and persists to config. (`app.py`)
- **Voice reminder TTS**: More natural confirmations — "Timer set for 5 minutes — laundry", "Got it, reminding you to call mom at 3pm", "Recurring reminder set to standup, every day". (`app.py`)
- **"in N days" bug**: "remind me in 28 days to X" was creating a 28-day countdown timer instead of a date-based reminder. Fixed: days/weeks now go to `time_parts` → `_parse_time("in 28 days")` → reminder at 9am that day. (`manager.py`)
- **Pattern 4 over-stripping**: Fallback label extraction was stripping content words like `the`, `my`, `i`, `don't`, `in`, `on`, `at`, `and`, `for`, `let`, `forget` — all of which can appear in real task labels. Narrowed strip list to unambiguous command words only (`remind`, `timer`, `alarm`, `alert`, `ping`, `tell`, `me`, `myself`). "remind me I left the stove on" → `I left the stove on` instead of `left stove on`. (`manager.py`)
- **Widget reminder count**: Header now shows total active reminder count, not just fired/triggered. (`widget.py`)
- **Widget small mode**: Single-column sections (layouts/launchers/workflows) now fill full width in Small mode. (`widget.py`)

### 2026-04-08: Focus-or-launch for app launchers

- **Focus existing window instead of re-launching**: `_launch_app` now checks for an existing window of that process before spawning. If `item.args` contains a project path, it extracts the last folder name and requires it to appear in the window title — so "active - cursor" and "vox - cursor" are treated as distinct windows. No match = launches new instance as before. Wired up by injecting `window_manager` into `Launcher` from `app.py`. (`launcher/launcher.py`, `ui/app.py`)

### 2026-04-08: Bug fixes — browser layout race, widget size, reminders, clipboard

- **Brave/browser layout race**: Browsers drift back after restore before DWM settles. Now fires a deferred second `move_window` call 350ms later for brave/chrome/firefox/edge. (`layouts.py`)
- **Layout page auto-refresh**: Windows list now auto-refreshes every 10s while the page is visible — no more manual Refresh needed. (`pages/windows.py`)
- **Widget size — Small/Large only**: Removed Medium. Large = 250px wide, MAX_H = 580 (taller). Small keeps 175px and now uses a single column for action lists instead of 2. Config default changed to Large. (`styles.py`, `widget.py`, `config.py`, `pages/settings.py`)
- **Widget reminders — (x) button**: Fired non-recurring reminders now show a dismiss ✓ button instead of "Done" text. Dismissing a non-recurring fired entry calls `cancel()` (removes it) instead of `dismiss()` (which only worked for recurring). (`widget.py`, `app.py`)
- **Widget reminders repaint**: `_clear()` now immediately hides and detaches old widgets (`hide()`+`setParent(None)`) before `deleteLater()`, fixing stale display until recollapse. (`widget.py`)
- **Clipboard save bug**: `_save_history` was mutating `self.history` in-place while truncating to the 5MB limit, causing in-memory data loss. Now works on a copy. (`clipboard/clipboard.py`)

### 2026-03-20: Reminder TTS confirmation, expired edit fix, README WSL docs

- **Reminder confirmation TTS**: Voice-set reminders now speak a full confirmation like "Setting reminder for 3pm tomorrow to: take out the trash". New "Reminder Confirmation" toggle in Settings (next to Voice Response) controls this — OFF = no TTS for reminder confirmations.
- **Expired reminder edit bug**: Editing a fired reminder no longer immediately replays it. Only resets `fired=False` when new fire_at is in the future.
- **Time parsing edge case**: "12:00 noon", "noon 12:00" etc. no longer fail — named times (noon, morning...) are stripped and used as fallback when combined with a clock time.
- **README WSL distro**: Added section explaining what the WSL Distro setting does and when to use it.
- Files touched: `ui/app.py`, `ui/pages/settings.py`, `ui/pages/reminders.py`, `modules/reminders/manager.py`, `README.md`

### 2026-03-20: Config open crash fix, sidebar width, demo data

- **Config file/folder open crash**: `subprocess.Popen(["cursor", path])` fails on Windows because `cursor` is a `.cmd` shim. Fixed with `shell=True`. Added try/except fallback. Consolidated into `_open_path()` helper.
- **Sidebar reminder badge clipping**: Widened sidebar 150→166px so "Reminders (N)" doesn't truncate. Added tooltip for badge count.
- **Demo data**: Created `demo/` directory with seed config, reminders, workflows, layouts, clipboard history, notes, and voice log for screenshots.
- Files touched: `ui/pages/settings.py`, `ui/app.py`, `demo/` (new)

### 2026-03-19: Sidebar + button truncation fixes, recurring reminder UX

- **Sidebar selected text clipping**: Added `padding-left: 11px` to selected item so border (3px) + padding = 14px matches unselected padding. Fixes "Reminders (8)" showing as "Remiders ...".
- **Quick button widths**: Bumped `+1d` and `+1h` buttons from 40→46px to prevent text cutoff.
- **Recurring "Next" label**: "Next Today 9:00 AM" → "Next: today 9:00 AM". Lowercase day after prefix, colon separator for readability.
- **Interval input widths**: Recurring interval fields (h/m/s) bumped 48→56px so placeholders like "30m" aren't clipped. Applied to both new-reminder form and edit dialog.
- Files touched: `ui/styles.py`, `ui/pages/reminders.py`

### 2026-03-19: Replace QDateEdit/QTimeEdit with plain text inputs

- **Date/time pickers**: Replaced Qt's section-based QDateEdit/QTimeEdit with custom `_DateInput` and `_TimeInput` (QLineEdit-based). Select-all + retype now works.
- **Date input**: Parses `3/25`, `Mar 25`, `3/25/2026`, `2026-03-25`, etc. Calendar popup button preserved.
- **Time input**: Parses `3pm`, `3:30pm`, `15:30`, `330pm`. Reverts to last valid value on bad input.
- Applied to both new-reminder form and edit dialog.
- Files touched: `ui/pages/reminders.py`

### 2026-03-18: Missed reminders batch notification

- **On load**: Past-due non-recurring reminders now marked as fired instead of silently dropped. Batch notification on startup.
- **On wake**: Sleep detection (tick gap > 10s) batches any reminders that fired during sleep into a single tray notification instead of individual popups.
- Files touched: `modules/reminders/manager.py`, `ui/app.py`

### 2026-03-18: Reminders UI polish

- **Triggered recurring rows**: 🔁 emoji instead of type badge, ✅ confirm + 🗑️ delete buttons replace empty spacer
- **Edit dialog buttons**: Manual Cancel/Save (72x32) replacing QDialogButtonBox, accent on Save
- **Quick buttons**: +1h button added to date quick btns, all styled as pills
- Files touched: `ui/pages/reminders.py`

### 2026-03-17: Fix boot-time race conditions

- **Workflow layout timing**: Poll for expected window count instead of fixed sleep — apps on cold boot take longer to open. Still respects `layout_delay` as minimum wait.
- **Widget position on boot**: Added delayed re-apply (500ms `QTimer.singleShot`) on first show so WM/taskbar can settle before positioning.
- **Notification click**: Made tray icon persistent (created at startup, not destroyed on restore) so `messageClicked` signal is always wired. Previously, non-tray notifications used a PowerShell balloon with no click handler.
- Files touched: `modules/workflows/workflow.py`, `ui/widget.py`, `ui/app.py`

### 2026-03-17: Fix F9 hotkey phantom key issue

- Added `suppress=True, trigger_on_release=True` to `keyboard.add_hotkey()` — fixes scan code collision where F9 (0x43) was misread as `1+F9` due to numpad overlap.
- Files touched: `core/hotkeys.py`

### 2026-03-17: Widget position fix + layout maximize shift fix

- **Widget position**: Added `showEvent`/`hideEvent` overrides to re-apply and save position — fixes WM nudging frameless Tool windows on show/hide cycles.
- **Layout maximize shift**: `restore_window` now only called on minimized windows — avoids the SW_RESTORE→SW_MAXIMIZE roundtrip that shifted maximized windows by a few pixels.
- Files touched: `ui/widget.py`, `modules/windows/layouts.py`

### 2026-03-17: Pre-launch docs & NLP review

- Help page: voice.py → help.py. Updated matching priority banner to 5 steps (notes/reminders NLP parsed first). Added "no time = tomorrow 9am" to reminders section + features blurb. Timer examples now show fuzzy durations.
- README: pages list Voice → Help, split Timers into Reminders + Timers rows with default behavior.
- agent_spec.md: voice.py → help.py references.
- Files touched: `ui/pages/help.py`, `README.md`, `agent_spec.md`

### 2026-03-16: Launcher refs, reminders UX, widget polish

- **Launcher→Workflow live refs**: `WorkflowStep.launcher_ref` links steps to launchers by name. Live lookup on execute. Rename/delete propagation. Picker dialog grouped by type with search/filter.
- **Reminders UX**: Expandable rows for truncated labels. Timer quick presets. Empty sections hidden. Sidebar badge for fired count.
- **Launchers page refactor**: Entries added directly to list layout, simplified filter/collapse.
- **restore_window simplified**: Single `SW_RESTORE` call.
- **Home page spacing**: Tighter Quick Actions margins and grid spacing.

### 2026-03-16: Widget position saving, layout load fix

### 2026-03-13: Workflows feature + layout fixes

- **Workflows**: New `modules/workflows/` — batch-launch with optional linked layout. Voice commands, favorites, Windows page tab.
- **Auto-launch removed from layouts**: Pure positioning now. Workflows handle app launching.
- **Multi-window layout matching**: Smart title/process scoring instead of FIFO.
- **Launcher args**: Added UI fields + fixed space-in-path bug.
- **Workflow "From Launcher"**: Import existing launcher items as steps.

### 2026-03-05: Voice improvements, reminder overhaul, recurring

- **Voice recognition alternatives**: Multiple transcription candidates, first match wins.
- **Phonetic fuzzy matching**: SequenceMatcher ≥0.8 fallback.
- **Voice search**: NLP prefix detection → Google search.
- **Reminder UX overhaul**: Fired persistence, snooze/dismiss, timer urgency colors, calendar/time pickers.
- **Recurring reminders**: daily/weekly/interval schedules, voice parsing, dedicated UI section.
- **Reminder NLP rewrite**: Fuzzy numbers, day names, calendar dates, named times.
- **Widget reminders**: Countdown display, urgency colors, header indicator.

### 2026-03-04: WSL shell fix, settings polish, fuzzy matching

- WSL launchers use user's default shell. Configurable editor. Settings dropdown z-order fix.
- Voice fuzzy matching with token overlap scoring.

### 2026-03-03: UI polish pass

- Voice page table, launcher alignment, window page buttons, widget fixes, browse button icon.

### 2026-03-02: PyQt6 migration

- Full rewrite from CustomTkinter to PyQt6. Monolith split into 8 files. Signal/slot pattern. QSystemTrayIcon. QPainter layout preview.

### 2026-02-27: Reminders module + Vosk removal

- New `modules/reminders/` with timers, alarms, voice NLP. Sound via winmm.dll. Tray notifications.
- Vosk removed, Google-only STT.

### 2026-02-26: Windows tab rework + favorites

- Dropdown selector + visual canvas preview. Accent-color favorite icons.

### 2026-02-24: Widget overflow + font consistency

- Scrollable widget, capped height. Cached `_font()` helper.

### 2026-02-11: Favorites system + clipboard sub-tabs

- Star/heart favorites pinned to Quick Actions. Clipboard History/Snippets as sub-tabs.

### 2026-02-10: UI facelift + WSL fixes + performance

- Shadcn dark palette. Icon buttons. Smart refresh. WSL terminal fixes. Command chaining.

### 2026-02-09: Ship-ready cleanup + voice flow

- Dead code removal. Siri-like voice responses. Windows tab grouped sections. Notes pad.

### 2026-01-25: Widget quick actions

### 2026-01-20: Stopwatch, delete confirmations, full launcher edit

### 2026-01-18: TTS consolidation + widget status

### 2026-01-17: Folder launch, layout restore, TTS fixes, launcher new_tab

### 2026-01-16: Initial UI, terminal commands, clipboard, layouts

- Multiple UI overhauls. Voice tab. Borderless auto-detect. Terminal launcher type. Snippets.

### 2026-01-15: Project created

- Combined window_manager + voice-note. Modular architecture. Python + CustomTkinter.
