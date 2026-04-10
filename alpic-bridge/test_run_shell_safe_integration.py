"""End-to-end test for run_shell_safe task."""
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


def api(method, path, data=None):
    url = BRIDGE_URL + path
    headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(req, timeout=5)
        return json.loads(resp.read().decode()), resp.status
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode()), e.code


def test_run_shell_safe_integration():
    print("=== Integration Test: run_shell_safe ===")

    task_data = {
        "task_type": "run_shell_safe",
        "payload": {
            "command": "python",
            "args": ["-c", "print('hello from shell safe')"],
        }
    }
    result, status = api("POST", "/task", task_data)
    task_id = result.get("task", {}).get("task_id")
    print(f"1. Created run_shell_safe task: {task_id} (status={status})")

    print("2. Waiting for worker to pick up task...")
    time.sleep(8)

    result, _ = api("GET", f"/task/{task_id}")
    task = result.get("task", {})
    print(f"3. Task final status: {task.get('status')}")
    print(f"   Summary: {task.get('summary', 'N/A')}")
    print(f"   Stdout: {task.get('stdout_tail', 'N/A')}")

    if task.get("status") == "done":
        print("\n=== run_shell_safe Integration Test PASSED ===")
        return True
    else:
        print(f"\n=== run_shell_safe Integration Test FAILED: status={task.get('status')} ===")
        return False


if __name__ == "__main__":
    sys.exit(0 if test_run_shell_safe_integration() else 1)
