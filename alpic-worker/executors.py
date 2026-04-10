"""
Task Executors - Actual execution logic for supported task types.
Each task type has its own executor function.
"""

import os
import sys
import logging
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Tuple

logger = logging.getLogger("worker")
MAX_OUTPUT_CHARS = 2000  # Max chars for stdout/stderr tails


class ExecutionError(Exception):
    """Raised when task execution fails."""
    def __init__(self, summary: str, stderr: str = ""):
        self.summary = summary
        self.stderr = stderr
        super().__init__(summary)


def normalize_path(path: str, allowed_dirs: list[str], relative_base: str = None) -> Path | None:
    """
    Normalize a path and verify it's within allowed directories.
    Returns Path object if valid, None if path is illegal.

    For relative paths: joins with relative_base if provided, else first allowed_dir, then resolves.
    For absolute paths: resolves directly, then checks against allowed_dirs.
    """
    try:
        p = Path(path)
        if not p.is_absolute():
            base = relative_base if relative_base else (allowed_dirs[0] if allowed_dirs else str(Path.cwd()))
            p = Path(base) / p
        abs_path = p.resolve()
    except Exception:
        return None

    for allowed_dir in allowed_dirs:
        allowed = Path(allowed_dir).resolve()
        try:
            abs_path.relative_to(allowed)
            return abs_path
        except ValueError:
            continue

    return None


def write_file(task_id: str, payload: dict, allowed_dirs: list[str]) -> Tuple[str, str, str, str, str]:
    """
    Execute write_file task.

    Payload:
        - path: relative or absolute path to target file (required)
        - content: string content to write (required)
        - overwrite: if False, fail if file exists (default False)
        - create_dirs: if True, create parent directories (default False)

    Returns: (status, summary, artifact_path, stdout_tail, stderr_tail)
    """
    path = payload.get("path")
    content = payload.get("content")
    overwrite = payload.get("overwrite", False)
    create_dirs = payload.get("create_dirs", False)

    if not path:
        return ("failed", "missing_required_field: path", "", "", "path is required in payload")

    if content is None:
        return ("failed", "missing_required_field: content", "", "", "content is required in payload")

    target_path = normalize_path(path, allowed_dirs, relative_base=allowed_dirs[0])
    if target_path is None:
        logger.warning(f"Task {task_id}: illegal path {path}")
        return ("failed", f"illegal_path: {path} not in allowed directories", "", "", f"path must be inside allowed directories: {allowed_dirs}")

    if target_path.exists():
        if not overwrite:
            logger.warning(f"Task {task_id}: file exists and overwrite=False")
            return ("failed", f"file_exists: {target_path} already exists, overwrite=false", str(target_path), "", "set overwrite=true to allow replacement")

    parent = target_path.parent
    if not parent.exists():
        if create_dirs:
            try:
                parent.mkdir(parents=True, exist_ok=True)
                logger.info(f"Task {task_id}: created parent dir {parent}")
            except Exception as e:
                return ("failed", f"mkdir_failed: {e}", "", "", str(e))
        else:
            logger.warning(f"Task {task_id}: parent dir does not exist, create_dirs=False")
            return ("failed", f"parent_dir_not_found: {parent} does not exist, set create_dirs=true to create", "", "", f"parent directory does not exist: {parent}")

    try:
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"Task {task_id}: wrote {len(content)} bytes to {target_path}")
        return ("done", f"wrote {len(content)} bytes to {target_path}", str(target_path), "", "")
    except Exception as e:
        logger.error(f"Task {task_id}: write failed: {e}")
        return ("failed", f"write_failed: {str(e)}", "", "", str(e))


def run_python(task_id: str, payload: dict, allowed_dirs: list[str], python_path: str = "python", default_timeout: int = 30) -> Tuple[str, str, str, str, str]:
    """
    Execute a Python script in a subprocess.

    Payload:
        - script: path to .py file (required)
        - args: list of string arguments (default [])
        - workdir: working directory for execution (default: script's directory)
        - timeout_seconds: max execution time in seconds (default from config)

    Returns: (status, summary, artifact_path, stdout_tail, stderr_tail)
    """
    script = payload.get("script")
    args = payload.get("args", [])
    workdir = payload.get("workdir")
    timeout_seconds = payload.get("timeout_seconds", default_timeout)

    if not script:
        return ("failed", "missing_required_field: script", "", "", "script is required in payload")

    if not isinstance(args, list):
        return ("failed", "invalid_args: args must be a list", "", "", f"args must be a list, got {type(args).__name__}")

    if not script.endswith(".py"):
        return ("failed", f"invalid_script: {script} must be a .py file", "", "", "script must have .py extension")

    script_path = normalize_path(script, allowed_dirs, relative_base=allowed_dirs[0])
    if script_path is None:
        logger.warning(f"Task {task_id}: illegal script path {script}")
        return ("failed", f"illegal_script_path: {script} not in allowed directories", "", "", "script path must be inside allowed directories")

    if workdir:
        workdir_path = normalize_path(workdir, allowed_dirs)
        if workdir_path is None:
            logger.warning(f"Task {task_id}: illegal workdir {workdir}")
            return ("failed", f"illegal_workdir: {workdir} not in allowed directories", "", "", "workdir must be inside allowed directories")
    else:
        workdir_path = script_path.parent

    cmd = [python_path or sys.executable, str(script_path)] + args
    logger.info(f"Task {task_id}: running {' '.join(cmd)}")

    stdout_file = None
    stderr_file = None
    try:
        stdout_fd, stdout_file = tempfile.mkstemp(suffix=".stdout")
        stderr_fd, stderr_file = tempfile.mkstemp(suffix=".stderr")
        os.close(stdout_fd)
        os.close(stderr_fd)

        with open(stdout_file, "w", encoding="utf-8", errors="replace") as stdout_f:
            with open(stderr_file, "w", encoding="utf-8", errors="replace") as stderr_f:
                proc = subprocess.Popen(
                    cmd,
                    stdout=stdout_f,
                    stderr=stderr_f,
                    cwd=str(workdir_path),
                    env=os.environ.copy(),
                )

                try:
                    poll_interval = 0.5
                    elapsed = 0.0
                    while proc.poll() is None:
                        time.sleep(poll_interval)
                        elapsed += poll_interval
                        if elapsed >= timeout_seconds:
                            proc.kill()
                            proc.wait()
                            logger.warning(f"Task {task_id}: timed out after {timeout_seconds}s")
                            return ("failed", f"timeout: script exceeded {timeout_seconds}s", "", "", f"script timed out after {timeout_seconds} seconds")
                    return_code = proc.returncode
                except Exception as e:
                    proc.kill()
                    proc.wait()
                    return ("failed", f"execution_error: {str(e)}", "", "", str(e))

        try:
            with open(stdout_file, "r", encoding="utf-8", errors="replace") as f:
                stdout_content = f.read()
        except Exception:
            stdout_content = ""

        try:
            with open(stderr_file, "r", encoding="utf-8", errors="replace") as f:
                stderr_content = f.read()
        except Exception:
            stderr_content = ""

        stdout_tail = stdout_content[-MAX_OUTPUT_CHARS:] if stdout_content else ""
        stderr_tail = stderr_content[-MAX_OUTPUT_CHARS:] if stderr_content else ""

        if return_code != 0:
            logger.warning(f"Task {task_id}: script exited with code {return_code}")
            return ("failed", f"script_exited_with_code_{return_code}", "", stdout_tail, stderr_tail)

        summary = "script completed successfully"
        if args:
            summary += f" (args: {args})"
        return ("done", summary, "", stdout_tail, stderr_tail)

    finally:
        for f in [stdout_file, stderr_file]:
            if f and os.path.exists(f):
                try:
                    os.unlink(f)
                except Exception:
                    pass


SUPPORTED_EXECUTORS = {
    "write_file": write_file,
    "run_python": run_python,
}


def run_shell_safe(task_id: str, payload: dict, allowed_dirs: list[str], allowed_commands: list[str], default_timeout: int = 30) -> Tuple[str, str, str, str, str]:
    """
    Execute a whitelisted shell command in a subprocess. Very restricted.

    Payload:
        - command: the command name (must be in allowed_commands whitelist) (required)
        - args: list of string arguments (default [])
        - workdir: working directory (default: first allowed dir)
        - timeout_seconds: max execution time in seconds (default from config)

    Returns: (status, summary, artifact_path, stdout_tail, stderr_tail)
    """
    command = payload.get("command")
    args = payload.get("args", [])
    workdir = payload.get("workdir")
    timeout_seconds = payload.get("timeout_seconds", default_timeout)

    # Validate required fields
    if not command:
        return ("failed", "missing_required_field: command", "", "", "command is required in payload")

    # Validate args is a list
    if not isinstance(args, list):
        return ("failed", "invalid_args: args must be a list", "", "", f"args must be a list, got {type(args).__name__}")

    # Check command is in whitelist
    if command not in allowed_commands:
        logger.warning(f"Task {task_id}: command '{command}' not in whitelist")
        return ("failed", f"command_not_allowed: {command} not in whitelist", "", "", f"allowed commands: {allowed_commands}")

    # Validate workdir
    if workdir:
        workdir_path = normalize_path(workdir, allowed_dirs)
        if workdir_path is None:
            logger.warning(f"Task {task_id}: illegal workdir {workdir}")
            return ("failed", f"illegal_workdir: {workdir} not in allowed directories", "", "", "workdir must be inside allowed directories")
    else:
        workdir_path = Path(allowed_dirs[0]) if allowed_dirs else Path.cwd()

    # Build command
    cmd = [command] + args
    logger.info(f"Task {task_id}: running shell command {' '.join(cmd)}")

    stdout_file = None
    stderr_file = None
    try:
        stdout_fd, stdout_file = tempfile.mkstemp(suffix=".stdout")
        stderr_fd, stderr_file = tempfile.mkstemp(suffix=".stderr")
        os.close(stdout_fd)
        os.close(stderr_fd)

        with open(stdout_file, "w", encoding="utf-8", errors="replace") as stdout_f:
            with open(stderr_file, "w", encoding="utf-8", errors="replace") as stderr_f:
                proc = subprocess.Popen(
                    cmd,
                    stdout=stdout_f,
                    stderr=stderr_f,
                    cwd=str(workdir_path),
                    env=os.environ.copy(),
                    shell=False,  # Always shell=False for safety
                )

                try:
                    poll_interval = 0.5
                    elapsed = 0.0
                    while proc.poll() is None:
                        time.sleep(poll_interval)
                        elapsed += poll_interval
                        if elapsed >= timeout_seconds:
                            proc.kill()
                            proc.wait()
                            logger.warning(f"Task {task_id}: timed out after {timeout_seconds}s")
                            return ("failed", f"timeout: command exceeded {timeout_seconds}s", "", "", f"command timed out after {timeout_seconds} seconds")
                    return_code = proc.returncode
                except Exception as e:
                    proc.kill()
                    proc.wait()
                    return ("failed", f"execution_error: {str(e)}", "", "", str(e))

        try:
            with open(stdout_file, "r", encoding="utf-8", errors="replace") as f:
                stdout_content = f.read()
        except Exception:
            stdout_content = ""

        try:
            with open(stderr_file, "r", encoding="utf-8", errors="replace") as f:
                stderr_content = f.read()
        except Exception:
            stderr_content = ""

        stdout_tail = stdout_content[-MAX_OUTPUT_CHARS:] if stdout_content else ""
        stderr_tail = stderr_content[-MAX_OUTPUT_CHARS:] if stderr_content else ""

        if return_code != 0:
            logger.warning(f"Task {task_id}: command exited with code {return_code}")
            return ("failed", f"command_exited_with_code_{return_code}", "", stdout_tail, stderr_tail)

        summary = f"command '{command}' completed successfully"
        if args:
            summary += f" (args: {args})"
        return ("done", summary, "", stdout_tail, stderr_tail)

    finally:
        for f in [stdout_file, stderr_file]:
            if f and os.path.exists(f):
                try:
                    os.unlink(f)
                except Exception:
                    pass

SUPPORTED_EXECUTORS["run_shell_safe"] = run_shell_safe
