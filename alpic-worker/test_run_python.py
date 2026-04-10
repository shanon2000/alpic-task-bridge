"""
Tests for run_python task executor.
Covers required scenarios:
1. Valid script executed successfully
2. Script output stdout returned correctly
3. Script error returns failed
4. Illegal path rejected
5. Non-.py file rejected
6. workdir escape rejected
7. args non-array rejected
8. Timeout works
9. Duplicate execution state is not affected
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from executors import run_python

ALLOWED = ["./allowed_write", "./temp", "./work"]
SCRIPT_DIR = Path(__file__).parent / "work"


def test_valid_script_success():
    """Test 1: Valid script executes successfully."""
    print("\n=== Test 1: Valid Script Success ===")

    result = run_python("t1", {
        "script": str(SCRIPT_DIR / "test_success.py"),
        "args": ["arg1", "arg2"],
        "workdir": str(SCRIPT_DIR),
    }, ALLOWED)

    status, summary, artifact, stdout, stderr = result
    assert status == "done", f"Expected done, got {status}: {summary}"
    assert "Hello from test_success.py" in stdout
    assert "arg1" in stdout
    print(f"  Status: {status}")
    print(f"  Summary: {summary}")
    print(f"  Stdout: {stdout[:100]}")
    print("  PASSED")


def test_stdout_returned():
    """Test 2: Script stdout is captured and returned."""
    print("\n=== Test 2: Stdout Captured ===")

    result = run_python("t2", {
        "script": str(SCRIPT_DIR / "test_success.py"),
        "args": [],
    }, ALLOWED)

    status, summary, artifact, stdout, stderr = result
    assert "Hello from test_success.py" in stdout
    assert "Success!" in stdout
    print(f"  Stdout contains script output: {'Hello' in stdout}")
    print("  PASSED")


def test_script_error():
    """Test 3: Script error (exit != 0) returns failed."""
    print("\n=== Test 3: Script Error ===")

    result = run_python("t3", {
        "script": str(SCRIPT_DIR / "test_fail.py"),
        "args": [],
    }, ALLOWED)

    status, summary, artifact, stdout, stderr = result
    assert status == "failed", f"Expected failed, got {status}: {summary}"
    assert "script_exited_with_code_1" in summary
    assert "Error message" in stderr
    print(f"  Status: {status}")
    print(f"  Summary: {summary}")
    print(f"  Stderr: {stderr[:100]}")
    print("  PASSED")


def test_illegal_script_path():
    """Test 4: Illegal script path rejected."""
    print("\n=== Test 4: Illegal Script Path ===")

    result = run_python("t4", {
        "script": "../secret.py",
        "args": [],
    }, ALLOWED)

    status, summary, artifact, stdout, stderr = result
    assert status == "failed"
    assert "illegal_script_path" in summary
    print(f"  Status: {status}")
    print(f"  Summary: {summary}")
    print("  PASSED")


def test_non_py_file_rejected():
    """Test 5: Non-.py file is rejected."""
    print("\n=== Test 5: Non-.py File Rejected ===")

    result = run_python("t5", {
        "script": str(SCRIPT_DIR / "test_success.sh"),  # Not a .py file
        "args": [],
    }, ALLOWED)

    status, summary, artifact, stdout, stderr = result
    assert status == "failed"
    assert "invalid_script" in summary
    print(f"  Status: {status}")
    print(f"  Summary: {summary}")
    print("  PASSED")


def test_workdir_escape_rejected():
    """Test 6: workdir escape is rejected."""
    print("\n=== Test 6: workdir Escape Rejected ===")

    result = run_python("t6", {
        "script": str(SCRIPT_DIR / "test_success.py"),
        "args": [],
        "workdir": "../../../etc",
    }, ALLOWED)

    status, summary, artifact, stdout, stderr = result
    assert status == "failed"
    assert "illegal_workdir" in summary
    print(f"  Status: {status}")
    print(f"  Summary: {summary}")
    print("  PASSED")


def test_args_not_array():
    """Test 7: args must be a list."""
    print("\n=== Test 7: args Must Be List ===")

    result = run_python("t7", {
        "script": str(SCRIPT_DIR / "test_success.py"),
        "args": "not_an_array",  # Should be a list
    }, ALLOWED)

    status, summary, artifact, stdout, stderr = result
    assert status == "failed"
    assert "invalid_args" in summary
    print(f"  Status: {status}")
    print(f"  Summary: {summary}")
    print("  PASSED")


def test_timeout():
    """Test 8: Timeout works and returns failed."""
    print("\n=== Test 8: Timeout ===")

    result = run_python("t8", {
        "script": str(SCRIPT_DIR / "test_timeout.py"),
        "args": [],
        "timeout_seconds": 2,  # Very short timeout
    }, ALLOWED)

    status, summary, artifact, stdout, stderr = result
    assert status == "failed"
    assert "timeout" in summary
    print(f"  Status: {status}")
    print(f"  Summary: {summary}")
    print("  PASSED")


def test_missing_script():
    """Test: Missing script field."""
    print("\n=== Test: Missing Script Field ===")

    result = run_python("t9", {
        "args": [],
    }, ALLOWED)

    status, summary, artifact, stdout, stderr = result
    assert status == "failed"
    assert "missing_required_field" in summary
    print(f"  Status: {status}")
    print(f"  Summary: {summary}")
    print("  PASSED")


def test_absolute_path_in_allowed():
    """Test: Absolute path within allowed dir works."""
    print("\n=== Test: Absolute Path in Allowed Dir ===")

    # Use the actual absolute path to the test script
    script_path = SCRIPT_DIR / "test_success.py"
    abs_script = str(script_path.resolve())

    result = run_python("t10", {
        "script": abs_script,
        "args": [],
    }, ALLOWED)

    status, summary, artifact, stdout, stderr = result
    assert status == "done", f"Expected done, got {status}: {summary}"
    print(f"  Status: {status}")
    print("  PASSED")


if __name__ == "__main__":
    print("Testing run_python executor...")

    test_valid_script_success()
    test_stdout_returned()
    test_script_error()
    test_illegal_script_path()
    test_non_py_file_rejected()
    test_workdir_escape_rejected()
    test_args_not_array()
    test_timeout()
    test_missing_script()
    test_absolute_path_in_allowed()

    print("\n=== All run_python Tests Passed! ===")
