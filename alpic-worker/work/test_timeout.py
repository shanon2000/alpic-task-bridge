#!/usr/bin/env python
"""Test script that hangs (times out)."""
import sys
import time

print("Starting long sleep...")
sys.stdout.flush()
time.sleep(60)  # Will be killed by timeout
print("This should not print")
