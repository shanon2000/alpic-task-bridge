"""
Simplified remote MCP test - verifies the server is reachable and the MCP
endpoint accepts requests in stateless mode.
"""

import json
import sys
import httpx
import asyncio
from pathlib import Path

import yaml

CONFIG_PATH = Path(__file__).parent / "config.yaml"
with open(CONFIG_PATH, encoding="utf-8") as f:
    CONFIG = yaml.safe_load(f)

SERVER_PORT = CONFIG["server"]["port"]
MCP_BASE_URL = f"http://127.0.0.1:{SERVER_PORT}"
BRIDGE_TOKEN = CONFIG["bridge"]["token"]

# MCP requires both application/json AND text/event-stream for POST /mcp
HEADERS = {
    "Authorization": f"Bearer {BRIDGE_TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
    "ngrok-skip-browser-warning": "1",
}


async def test_server_reachable():
    print("\n=== Test 1: Server Reachable ===")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{MCP_BASE_URL}/", timeout=5)
            print(f"  HTTP {resp.status_code} from {MCP_BASE_URL}/")
    except Exception as e:
        print(f"  FAILED: {e}")
        return False
    print("  PASSED")
    return True


async def call_mcp(method: str, params: dict = None) -> dict:
    """Make a JSON-RPC call to the MCP endpoint."""
    payload = {"jsonrpc": "2.0", "id": 1, "method": method}
    if params:
        payload["params"] = params
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(f"{MCP_BASE_URL}/mcp", json=payload, headers=HEADERS)
    raw = resp.text
    for line in raw.split("\n"):
        line = line.strip()
        if line.startswith("data:"):
            return json.loads(line[5:])
    return {"_raw": raw, "_status": resp.status_code}


async def test_tools_list():
    print("\n=== Test 2: tools/list ===")
    result = await call_mcp("tools/list")
    if "error" in result:
        print(f"  FAILED: {result['error']}")
        return False
    tools = result.get("result", {}).get("tools", [])
    tool_names = [t.get("name") for t in tools]
    print(f"  Tools: {tool_names}")
    expected = {"create_task", "get_task_status", "get_bridge_health"}
    if expected.issubset(set(tool_names)):
        print("  PASSED")
        return True
    print(f"  FAILED: missing tools")
    return False


async def test_get_bridge_health():
    print("\n=== Test 3: get_bridge_health ===")
    result = await call_mcp("tools/call", {"name": "get_bridge_health", "arguments": {}})
    if "error" in result:
        print(f"  FAILED: {result['error']}")
        return False
    content = result.get("result", {}).get("content", [])
    text = content[0].get("text", "") if content else ""
    print(f"  Response: {text[:200]}")
    parsed = json.loads(text)
    if parsed.get("status") == "ok":
        print("  PASSED")
        return True
    print(f"  FAILED: unexpected response")
    return False


async def test_create_task():
    print("\n=== Test 4: create_task ===")
    result = await call_mcp("tools/call", {
        "name": "create_task",
        "arguments": {
            "task_type": "write_file",
            "payload": {"path": "mcp_remote.txt", "content": "Hello from MCP remote!", "overwrite": True}
        }
    })
    if "error" in result:
        print(f"  FAILED: {result['error']}")
        return None
    content = result.get("result", {}).get("content", [])
    text = content[0].get("text", "") if content else ""
    print(f"  Response: {text[:200]}")
    parsed = json.loads(text)
    if parsed.get("success"):
        task_id = parsed.get("task_id")
        print(f"  task_id={task_id} - PASSED")
        return task_id
    print(f"  FAILED: {parsed.get('error')}")
    return None


async def test_get_task_status(task_id: str):
    print(f"\n=== Test 5: get_task_status ({task_id}) ===")
    result = await call_mcp("tools/call", {
        "name": "get_task_status",
        "arguments": {"task_id": task_id}
    })
    if "error" in result:
        print(f"  FAILED: {result['error']}")
        return False
    content = result.get("result", {}).get("content", [])
    text = content[0].get("text", "") if content else ""
    print(f"  Response: {text[:200]}")
    parsed = json.loads(text)
    if "status" in parsed:
        print(f"  status={parsed.get('status')} - PASSED")
        return True
    print(f"  FAILED: unexpected response")
    return False


async def main():
    print("=" * 50)
    print("Alpic MCP Server - Remote Mode Tests")
    print("=" * 50)
    print(f"\nMCP Server: {MCP_BASE_URL}")
    print(f"Transport: streamable-http (stateless)")

    all_ok = True

    r1 = await test_server_reachable()
    all_ok = all_ok and r1

    r2 = await test_tools_list()
    all_ok = all_ok and r2

    r3 = await test_get_bridge_health()
    all_ok = all_ok and r3

    task_id = await test_create_task()
    if task_id:
        all_ok = all_ok and (task_id is not None)
    else:
        print("\n=== Test 5: SKIPPED (no task_id)")

    if task_id:
        r5 = await test_get_task_status(task_id)
        all_ok = all_ok and r5

    print(f"\n{'=' * 50}")
    print(f"Result: {'ALL PASSED' if all_ok else 'SOME FAILED'}")
    print("=" * 50)
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    asyncio.run(main())
