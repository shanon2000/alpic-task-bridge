#!/usr/bin/env python
"""Test script that fails with an error."""
import sys

print("About to fail...", file=sys.stderr)
print("Error message", file=sys.stderr)
sys.exit(1)
