"""End-to-end test: create a run_python task and verify worker executes it."""
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


def test_run_python_integration():
    print("=== Integration Test: run_python ===")

    script_path = Path(__file__).parent.parent / "alpic-worker" / "work" / "test_success.py"

    # Create a run_python task
    task_data = {
        "task_type": "run_python",
        "payload": {
            "script": str(script_path.resolve()),
            "args": ["hello", "world"],
        }
    }
    result, status = api("POST", "/task", task_data)
    task_id = result.get("task", {}).get("task_id")
    print(f"1. Created run_python task: {task_id} (status={status})")

    # Worker should pick it up within poll interval (5s)
    print("2. Waiting for worker to pick up task...")
    time.sleep(8)

    # Check task status
    result, status = api("GET", f"/task/{task_id}")
    task = result.get("task", {})
    print(f"3. Task final status: {task.get('status')}")
    print(f"   Summary: {task.get('summary', 'N/A')}")
    print(f"   Stdout: {task.get('stdout_tail', 'N/A')}")

    if task.get("status") == "done":
        print("\n=== run_python Integration Test PASSED ===")
        return True
    else:
        print(f"\n=== run_python Integration Test FAILED: status={task.get('status')} ===")
        return False


if __name__ == "__main__":
    sys.exit(0 if test_run_python_integration() else 1)
