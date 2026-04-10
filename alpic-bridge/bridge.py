"""
Alpic Task Bridge V1 - Minimal Bridge Service
Provides 4 endpoints: POST /task, GET /task/next, POST /task/result, GET /task/{task_id}

V1.1 Security Hardening:
- Bearer token authentication on all task endpoints
- GET /task/{task_id} now requires token
- Enhanced /health endpoint with service info
- Configurable data directories
"""

import json
import re
import sys
import logging
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
from datetime import datetime, timezone

import yaml

VERSION = "1.1"

# Determine base dir (where this script is located)
BASE_DIR = Path(__file__).parent.absolute()

# Load config
CONFIG_PATH = BASE_DIR / "config.yaml"
with open(CONFIG_PATH, encoding="utf-8") as f:
    CONFIG = yaml.safe_load(f)

# Resolve data directories relative to BASE_DIR
LOG_DIR = (BASE_DIR / CONFIG["storage"]["log_dir"]).resolve()
TASK_DIR = (BASE_DIR / CONFIG["storage"]["task_dir"]).resolve()
LOG_DIR.mkdir(parents=True, exist_ok=True)
TASK_DIR.mkdir(parents=True, exist_ok=True)
BRIDGE_TOKEN = CONFIG["bridge"]["token"]

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / "bridge.log"),
    ],
)
logger = logging.getLogger("bridge")

logger.info(f"Task dir: {TASK_DIR}")
logger.info(f"Log dir: {LOG_DIR}")
logger.info(f"Token configured: {'yes' if BRIDGE_TOKEN else 'NO TOKEN SET'}")

# Import task store
sys.path.insert(0, str(BASE_DIR))
from task_store import TaskStore

store = TaskStore(str(TASK_DIR))


def check_token(headers: dict) -> bool:
    """Check Authorization header for valid token."""
    auth = headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:] == BRIDGE_TOKEN
    return False


class BridgeHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler for task bridge."""

    def log_message(self, format, *args):
        logger.info(f"{self.address_string()} {format % args}")

    def send_json(self, status: int, data: dict):
        """Send JSON response."""
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode("utf-8"))
        except Exception as e:
            logger.error(f"Error sending response: {e}")

    def read_body(self):
        """Read request body safely."""
        try:
            length = self.headers.get("Content-Length")
            if length:
                length = int(length)
                if length > 0:
                    return self.rfile.read(length)
            return None
        except Exception as e:
            logger.error(f"Error reading body: {e}")
            return None

    def do_GET(self):
        """Handle GET requests."""
        parsed = urlparse(self.path)
        path = parsed.path
        logger.info(f"GET {path}")

        try:
            # GET /health
            if path == "/health":
                self.send_json(200, {
                    "service": "alpic-bridge",
                    "version": VERSION,
                    "status": "ok",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                return

            # GET /task/next
            if path == "/task/next":
                if not check_token(self.headers):
                    self.send_json(401, {"error": "unauthorized"})
                    return

                task = store.get_next_pending()
                if not task:
                    self.send_json(200, {"task": None, "message": "no pending tasks"})
                    return

                claimed = store.claim(task["task_id"])
                if not claimed:
                    self.send_json(200, {"task": None, "message": "task already claimed"})
                    return

                self.send_json(200, {"task": claimed})
                return

            # GET /task/{task_id}
            match = re.match(r"^/task/([^/]+)$", path)
            if match:
                if not check_token(self.headers):
                    self.send_json(401, {"error": "unauthorized"})
                    return
                task_id = match.group(1)
                task = store.get(task_id)
                if not task:
                    self.send_json(404, {"error": "task not found"})
                    return
                self.send_json(200, {"task": task})
                return

            self.send_json(404, {"error": "not found"})
        except Exception as e:
            logger.error(f"Error handling GET {path}: {e}")
            self.send_json(500, {"error": str(e)})

    def do_POST(self):
        """Handle POST requests."""
        parsed = urlparse(self.path)
        path = parsed.path
        logger.info(f"POST {path}")

        try:
            body = self.read_body()
            if body is not None:
                try:
                    data = json.loads(body)
                except json.JSONDecodeError as e:
                    self.send_json(400, {"error": f"invalid JSON: {e}"})
                    return
            else:
                data = {}

            # POST /task
            if path == "/task":
                if not check_token(self.headers):
                    self.send_json(401, {"error": "unauthorized"})
                    return

                task_type = data.get("task_type")
                payload = data.get("payload", {})

                if not task_type:
                    self.send_json(400, {"error": "task_type is required"})
                    return

                if task_type not in ["write_file", "run_python", "run_shell_safe"]:
                    self.send_json(400, {"error": f"unsupported task_type: {task_type}"})
                    return

                task = store.create(task_type, payload)
                logger.info(f"Created task {task['task_id']} type={task_type}")
                self.send_json(201, {"task": task})
                return

            # POST /task/result
            if path == "/task/result":
                if not check_token(self.headers):
                    self.send_json(401, {"error": "unauthorized"})
                    return

                task_id = data.get("task_id")
                status = data.get("status")
                result = {
                    k: data[k]
                    for k in ["summary", "artifact_path", "stdout_tail", "stderr_tail"]
                    if k in data
                }

                if not task_id:
                    self.send_json(400, {"error": "task_id is required"})
                    return
                if not status:
                    self.send_json(400, {"error": "status is required"})
                    return

                updated = store.update_status(task_id, status, result)
                if not updated:
                    self.send_json(404, {"error": "task not found"})
                    return

                logger.info(f"Task {task_id} updated to status={status}")
                self.send_json(200, {"task": updated})
                return

            self.send_json(404, {"error": "not found"})
        except Exception as e:
            logger.error(f"Error handling POST {path}: {e}")
            self.send_json(500, {"error": str(e)})


def run():
    host = CONFIG["bridge"]["host"]
    port = CONFIG["bridge"]["port"]
    server = HTTPServer((host, port), BridgeHandler)
    logger.info(f"Alpic Task Bridge V1 running on {host}:{port}")
    logger.info(f"Endpoints: POST /task, GET /task/next, POST /task/result, GET /task/{{task_id}}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        server.shutdown()


if __name__ == "__main__":
    run()
