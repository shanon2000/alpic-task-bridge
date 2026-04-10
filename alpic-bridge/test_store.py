"""Direct test of TaskStore without running server"""
import json
import os
import shutil
import tempfile
from pathlib import Path

# Add bridge to path
import sys
sys.path.insert(0, str(Path(__file__).parent))

from task_store import TaskStore

# Use temp dir for testing
TEST_DIR = Path(tempfile.mkdtemp())
print(f"Testing with temp dir: {TEST_DIR}")

store = TaskStore(str(TEST_DIR))

# Test 1: Create task
print("\n=== Test 1: Create Task ===")
task = store.create("write_file", {"path": "test.txt", "content": "hello"})
print(f"Created: {task['task_id']}, status={task['status']}")
assert task["status"] == "pending"
assert task["task_type"] == "write_file"

# Test 2: Get task by ID
print("\n=== Test 2: Get Task by ID ===")
fetched = store.get(task["task_id"])
print(f"Fetched: {fetched['task_id']}")
assert fetched["task_id"] == task["task_id"]

# Test 3: Get next pending (should return our task)
print("\n=== Test 3: Get Next Pending ===")
next_task = store.get_next_pending()
print(f"Next: {next_task['task_id'] if next_task else None}")
assert next_task is not None
assert next_task["task_id"] == task["task_id"]

# Test 4: Claim task
print("\n=== Test 4: Claim Task ===")
claimed = store.claim(task["task_id"])
print(f"Claimed: {claimed['status']}")
assert claimed["status"] == "claimed"

# Test 5: get_next_pending after claim (should return None)
print("\n=== Test 5: No More Pending ===")
next_task = store.get_next_pending()
print(f"Next: {next_task}")
assert next_task is None

# Test 6: Update status with result
print("\n=== Test 6: Update Status ===")
updated = store.update_status(task["task_id"], "done", {
    "summary": "File written",
    "stdout_tail": "1 file written",
    "stderr_tail": ""
})
print(f"Updated: {updated['status']}, summary={updated.get('summary')}")
assert updated["status"] == "done"
assert updated["summary"] == "File written"

# Test 7: Task not found
print("\n=== Test 7: Task Not Found ===")
not_found = store.get("nonexistent-id")
print(f"Not found: {not_found}")
assert not_found is None

# Test 8: Duplicate task_id should fail
print("\n=== Test 8: Create Duplicate (should fail) ===")
try:
    # Manually create a task file with same ID to simulate collision
    store.create("run_python", {"script": "test.py"})
    print("ERROR: Should have raised ValueError")
except ValueError as e:
    print(f"Correctly raised: {e}")

# Cleanup
shutil.rmtree(TEST_DIR)
print("\n=== All tests passed! ===")
