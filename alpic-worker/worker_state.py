"""
Worker State - Local state ledger for deduplication and running lock.
Stores state in a single JSON file.
"""

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional


class WorkerState:
    """Thread-safe local state for worker deduplication."""

    def __init__(self, state_file: str | Path):
        self.state_file = Path(state_file)
        self._lock = threading.Lock()
        self._ensure_state_file()

    def _ensure_state_file(self):
        """Create state file with defaults if it doesn't exist."""
        if not self.state_file.exists():
            self._write_state({
                "last_seen_task_id": None,
                "last_completed_task_id": None,
                "current_running_task_id": None,
                "current_status": "idle",
                "updated_at": datetime.utcnow().isoformat() + "Z",
            })

    def _read_state(self) -> dict:
        """Read state from file."""
        with open(self.state_file, encoding="utf-8") as f:
            return json.load(f)

    def _write_state(self, state: dict):
        """Write state to file."""
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)

    def get_state(self) -> dict:
        """Get current state snapshot."""
        with self._lock:
            return self._read_state()

    def is_idle(self) -> bool:
        """Check if worker is currently idle (not running a task)."""
        with self._lock:
            state = self._read_state()
            return state["current_running_task_id"] is None

    def is_task_running(self, task_id: str) -> bool:
        """Check if a specific task is currently running."""
        with self._lock:
            state = self._read_state()
            return state["current_running_task_id"] == task_id

    def has_completed(self, task_id: str) -> bool:
        """Check if a task has already been completed."""
        with self._lock:
            state = self._read_state()
            return state["last_completed_task_id"] == task_id

    def start_task(self, task_id: str) -> bool:
        """
        Attempt to start a task. Returns True if successful (worker was idle).
        Sets current_running_task_id and current_status.
        """
        with self._lock:
            state = self._read_state()
            if state["current_running_task_id"] is not None:
                # Already running a task
                return False

            state["current_running_task_id"] = task_id
            state["current_status"] = "running"
            state["last_seen_task_id"] = task_id
            state["updated_at"] = datetime.utcnow().isoformat() + "Z"
            self._write_state(state)
            return True

    def complete_task(self, task_id: str):
        """Mark a task as completed. Only completes if it's the current running task."""
        with self._lock:
            state = self._read_state()
            if state["current_running_task_id"] != task_id:
                return False

            state["last_completed_task_id"] = task_id
            state["current_running_task_id"] = None
            state["current_status"] = "idle"
            state["updated_at"] = datetime.utcnow().isoformat() + "Z"
            self._write_state(state)
            return True

    def fail_task(self, task_id: str):
        """Mark a task as failed. Similar to complete_task."""
        with self._lock:
            state = self._read_state()
            if state["current_running_task_id"] != task_id:
                return False

            state["last_completed_task_id"] = task_id
            state["current_running_task_id"] = None
            state["current_status"] = "idle"
            state["updated_at"] = datetime.utcnow().isoformat() + "Z"
            self._write_state(state)
            return True

    def clear_running(self):
        """Force clear running state (for recovery after crash)."""
        with self._lock:
            state = self._read_state()
            state["current_running_task_id"] = None
            state["current_status"] = "idle"
            state["updated_at"] = datetime.utcnow().isoformat() + "Z"
            self._write_state(state)
