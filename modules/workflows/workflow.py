"""Workflow system — batch launching with optional layout linking."""

import json
import threading
import time
from dataclasses import dataclass, asdict, field
from typing import List, Optional, Dict, Any, Callable
from core.config import get_config
from modules.launcher.launcher import LaunchItem


@dataclass
class WorkflowStep:
    """A single step in a workflow."""
    name: str
    item_type: str  # "app", "terminal", "url", "folder", "command", "script"
    path: str
    args: str = ""
    terminal_type: Optional[str] = None
    new_tab: bool = False
    launcher_ref: Optional[str] = None  # linked launcher name (live lookup at execution)

    def to_launch_item(self) -> LaunchItem:
        return LaunchItem(
            name=self.name,
            path=self.path,
            item_type=self.item_type,
            args=self.args,
            terminal_type=self.terminal_type,
            new_tab=self.new_tab,
        )


@dataclass
class Workflow:
    """A named workflow with steps and optional layout linking."""
    name: str
    steps: List[WorkflowStep] = field(default_factory=list)
    voice_phrase: str = ""
    linked_layout: str = ""
    layout_delay: int = 5


class WorkflowManager:
    """Manages workflow saving, loading, and execution."""

    def __init__(self, launcher, layout_manager):
        self.launcher = launcher
        self.layout_manager = layout_manager
        self.config = get_config()
        self._file = self.config.get_data_path("workflows.json")
        self.workflows: Dict[str, Workflow] = {}
        self._load()

    def _load(self):
        if not self._file.exists():
            return
        try:
            with open(self._file, 'r') as f:
                data = json.load(f)
            for name, wd in data.items():
                steps = [WorkflowStep(**s) for s in wd.get("steps", [])]
                self.workflows[name] = Workflow(
                    name=name,
                    steps=steps,
                    voice_phrase=wd.get("voice_phrase", ""),
                    linked_layout=wd.get("linked_layout", ""),
                    layout_delay=wd.get("layout_delay", 5),
                )
        except Exception as e:
            print(f"Error loading workflows: {e}")

    def _save(self):
        data = {}
        for name, wf in self.workflows.items():
            data[name] = {
                "voice_phrase": wf.voice_phrase,
                "linked_layout": wf.linked_layout,
                "layout_delay": wf.layout_delay,
                "steps": [asdict(s) for s in wf.steps],
            }
        try:
            with open(self._file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving workflows: {e}")

    def get_names(self) -> List[str]:
        return list(self.workflows.keys())

    def get(self, name: str) -> Optional[Workflow]:
        return self.workflows.get(name)

    def save_workflow(self, workflow: Workflow):
        self.workflows[workflow.name] = workflow
        self._save()

    def delete_workflow(self, name: str) -> bool:
        if name in self.workflows:
            del self.workflows[name]
            self._save()
            return True
        return False

    def rename_workflow(self, old_name: str, new_name: str) -> bool:
        if old_name not in self.workflows or new_name in self.workflows:
            return False
        wf = self.workflows.pop(old_name)
        wf.name = new_name
        self.workflows[new_name] = wf
        self._save()
        return True

    def update_launcher_ref(self, old_name: str, new_name: str):
        """Update all workflow steps that reference a renamed launcher."""
        changed = False
        for wf in self.workflows.values():
            for step in wf.steps:
                if step.launcher_ref == old_name:
                    step.launcher_ref = new_name
                    changed = True
        if changed:
            self._save()

    def clear_launcher_ref(self, launcher_name: str):
        """Clear refs to a deleted launcher (steps keep their fallback data)."""
        changed = False
        for wf in self.workflows.values():
            for step in wf.steps:
                if step.launcher_ref == launcher_name:
                    step.launcher_ref = None
                    changed = True
        if changed:
            self._save()

    def execute(self, name: str, on_complete: Optional[Callable] = None):
        """Execute a workflow in a background thread."""
        wf = self.workflows.get(name)
        if not wf:
            return

        def _run():
            for step in wf.steps:
                # Live lookup: use current launcher data if linked
                if step.launcher_ref:
                    live = self.launcher.get_item(step.launcher_ref)
                    if live:
                        self.launcher.launch(live)
                        time.sleep(0.3)
                        continue
                # Fallback to stored step data
                item = step.to_launch_item()
                self.launcher.launch(item)
                time.sleep(0.3)

            if wf.linked_layout and wf.linked_layout in self.layout_manager.layouts:
                time.sleep(wf.layout_delay)
                self.layout_manager.load_layout(wf.linked_layout)

            if on_complete:
                on_complete(name)

        threading.Thread(target=_run, daemon=True).start()
