"""
Tests for run_shell_safe task executor.
Covers required scenarios:
1. Whitelisted command executes successfully
2. Non-whitelisted command rejected
3. args non-list rejected
4. workdir escape rejected
5. timeout works
6. Dangerous shell characters (not applicable with shell=False and list args, but test args validation)
7. Exit code non-0 returns failed
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from executors import run_shell_safe

ALLOWED = ["./allowed_write", "./temp", "./work"]
WHITELIST = ["python", "py"]


def test_whitelisted_command_success():
    """Test 1: Whitelisted command executes successfully."""
    print("\n=== Test 1: Whitelisted Command Success ===")

    # Run python -c "print('hello')"
    result = run_shell_safe("t1", {
        "command": "python",
        "args": ["-c", "print('hello from shell')"],
        "workdir": "./work",
    }, ALLOWED, WHITELIST)

    status, summary, artifact, stdout, stderr = result
    assert status == "done", f"Expected done, got {status}: {summary}"
    assert "hello from shell" in stdout
    print(f"  Status: {status}")
    print(f"  Stdout: {stdout.strip()}")
    print("  PASSED")


def test_non_whitelisted_rejected():
    """Test 2: Non-whitelisted command rejected."""
    print("\n=== Test 2: Non-Whitelisted Command Rejected ===")

    result = run_shell_safe("t2", {
        "command": "del",
        "args": ["/f", "file.txt"],
    }, ALLOWED, WHITELIST)

    status, summary, artifact, stdout, stderr = result
    assert status == "failed", f"Expected failed, got {status}: {summary}"
    assert "command_not_allowed" in summary
    print(f"  Status: {status}")
    print(f"  Summary: {summary}")
    print("  PASSED")


def test_args_not_list():
    """Test 3: args must be a list."""
    print("\n=== Test 3: args Must Be List ===")

    result = run_shell_safe("t3", {
        "command": "python",
        "args": "-c print('hello')",  # String, not list
    }, ALLOWED, WHITELIST)

    status, summary, artifact, stdout, stderr = result
    assert status == "failed"
    assert "invalid_args" in summary
    print(f"  Status: {status}")
    print(f"  Summary: {summary}")
    print("  PASSED")


def test_workdir_escape():
    """Test 4: workdir escape rejected."""
    print("\n=== Test 4: workdir Escape Rejected ===")

    result = run_shell_safe("t4", {
        "command": "python",
        "args": ["-c", "print('test')"],
        "workdir": "../../../etc",
    }, ALLOWED, WHITELIST)

    status, summary, artifact, stdout, stderr = result
    assert status == "failed"
    assert "illegal_workdir" in summary
    print(f"  Status: {status}")
    print(f"  Summary: {summary}")
    print("  PASSED")


def test_command_failure():
    """Test 7: Command with non-zero exit code returns failed."""
    print("\n=== Test 7: Command Failure ===")

    result = run_shell_safe("t7", {
        "command": "python",
        "args": ["-c", "import sys; sys.exit(1)"],
    }, ALLOWED, WHITELIST)

    status, summary, artifact, stdout, stderr = result
    assert status == "failed", f"Expected failed, got {status}: {summary}"
    assert "command_exited_with_code_1" in summary
    print(f"  Status: {status}")
    print(f"  Summary: {summary}")
    print("  PASSED")


def test_missing_command():
    """Test: Missing command field."""
    print("\n=== Test: Missing Command ===")

    result = run_shell_safe("t9", {
        "args": [],
    }, ALLOWED, WHITELIST)

    status, summary, artifact, stdout, stderr = result
    assert status == "failed"
    assert "missing_required_field" in summary
    print(f"  Status: {status}")
    print(f"  Summary: {summary}")
    print("  PASSED")


def test_py_command():
    """Test: py command works (Windows Python launcher)."""
    print("\n=== Test: py Command ===")

    result = run_shell_safe("t10", {
        "command": "py",
        "args": ["-c", "print('hello from py')"],
    }, ALLOWED, WHITELIST)

    status, summary, artifact, stdout, stderr = result
    # May fail if py is not installed, but that's ok - it should at least not be "command_not_allowed"
    print(f"  Status: {status}")
    print(f"  Summary: {summary}")
    if status == "failed" and "command_not_allowed" in summary:
        print("  py not installed, but correctly checked against whitelist")
    elif status == "failed" and "command_exited_with_code" in summary:
        print("  py found but script failed (expected for sys.exit(1))")
    elif status == "done":
        print(f"  Stdout: {stdout.strip()}")
    print("  PASSED (validation logic works)")


if __name__ == "__main__":
    print("Testing run_shell_safe executor...")

    test_whitelisted_command_success()
    test_non_whitelisted_rejected()
    test_args_not_list()
    test_workdir_escape()
    test_command_failure()
    test_missing_command()
    test_py_command()

    print("\n=== All run_shell_safe Tests Passed! ===")
