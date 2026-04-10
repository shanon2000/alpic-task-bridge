"""
Tests for write_file task executor.
Covers all 7 required scenarios:
1. New file written successfully
2. overwrite=false fails when file exists
3. overwrite=true succeeds when file exists
4. Illegal paths are rejected
5. Missing fields cause failure
6. Chinese content written successfully
7. create_dirs behaves correctly
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path

# Add worker dir to path
sys.path.insert(0, str(Path(__file__).parent))

from executors import write_file, normalize_path


ALLOWED = ["./allowed_write", "./temp", "./work"]


def test_new_file_success():
    """Test 1: New file written successfully."""
    print("\n=== Test 1: New File Write Success ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        allowed = [str(Path(tmpdir) / "allowed")]
        os.makedirs(Path(tmpdir) / "allowed")

        result = write_file("t1", {
            "path": str(Path(tmpdir) / "allowed" / "test.txt"),
            "content": "Hello World",
            "overwrite": False
        }, allowed)

        status, summary, artifact, stdout, stderr = result
        assert status == "done", f"Expected done, got {status}: {summary}"
        assert "Hello World" in Path(artifact).read_text(encoding="utf-8")
        print(f"  Status: {status}")
        print(f"  Summary: {summary}")
        print(f"  Artifact: {artifact}")
    print("  PASSED")


def test_overwrite_false_fails():
    """Test 2: overwrite=false fails when file exists."""
    print("\n=== Test 2: overwrite=false Fails on Existing File ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        allowed = [str(Path(tmpdir) / "allowed")]
        os.makedirs(Path(tmpdir) / "allowed")
        file_path = Path(tmpdir) / "allowed" / "existing.txt"
        file_path.write_text("original content", encoding="utf-8")

        result = write_file("t2", {
            "path": str(file_path),
            "content": "new content",
            "overwrite": False
        }, allowed)

        status, summary, artifact, stdout, stderr = result
        assert status == "failed", f"Expected failed, got {status}"
        assert "file_exists" in summary
        print(f"  Status: {status}")
        print(f"  Summary: {summary}")
        print(f"  Stderr: {stderr}")
    print("  PASSED")


def test_overwrite_true_succeeds():
    """Test 3: overwrite=true succeeds when file exists."""
    print("\n=== Test 3: overwrite=true Succeeds ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        allowed = [str(Path(tmpdir) / "allowed")]
        os.makedirs(Path(tmpdir) / "allowed")
        file_path = Path(tmpdir) / "allowed" / "existing.txt"
        file_path.write_text("original content", encoding="utf-8")

        result = write_file("t3", {
            "path": str(file_path),
            "content": "replaced content",
            "overwrite": True
        }, allowed)

        status, summary, artifact, stdout, stderr = result
        assert status == "done", f"Expected done, got {status}: {summary}"
        assert Path(artifact).read_text(encoding="utf-8") == "replaced content"
        print(f"  Status: {status}")
        print(f"  Summary: {summary}")
    print("  PASSED")


def test_illegal_path_rejected():
    """Test 4: Illegal paths are rejected."""
    print("\n=== Test 4: Illegal Path Rejected ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        allowed = [str(Path(tmpdir) / "allowed")]
        os.makedirs(Path(tmpdir) / "allowed")

        # Try to escape with ..
        result = write_file("t4", {
            "path": str(Path(tmpdir) / "allowed" / ".." / ".." / "secret.txt"),
            "content": "should not be written",
            "overwrite": True
        }, allowed)

        status, summary, artifact, stdout, stderr = result
        assert status == "failed", f"Expected failed, got {status}"
        assert "illegal_path" in summary
        print(f"  Status: {status}")
        print(f"  Summary: {summary}")

        # Verify file was NOT written outside allowed dir
        secret = Path(tmpdir) / "secret.txt"
        assert not secret.exists(), "File should not exist outside allowed dir!"
        print("  File was correctly NOT written")
    print("  PASSED")


def test_missing_fields_fail():
    """Test 5: Missing required fields cause failure."""
    print("\n=== Test 5: Missing Fields Fail ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        allowed = [str(Path(tmpdir) / "allowed")]
        os.makedirs(Path(tmpdir) / "allowed")

        # Missing path
        result = write_file("t5a", {"content": "hello"}, allowed)
        status, summary, _, _, _ = result
        assert status == "failed" and "path" in summary
        print(f"  Missing path: {status} - {summary}")

        # Missing content
        result = write_file("t5b", {"path": str(Path(tmpdir) / "allowed" / "f.txt")}, allowed)
        status, summary, _, _, stderr = result
        assert status == "failed" and "content" in summary
        print(f"  Missing content: {status} - {summary}")
    print("  PASSED")


def test_chinese_content():
    """Test 6: Chinese content written successfully."""
    print("\n=== Test 6: Chinese Content ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        allowed = [str(Path(tmpdir) / "allowed")]
        os.makedirs(Path(tmpdir) / "allowed")

        chinese = "你好世界\n这是中文内容\nHello 世界"

        result = write_file("t6", {
            "path": str(Path(tmpdir) / "allowed" / "中文.txt"),
            "content": chinese,
            "overwrite": True
        }, allowed)

        status, summary, artifact, stdout, stderr = result
        assert status == "done", f"Expected done, got {status}: {summary}"
        assert Path(artifact).read_text(encoding="utf-8") == chinese
        print(f"  Status: {status}")
        print(f"  Content verified: {len(chinese)} chars written correctly")
    print("  PASSED")


def test_create_dirs():
    """Test 7: create_dirs behaves correctly."""
    print("\n=== Test 7: create_dirs ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        allowed = [str(Path(tmpdir) / "allowed")]
        os.makedirs(Path(tmpdir) / "allowed")

        # create_dirs=false (default) should fail if parent doesn't exist
        nested = str(Path(tmpdir) / "allowed" / "a" / "b" / "c" / "file.txt")
        result = write_file("t7a", {
            "path": nested,
            "content": "should not create",
            "overwrite": True,
            "create_dirs": False
        }, allowed)

        status, summary, _, _, _ = result
        assert status == "failed" and "parent_dir_not_found" in summary
        print(f"  create_dirs=False (default): {status} - {summary}")

        # create_dirs=true should succeed
        result = write_file("t7b", {
            "path": nested,
            "content": "nested content",
            "overwrite": True,
            "create_dirs": True
        }, allowed)

        status, summary, artifact, stdout, stderr = result
        assert status == "done", f"Expected done, got {status}: {summary}"
        assert Path(artifact).read_text(encoding="utf-8") == "nested content"
        print(f"  create_dirs=True: {status} - {summary}")
    print("  PASSED")


def test_normalize_path():
    """Test path normalization edge cases."""
    print("\n=== Test: Path Normalization ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        allowed_base = Path(tmpdir) / "project"
        allowed = [str(allowed_base)]
        allowed_base.mkdir()

        # Normal relative path
        p = normalize_path("subdir/file.txt", allowed)
        assert p is not None
        assert "subdir" in str(p)
        print(f"  Relative path OK: {p}")

        # Absolute path within allowed
        abs_path = allowed_base / "abs_file.txt"
        p = normalize_path(str(abs_path), allowed)
        assert p is not None
        print(f"  Absolute in allowed OK: {p}")

        # Escape with ..
        p = normalize_path(str(allowed_base / ".." / "outside.txt"), allowed)
        assert p is None
        print("  Escape with .. correctly rejected")

        # Windows-style escape
        p = normalize_path(str(allowed_base / ".." / ".." / "secret.txt"), allowed)
        assert p is None
        print("  Deep escape correctly rejected")
    print("  PASSED")


if __name__ == "__main__":
    print("Testing write_file executor...")

    test_new_file_success()
    test_overwrite_false_fails()
    test_overwrite_true_succeeds()
    test_illegal_path_rejected()
    test_missing_fields_fail()
    test_chinese_content()
    test_create_dirs()
    test_normalize_path()

    print("\n=== All write_file Tests Passed! ===")
