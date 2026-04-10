"""
Task Store - Simple file-based task storage for Alpic Task Bridge V1
"""

import json
import os
import uuid
from datetime import datetime
from pathlib import Path

TASK_STATUSES = ["pending", "claimed", "running", "done", "failed", "cancelled"]


class TaskStore:
    def __init__(self, task_dir: str):
        self.task_dir = Path(task_dir)
        self.task_dir.mkdir(parents=True, exist_ok=True)

    def _task_file(self, task_id: str) -> Path:
        return self.task_dir / f"{task_id}.json"

    def create(self, task_type: str, payload: dict) -> dict:
        """Create a new task, returns task dict. Fails if task_id already exists."""
        task_id = str(uuid.uuid4())
        task_file = self._task_file(task_id)

        if task_file.exists():
            raise ValueError(f"Task {task_id} already exists")

        now = datetime.utcnow().isoformat() + "Z"
        task = {
            "task_id": task_id,
            "task_type": task_type,
            "payload": payload,
            "status": "pending",
            "created_at": now,
            "updated_at": now,
        }

        with open(task_file, "w", encoding="utf-8") as f:
            json.dump(task, f, indent=2)

        return task

    def get(self, task_id: str) -> dict | None:
        """Get task by ID, returns None if not found."""
        task_file = self._task_file(task_id)
        if not task_file.exists():
            return None
        with open(task_file, encoding="utf-8") as f:
            return json.load(f)

    def get_next_pending(self) -> dict | None:
        """Get the oldest pending task, or None if none available."""
        tasks = []
        for tf in self.task_dir.glob("*.json"):
            with open(tf, encoding="utf-8") as f:
                task = json.load(f)
                if task["status"] == "pending":
                    tasks.append(task)

        if not tasks:
            return None

        # Return oldest by created_at
        tasks.sort(key=lambda t: t["created_at"])
        return tasks[0]

    def claim(self, task_id: str) -> dict | None:
        """Atomically claim a pending task, changing it to 'claimed'."""
        task = self.get(task_id)
        if not task:
            return None
        if task["status"] != "pending":
            return None

        task["status"] = "claimed"
        task["updated_at"] = datetime.utcnow().isoformat() + "Z"

        with open(self._task_file(task_id), "w", encoding="utf-8") as f:
            json.dump(task, f, indent=2)

        return task

    def update_status(self, task_id: str, status: str, result: dict | None = None) -> dict | None:
        """Update task status, optionally with result data."""
        if status not in TASK_STATUSES:
            raise ValueError(f"Invalid status: {status}")

        task = self.get(task_id)
        if not task:
            return None

        task["status"] = status
        task["updated_at"] = datetime.utcnow().isoformat() + "Z"

        if result:
            for key in ["summary", "artifact_path", "stdout_tail", "stderr_tail"]:
                if key in result:
                    task[key] = result[key]

        with open(self._task_file(task_id), "w", encoding="utf-8") as f:
            json.dump(task, f, indent=2)

        return task
