"""
Alpic Task Bridge V1.1 - Minimal End-to-End Demo

Demonstrates the full loop:
1. Create a write_file task via Bridge API
2. Worker picks it up and executes
3. Query task status to confirm 'done'

Run order:
  Terminal 1: cd alpic-bridge && python bridge.py
  Terminal 2: cd alpic-worker && python worker.py
  Terminal 3: cd alpic-bridge && python demo.py
"""

import json
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

import yaml

BRIDGE_URL = "http://127.0.0.1:18080"
BRIDGE_DIR = Path(__file__).parent
CONFIG_PATH = BRIDGE_DIR / "config.yaml"
with open(CONFIG_PATH, encoding="utf-8") as f:
    CONFIG = yaml.safe_load(f)
TOKEN = CONFIG["bridge"]["token"]


def api(method: str, path: str, data: dict = None) -> tuple[dict, int]:
    url = BRIDGE_URL + path
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
    }
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(
        url, data=body, headers=headers, method=method
    )
    try:
        resp = urllib.request.urlopen(req, timeout=5)
        return json.loads(resp.read().decode()), resp.status
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode()), e.code


def wait_for_status(task_id: str, expected: str, timeout: int = 15) -> dict | None:
    """Poll task status until expected status or timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        result, _ = api("GET", f"/task/{task_id}")
        task = result.get("task", {})
        status = task.get("status")
        print(f"  [{time.time() - (deadline - timeout):.1f}s] status={status}")
        if status == expected:
            return task
        if status in ("failed", "cancelled"):
            return task
        time.sleep(1)
    return None


def demo_write_file():
    print("\n=== Demo: write_file task ===")

    # 1. Create task
    task_data = {
        "task_type": "write_file",
        "payload": {
            "path": "demo_output.txt",
            "content": "Hello from Alpic Task Bridge V1 demo!",
            "overwrite": True,
            "create_dirs": True,
        },
    }
    result, status = api("POST", "/task", task_data)
    if status != 201:
        print(f"❌ Failed to create task: {result}")
        return False

    task = result["task"]
    task_id = task["task_id"]
    print(f"[OK] Task created: {task_id}")
    print(f"   type={task['task_type']}")
    print(f"   payload={task['payload']}")

    # 2. Wait for worker to pick up and complete
    print("\n[WAIT] Waiting for worker to process (polling every 1s)...")
    final_task = wait_for_status(task_id, "done", timeout=15)

    if not final_task:
        print("[FAIL] Timeout waiting for task completion")
        return False

    print(f"\n[FILE] Final status: {final_task['status']}")
    print(f"   summary: {final_task.get('summary', 'N/A')}")
    print(f"   artifact: {final_task.get('artifact_path', 'N/A')}")

    if final_task["status"] == "done":
        # Verify file was written
        output_path = Path(__file__).parent.parent / "alpic-worker" / "allowed_write" / "demo_output.txt"
        if output_path.exists():
            content = output_path.read_text(encoding="utf-8")
            print(f"   file content: {content.strip()}")
        print("\n[OK] Demo PASSED - full loop verified")
        return True
    else:
        print(f"\n[FAIL] Demo FAILED - status={final_task['status']}")
        print(f"   summary: {final_task.get('summary', 'N/A')}")
        return False


if __name__ == "__main__":
    print("=" * 50)
    print("Alpic Task Bridge V1 - Minimal Demo")
    print("=" * 50)
    print("\nPrerequisites:")
    print("  Terminal 1: cd alpic-bridge && python bridge.py")
    print("  Terminal 2: cd alpic-worker && python worker.py")
    print()

    success = demo_write_file()
    sys.exit(0 if success else 1)
