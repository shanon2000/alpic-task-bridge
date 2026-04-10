"""Test script for Alpic Task Bridge V1 endpoints"""
import json
import urllib.request
import urllib.error
from pathlib import Path

import yaml

BASE_URL = "http://127.0.0.1:18080"
BRIDGE_DIR = Path(__file__).parent
CONFIG_PATH = BRIDGE_DIR / "config.yaml"
with open(CONFIG_PATH, encoding="utf-8") as f:
    CONFIG = yaml.safe_load(f)
TOKEN = CONFIG["bridge"]["token"]


def make_request(method, path, data=None):
    url = BASE_URL + path
    headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data else None, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(req, timeout=5)
        return json.loads(resp.read().decode()), resp.status
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode()), e.code
    except Exception as e:
        return {"error": str(e)}, 0


def test_health():
    print("\n=== Test: GET /health ===")
    result, status = make_request("GET", "/health")
    print(f"Status: {status}")
    print(f"Response: {result}")
    return status == 200


def test_create_task():
    print("\n=== Test: POST /task ===")
    task_data = {
        "task_type": "write_file",
        "payload": {"path": "test.txt", "content": "hello world", "overwrite": True}
    }
    result, status = make_request("POST", "/task", task_data)
    print(f"Status: {status}")
    print(f"Response: {json.dumps(result, indent=2)}")
    return result.get("task", {}).get("task_id") if status == 201 else None


def test_get_task_next():
    print("\n=== Test: GET /task/next ===")
    result, status = make_request("GET", "/task/next")
    print(f"Status: {status}")
    print(f"Response: {json.dumps(result, indent=2)}")
    return result.get("task")


def test_get_task(task_id):
    print(f"\n=== Test: GET /task/{task_id} ===")
    result, status = make_request("GET", f"/task/{task_id}")
    print(f"Status: {status}")
    print(f"Response: {json.dumps(result, indent=2)}")
    return result.get("task")


def test_post_result(task_id):
    print(f"\n=== Test: POST /task/result ===")
    result_data = {
        "task_id": task_id,
        "status": "done",
        "summary": "File written successfully",
        "stdout_tail": "1 file written",
        "stderr_tail": ""
    }
    result, status = make_request("POST", "/task/result", result_data)
    print(f"Status: {status}")
    print(f"Response: {json.dumps(result, indent=2)}")
    return status == 200


if __name__ == "__main__":
    print("Testing Alpic Task Bridge V1...")

    # Test health
    if not test_health():
        print("Health check failed - is the server running?")
        exit(1)

    # Test create task
    task_id = test_create_task()
    if not task_id:
        print("Failed to create task")
        exit(1)

    # Test get task (by ID)
    task = test_get_task(task_id)
    if not task:
        print("Failed to get task by ID")
        exit(1)

    # Test get next (should be empty now since we claimed the only task)
    next_task = test_get_task_next()
    print(f"Next task (should be None): {next_task}")

    # Test post result
    if test_post_result(task_id):
        print("Result posted successfully")
    else:
        print("Failed to post result")
        exit(1)

    # Verify final status
    task = test_get_task(task_id)
    print(f"\nFinal task status: {task['status']}")

    print("\n=== All tests passed! ===")
