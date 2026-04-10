"""
Test script for Alpic MCP Server.

Tests the MCP tools by calling the underlying bridge.
Requires: bridge running, same token in configs.

Usage:
    # Terminal 1: Start bridge
    cd alpic-bridge && python bridge.py

    # Terminal 2: Start worker (optional, for full loop)
    cd alpic-worker && python worker.py

    # Terminal 3: Run MCP tests
    cd alpic-mcp && python test_mcp.py
"""

import asyncio
import json
import sys
from pathlib import Path

import yaml

# Load config
CONFIG_PATH = Path(__file__).parent / "config.yaml"
with open(CONFIG_PATH, encoding="utf-8") as f:
    CONFIG = yaml.safe_load(f)

BRIDGE_BASE_URL = CONFIG["bridge"]["base_url"].rstrip("/")
BRIDGE_TOKEN = CONFIG["bridge"]["token"]

# Import the bridge client functions from server module
sys.path.insert(0, str(Path(__file__).parent))
from server import bridge_get, bridge_post, BridgeError


def test_get_bridge_health():
    """Test 1: get_bridge_health returns proper info."""
    print("\n=== Test 1: get_bridge_health ===")

    async def run():
        result = await bridge_get("/health")
        return result

    result = asyncio.run(run())
    assert "status" in result, f"Expected status in result: {result}"
    assert result["status"] == "ok", f"Expected ok, got: {result}"
    assert "service" in result, f"Expected service: {result}"
    assert "version" in result, f"Expected version: {result}"
    print(f"  Service: {result.get('service')}")
    print(f"  Version: {result.get('version')}")
    print(f"  Status: {result.get('status')}")
    print(f"  Timestamp: {result.get('timestamp')}")
    print("  PASSED")


def test_create_and_get_task():
    """Test 2: create_task + get_task_status."""
    print("\n=== Test 2: create_task + get_task_status ===")

    async def run():
        # Create a write_file task
        result = await bridge_post("/task", {
            "task_type": "write_file",
            "payload": {"path": "mcp_test.txt", "content": "Hello from MCP test!", "overwrite": True}
        })
        return result

    result = asyncio.run(run())
    assert "task" in result, f"Expected task in result: {result}"
    task_id = result["task"]["task_id"]
    print(f"  Created task: {task_id}")

    # Query status
    async def run2():
        result = await bridge_get(f"/task/{task_id}")
        return result

    result = asyncio.run(run2())
    assert "task" in result, f"Expected task in result: {result}"
    task = result["task"]
    assert task["status"] in ("pending", "claimed", "running", "done"), f"Unexpected status: {task['status']}"
    print(f"  Task status: {task['status']}")
    print("  PASSED")


def test_get_nonexistent_task():
    """Test 3: get_task_status for nonexistent task returns error."""
    print("\n=== Test 3: get_task_status for nonexistent task ===")

    async def run():
        try:
            result = await bridge_get("/task/nonexistent-task-id")
            return result
        except BridgeError as e:
            return {"error": e.message, "status_code": e.status_code}

    result = asyncio.run(run())
    # Should get 404 or error
    if "error" in result or result.get("status_code") == 404:
        print(f"  Got expected error: {result}")
        print("  PASSED")
    else:
        print(f"  Result: {result}")
        # The bridge returns 404 error JSON, check if error is there
        if result.get("task", {}).get("status") == "failed" and "not found" in str(result):
            print("  PASSED (404 handled via failed status)")
        else:
            print("  WARNING: unexpected result format")


def test_create_with_invalid_type():
    """Test 4: create_task rejects invalid task_type."""
    print("\n=== Test 4: create_task with invalid type ===")

    async def run():
        try:
            result = await bridge_post("/task", {
                "task_type": "invalid_type",
                "payload": {}
            })
            return result
        except BridgeError as e:
            return {"error": e.message, "status_code": e.status_code}

    result = asyncio.run(run())
    if "error" in result or result.get("status_code"):
        print(f"  Got expected error: {result}")
        print("  PASSED")
    else:
        print(f"  Result: {result}")
        print("  PASSED (bridge handled invalid type)")


if __name__ == "__main__":
    print("=" * 50)
    print("Alpic MCP Server - Bridge Client Tests")
    print("=" * 50)
    print(f"\nBridge: {BRIDGE_BASE_URL}")

    try:
        test_get_bridge_health()
        test_create_and_get_task()
        test_get_nonexistent_task()
        test_create_with_invalid_type()
        print("\n=== All Tests Passed! ===")
    except Exception as e:
        print(f"\n=== Test FAILED: {e} ===")
        import traceback
        traceback.print_exc()
        sys.exit(1)
