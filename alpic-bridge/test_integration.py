"""Minimal end-to-end integration test: bridge + worker."""
import json
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

import yaml

BRIDGE_DIR = Path(__file__).parent
WORKER_DIR = Path(__file__).parent.parent / "alpic-worker"
BRIDGE_URL = "http://127.0.0.1:18080"

# Read token from bridge config
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


def test_integration():
    print("=== Integration Test: Bridge + Worker ===")

    # Create a task
    task_data = {
        "task_type": "write_file",
        "payload": {"path": "test.txt", "content": "hello from worker", "overwrite": True}
    }
    result, status = api("POST", "/task", task_data)
    task_id = result.get("task", {}).get("task_id")
    print(f"1. Created task: {task_id} (status={status})")

    # Worker should pick it up within poll interval (5s), give it 8s
    print("2. Waiting for worker to pick up task...")
    time.sleep(8)

    # Check task status
    result, status = api("GET", f"/task/{task_id}")
    task = result.get("task", {})
    print(f"3. Task final status: {task.get('status')}")
    print(f"   Summary: {task.get('summary', 'N/A')}")

    if task.get("status") == "done":
        print("\n=== Integration Test PASSED ===")
        return True
    else:
        print(f"\n=== Integration Test FAILED: status={task.get('status')} ===")
        return False


if __name__ == "__main__":
    # Run from bridge dir
    sys.exit(0 if test_integration() else 1)
