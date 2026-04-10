"""
Alpic MCP Server V1.1 - Remote-Ready MCP Wrapper for Alpic Task Bridge

Supports two transport modes:
- streamable-http: Remote deployment (default for remote mode)
- stdio: Local development / Claude Desktop

Usage:
    # Remote mode (streamable-http):
    cd alpic-mcp && python server.py remote

    # Local stdio mode (Claude Desktop, etc.):
    cd alpic-mcp && python server.py

Transport is read from config.yaml (server.transport).
Override via command line: python server.py [stdio|remote]
"""

import sys
import os
import logging
import asyncio
from pathlib import Path

import httpx
import yaml

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("alpic-mcp")

# Load config
CONFIG_PATH = Path(__file__).parent / "config.yaml"
if not CONFIG_PATH.exists():
    logger.error(f"Config file not found: {CONFIG_PATH}")
    sys.exit(1)

with open(CONFIG_PATH, encoding="utf-8") as f:
    CONFIG = yaml.safe_load(f)

# Bridge connection
BRIDGE_BASE_URL = os.environ.get("ALPIC_BRIDGE_URL", CONFIG["bridge"]["base_url"]).rstrip("/")
BRIDGE_TOKEN = os.environ.get("ALPIC_BRIDGE_TOKEN", CONFIG["bridge"]["token"])

# MCP identity
MCP_NAME = CONFIG["mcp"]["name"]
MCP_INSTRUCTIONS = CONFIG["mcp"].get("instructions", "")

# Server settings
SERVER_TRANSPORT = os.environ.get("ALPIC_TRANSPORT", CONFIG["server"].get("transport", "streamable-http"))
SERVER_HOST = os.environ.get("ALPIC_HOST", CONFIG["server"].get("host", "0.0.0.0"))
SERVER_PORT = int(os.environ.get("ALPIC_PORT", CONFIG["server"].get("port", 8081)))

if not BRIDGE_TOKEN or BRIDGE_TOKEN == "CHANGE-ME-IN-PRODUCTION":
    logger.warning("Bridge token is not set or still at default value. Set a strong token before deploying.")


class BridgeError(Exception):
    def __init__(self, message: str, status_code: int = None, bridge_response: dict = None):
        self.message = message
        self.status_code = status_code
        self.bridge_response = bridge_response
        super().__init__(self.message)


async def bridge_get(path: str) -> dict:
    url = f"{BRIDGE_BASE_URL}{path}"
    headers = {
        "Authorization": f"Bearer {BRIDGE_TOKEN}",
        "ngrok-skip-browser-warning": "1",
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(url, headers=headers)
        except httpx.ConnectError:
            raise BridgeError(f"Cannot connect to bridge at {BRIDGE_BASE_URL}. Is the bridge running?", status_code=None)
        except httpx.TimeoutException:
            raise BridgeError(f"Bridge request timed out: {path}")

    if resp.status_code == 401:
        raise BridgeError("Unauthorized: token is invalid or missing", status_code=401)
    if resp.status_code == 404:
        raise BridgeError(f"Resource not found: {path}", status_code=404)

    try:
        return resp.json()
    except Exception:
        raise BridgeError(f"Invalid JSON from bridge: {resp.text[:200]}", status_code=resp.status_code)


async def bridge_post(path: str, data: dict) -> dict:
    url = f"{BRIDGE_BASE_URL}{path}"
    headers = {
        "Authorization": f"Bearer {BRIDGE_TOKEN}",
        "Content-Type": "application/json",
        "ngrok-skip-browser-warning": "1",
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(url, json=data, headers=headers)
        except httpx.ConnectError:
            raise BridgeError(f"Cannot connect to bridge at {BRIDGE_BASE_URL}. Is the bridge running?", status_code=None)
        except httpx.TimeoutException:
            raise BridgeError(f"Bridge request timed out: {path}")

    if resp.status_code == 401:
        raise BridgeError("Unauthorized: token is invalid or missing", status_code=401)

    try:
        return resp.json()
    except Exception:
        raise BridgeError(f"Invalid JSON from bridge: {resp.text[:200]}", status_code=resp.status_code)


from mcp.server.fastmcp import FastMCP

# stateless_http=True: each request is independent, no session tracking needed
mcp = FastMCP(MCP_NAME, instructions=MCP_INSTRUCTIONS, stateless_http=True)


@mcp.tool()
async def create_task(task_type: str, payload: dict) -> str:
    """
    Create a new task in the Alpic Task Bridge.

    Args:
        task_type: Type of task - write_file, run_python, or run_shell_safe
        payload: Task-specific payload dictionary

    Returns:
        JSON with task_id and creation result
    """
    if not task_type:
        return '{"error": "task_type is required"}'
    if task_type not in ("write_file", "run_python", "run_shell_safe"):
        return f'{{"error": "unsupported task_type: {task_type}. Supported: write_file, run_python, run_shell_safe"}}'
    if not isinstance(payload, dict):
        return '{"error": "payload must be a dictionary"}'

    try:
        result = await bridge_post("/task", {"task_type": task_type, "payload": payload})
        if "task" in result:
            task = result["task"]
            return f'{{"success": true, "task_id": "{task["task_id"]}", "status": "accepted", "message": "Task created successfully"}}'
        if "error" in result:
            return f'{{"success": false, "error": "{result["error"]}"}}'
        return f'{{"success": false, "error": "Unexpected response: {result}"}}'
    except BridgeError as e:
        return f'{{"success": false, "error": "{e.message}", "http_status": {e.status_code}}}'
    except Exception as e:
        logger.error(f"Unexpected error in create_task: {e}")
        return f'{{"success": false, "error": "MCP server error: {str(e)}"}}'


@mcp.tool()
async def get_task_status(task_id: str) -> str:
    """
    Query the status of a task by its ID.

    Args:
        task_id: The UUID of the task to query

    Returns:
        JSON with task_id, status, summary, artifact_path, stdout_tail, stderr_tail
    """
    if not task_id:
        return '{"error": "task_id is required"}'

    try:
        result = await bridge_get(f"/task/{task_id}")
        if "task" in result:
            task = result["task"]
            import json
            return json.dumps({
                "task_id": task_id,
                "status": task.get("status"),
                "summary": task.get("summary", ""),
                "artifact_path": task.get("artifact_path", ""),
                "stdout_tail": task.get("stdout_tail", ""),
                "stderr_tail": task.get("stderr_tail", ""),
            })
        if "error" in result:
            return f'{{"error": "{result["error"]}"}}'
        return f'{{"error": "Unexpected response: {result}"}}'
    except BridgeError as e:
        if e.status_code == 404:
            return f'{{"error": "Task not found: {task_id}"}}'
        return f'{{"success": false, "error": "{e.message}", "http_status": {e.status_code}}}'
    except Exception as e:
        logger.error(f"Unexpected error in get_task_status: {e}")
        return f'{{"error": "MCP server error: {str(e)}"}}'


@mcp.tool()
async def get_bridge_health() -> str:
    """
    Check the health status of the Alpic Task Bridge.

    Returns:
        JSON with service, version, status, timestamp
    """
    try:
        result = await bridge_get("/health")
        if "status" in result:
            import json
            return json.dumps({
                "service": result.get("service", "unknown"),
                "version": result.get("version", "unknown"),
                "status": result.get("status"),
                "timestamp": result.get("timestamp", ""),
            })
        return f'{{"error": "Unexpected health response: {result}"}}'
    except BridgeError as e:
        return f'{{"error": "{e.message}", "http_status": {e.status_code}}}'
    except Exception as e:
        logger.error(f"Unexpected error in get_bridge_health: {e}")
        return f'{{"error": "MCP server error: {str(e)}"}}'


def run_remote():
    """Run as a streamable-http server via Uvicorn."""
    import uvicorn
    logger.info(f"Starting MCP server (streamable-http) on {SERVER_HOST}:{SERVER_PORT}")
    logger.info(f"Bridge: {BRIDGE_BASE_URL}")
    app = mcp.streamable_http_app()
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT, log_level="info")


def run_stdio():
    """Run in stdio mode (local development / Claude Desktop)."""
    logger.info(f"Starting MCP server (stdio)")
    logger.info(f"Bridge: {BRIDGE_BASE_URL}")
    mcp.run(transport="stdio")


def main():
    mode = sys.argv[1].lower() if len(sys.argv) > 1 else ""

    if mode in ("remote", "streamable-http", "http"):
        run_remote()
    elif mode == "stdio":
        run_stdio()
    else:
        # Default: remote (streamable-http) for deployment
        logger.info(f"No transport specified, defaulting to remote (streamable-http)")
        logger.info(f"Specify 'stdio' as argument for local mode")
        run_remote()


if __name__ == "__main__":
    main()
