"""
Alpic Worker V1 - Minimal Worker
Pulls tasks from bridge, deduplicates, executes, reports results.
"""

import json
import sys
import time
import logging
from pathlib import Path
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

import yaml

# Determine base dir
BASE_DIR = Path(__file__).parent.absolute()

# Setup logging
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / "worker.log"),
    ],
)
logger = logging.getLogger("worker")

# Load config
CONFIG_PATH = BASE_DIR / "config.yaml"
with open(CONFIG_PATH, encoding="utf-8") as f:
    CONFIG = yaml.safe_load(f)

BRIDGE_URL = CONFIG["worker"]["bridge_url"]
BRIDGE_TOKEN = CONFIG["worker"]["token"]
POLL_INTERVAL = CONFIG["worker"]["poll_interval_seconds"]
STATE_FILE = BASE_DIR / CONFIG["state"]["state_file"]
SUPPORTED_TYPES = CONFIG["supported_task_types"]
ALLOWED_WRITE_DIRS = [str(BASE_DIR / d) for d in CONFIG.get("allowed_dirs", [])]
PYTHON_PATH = CONFIG.get("python", {}).get("python_path", "") or "python"
PYTHON_TIMEOUT = CONFIG.get("python", {}).get("default_timeout_seconds", 30)
SHELL_ALLOWED_COMMANDS = CONFIG.get("shell", {}).get("allowed_commands", [])
SHELL_TIMEOUT = CONFIG.get("shell", {}).get("default_timeout_seconds", 30)

STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

from worker_state import WorkerState
from executors import SUPPORTED_EXECUTORS

state = WorkerState(STATE_FILE)


def api_get(path: str) -> dict | None:
    """Make authenticated GET request to bridge."""
    url = f"{BRIDGE_URL}{path}"
    req = Request(url, headers={"Authorization": f"Bearer {BRIDGE_TOKEN}"})
    try:
        resp = urlopen(req, timeout=10)
        return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        body = e.read().decode("utf-8") if e.fp else "{}"
        logger.error(f"HTTP {e.code} on {path}: {body}")
        return None
    except URLError as e:
        logger.error(f"URL error on {path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Request error on {path}: {e}")
        return None


def api_post(path: str, data: dict) -> dict | None:
    """Make authenticated POST request to bridge."""
    url = f"{BRIDGE_URL}{path}"
    body = json.dumps(data).encode("utf-8")
    req = Request(
        url,
        data=body,
        headers={"Authorization": f"Bearer {BRIDGE_TOKEN}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        resp = urlopen(req, timeout=10)
        return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        body = e.read().decode("utf-8") if e.fp else "{}"
        logger.error(f"HTTP {e.code} on {path}: {body}")
        return None
    except URLError as e:
        logger.error(f"URL error on {path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Request error on {path}: {e}")
        return None


def report_result(task_id: str, status: str, summary: str = "", artifact_path: str = "", stdout_tail: str = "", stderr_tail: str = ""):
    """Report task result to bridge."""
    result = {
        "task_id": task_id,
        "status": status,
        "summary": summary,
        "artifact_path": artifact_path,
        "stdout_tail": stdout_tail,
        "stderr_tail": stderr_tail,
    }
    resp = api_post("/task/result", result)
    if resp:
        logger.info(f"Reported result for {task_id}: {status}")
    else:
        logger.error(f"Failed to report result for {task_id}")
    return resp is not None


def execute_task(task: dict) -> tuple[str, str, str, str, str]:
    """
    Execute a task. Returns (status, summary, artifact_path, stdout_tail, stderr_tail).
    Dispatches to the appropriate executor based on task_type.
    """
    task_id = task["task_id"]
    task_type = task["task_type"]
    payload = task.get("payload", {})

    if task_type not in SUPPORTED_TYPES:
        return ("failed", f"unsupported_task_type: {task_type}", "", "", "")

    executor = SUPPORTED_EXECUTORS.get(task_type)
    if executor is None:
        return ("failed", f"executor_not_implemented: {task_type}", "", "", "executor not yet implemented")

    # Dispatch to the appropriate executor
    if task_type == "write_file":
        return executor(task_id, payload, ALLOWED_WRITE_DIRS)

    if task_type == "run_python":
        return executor(task_id, payload, ALLOWED_WRITE_DIRS, PYTHON_PATH, PYTHON_TIMEOUT)

    if task_type == "run_shell_safe":
        return executor(task_id, payload, ALLOWED_WRITE_DIRS, SHELL_ALLOWED_COMMANDS, SHELL_TIMEOUT)

    # Fallback for other types
    return ("failed", f"executor_not_implemented: {task_type}", "", "", "executor not yet implemented")


def poll_and_execute():
    """Poll bridge for a task, execute if available, report result."""
    # Check if already running something
    if not state.is_idle():
        logger.debug("Already running a task, skipping poll")
        return

    # Pull next task
    result = api_get("/task/next")
    if result is None:
        logger.warning("Failed to get task from bridge")
        return

    task_data = result.get("task")
    if task_data is None:
        logger.debug("No pending tasks")
        return

    task_id = task_data["task_id"]
    task_type = task_data["task_type"]

    logger.info(f"Received task: {task_id} type={task_type}")

    # Deduplication checks
    if state.has_completed(task_id):
        logger.info(f"Task {task_id} already completed, skipping")
        return

    if not state.start_task(task_id):
        logger.info(f"Task {task_id} is already running elsewhere or lock not acquired")
        return

    try:
        # Execute task
        status, summary, artifact_path, stdout_tail, stderr_tail = execute_task(task_data)

        # Report result
        report_result(task_id, status, summary, artifact_path, stdout_tail, stderr_tail)

        # Update local state
        if status == "done":
            state.complete_task(task_id)
        else:
            state.fail_task(task_id)

        logger.info(f"Task {task_id} finished with status={status}")

    except Exception as e:
        logger.error(f"Error executing task {task_id}: {e}")
        report_result(task_id, "failed", f"execution_error: {str(e)}", "", "", str(e))
        state.fail_task(task_id)


def run():
    """Main worker loop."""
    logger.info(f"Alpic Worker V1 starting")
    logger.info(f"Bridge: {BRIDGE_URL}")
    logger.info(f"Poll interval: {POLL_INTERVAL}s")
    logger.info(f"State file: {STATE_FILE}")

    # Recover from any leftover running state (crash recovery)
    current_state = state.get_state()
    if current_state["current_running_task_id"] is not None:
        logger.warning(f"Found leftover running task: {current_state['current_running_task_id']}, clearing")
        state.clear_running()

    while True:
        try:
            poll_and_execute()
        except Exception as e:
            logger.error(f"Error in worker loop: {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    run()
