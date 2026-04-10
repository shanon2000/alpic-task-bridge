"""
Security and Hardening Tests for Alpic Task Bridge V1.1

Tests:
1. GET /health returns proper info (no auth required)
2. GET /task/{id} with correct token succeeds
3. GET /task/{id} without token returns 401
4. GET /task/{id} with wrong token returns 401
5. POST /task with correct token succeeds
6. POST /task without token returns 401
7. POST /task/result with correct token succeeds
8. POST /task/result without token returns 401
"""

import json
import sys
import urllib.request
import urllib.error
from pathlib import Path

BRIDGE_URL = "http://127.0.0.1:18080"
CORRECT_TOKEN = "CHANGE-ME-IN-PRODUCTION"
WRONG_TOKEN = "wrong-token-12345"


def api(method: str, path: str, data: dict = None, token: str = None) -> tuple[dict, int]:
    url = BRIDGE_URL + path
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(req, timeout=5)
        return json.loads(resp.read().decode()), resp.status
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode()), e.code
        except Exception:
            return {"error": str(e)}, e.code
    except Exception as e:
        return {"error": str(e)}, 0


def test_health_no_auth():
    """Test 1: /health works without auth."""
    print("\n=== Test 1: GET /health (no auth) ===")
    result, status = api("GET", "/health")
    assert status == 200, f"Expected 200, got {status}"
    assert result.get("status") == "ok", f"Expected ok, got {result}"
    assert "service" in result, f"Expected service field, got {result}"
    assert "version" in result, f"Expected version field, got {result}"
    assert "timestamp" in result, f"Expected timestamp field, got {result}"
    print(f"  Status: {status}")
    print(f"  Response: {result}")
    print("  PASSED")


def test_get_task_with_correct_token():
    """Test 2: GET /task/{id} with correct token."""
    print("\n=== Test 2: GET /task/{id} with correct token ===")
    # Create a task first
    result, _ = api("POST", "/task", {"task_type": "write_file", "payload": {"path": "test.txt", "content": "hi"}}, CORRECT_TOKEN)
    task_id = result.get("task", {}).get("task_id")
    assert task_id, f"No task_id in response: {result}"

    # Now fetch with correct token
    result, status = api("GET", f"/task/{task_id}", token=CORRECT_TOKEN)
    assert status == 200, f"Expected 200, got {status}: {result}"
    assert result.get("task", {}).get("task_id") == task_id
    print(f"  Status: {status}, task_id={task_id}")
    print("  PASSED")


def test_get_task_no_token():
    """Test 3: GET /task/{id} without token returns 401."""
    print("\n=== Test 3: GET /task/{id} without token ===")
    result, status = api("GET", "/task/some-nonexistent-id")
    assert status == 401, f"Expected 401, got {status}: {result}"
    print(f"  Status: {status} (correctly unauthorized)")
    print("  PASSED")


def test_get_task_wrong_token():
    """Test 4: GET /task/{id} with wrong token returns 401."""
    print("\n=== Test 4: GET /task/{id} with wrong token ===")
    result, status = api("GET", "/task/some-id", token=WRONG_TOKEN)
    assert status == 401, f"Expected 401, got {status}: {result}"
    print(f"  Status: {status} (correctly rejected)")
    print("  PASSED")


def test_post_task_with_correct_token():
    """Test 5: POST /task with correct token."""
    print("\n=== Test 5: POST /task with correct token ===")
    result, status = api("POST", "/task", {"task_type": "write_file", "payload": {"path": "test.txt", "content": "hi"}}, CORRECT_TOKEN)
    assert status == 201, f"Expected 201, got {status}: {result}"
    assert "task" in result
    print(f"  Status: {status}, task_id={result['task']['task_id']}")
    print("  PASSED")


def test_post_task_no_token():
    """Test 6: POST /task without token returns 401."""
    print("\n=== Test 6: POST /task without token ===")
    result, status = api("POST", "/task", {"task_type": "write_file", "payload": {"path": "test.txt", "content": "hi"}})
    assert status == 401, f"Expected 401, got {status}: {result}"
    print(f"  Status: {status} (correctly unauthorized)")
    print("  PASSED")


def test_post_result_with_correct_token():
    """Test 7: POST /task/result with correct token."""
    print("\n=== Test 7: POST /task/result with correct token ===")
    # Create a task
    result, _ = api("POST", "/task", {"task_type": "write_file", "payload": {"path": "test.txt", "content": "hi"}}, CORRECT_TOKEN)
    task_id = result.get("task", {}).get("task_id")

    # Report result
    result, status = api("POST", "/task/result", {"task_id": task_id, "status": "done", "summary": "test done"}, CORRECT_TOKEN)
    assert status == 200, f"Expected 200, got {status}: {result}"
    print(f"  Status: {status}")
    print("  PASSED")


def test_post_result_no_token():
    """Test 8: POST /task/result without token returns 401."""
    print("\n=== Test 8: POST /task/result without token ===")
    result, status = api("POST", "/task/result", {"task_id": "fake-id", "status": "done"})
    assert status == 401, f"Expected 401, got {status}: {result}"
    print(f"  Status: {status} (correctly unauthorized)")
    print("  PASSED")


def test_get_task_next_with_correct_token():
    """Test 9: GET /task/next with correct token."""
    print("\n=== Test 9: GET /task/next with correct token ===")
    result, status = api("GET", "/task/next", token=CORRECT_TOKEN)
    # 200 is fine - there may or may not be tasks
    assert status == 200, f"Expected 200, got {status}: {result}"
    print(f"  Status: {status}")
    print("  PASSED")


def test_get_task_next_no_token():
    """Test 10: GET /task/next without token returns 401."""
    print("\n=== Test 10: GET /task/next without token ===")
    result, status = api("GET", "/task/next")
    assert status == 401, f"Expected 401, got {status}: {result}"
    print(f"  Status: {status} (correctly unauthorized)")
    print("  PASSED")


if __name__ == "__main__":
    print("=" * 50)
    print("Security Hardening Tests - Alpic Task Bridge V1.1")
    print("=" * 50)

    tests = [
        test_health_no_auth,
        test_get_task_with_correct_token,
        test_get_task_no_token,
        test_get_task_wrong_token,
        test_post_task_with_correct_token,
        test_post_task_no_token,
        test_post_result_with_correct_token,
        test_post_result_no_token,
        test_get_task_next_with_correct_token,
        test_get_task_next_no_token,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"  FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"  ERROR: {e}")
            failed += 1

    print(f"\n{'=' * 50}")
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 50)
    sys.exit(0 if failed == 0 else 1)
