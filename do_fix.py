#!/usr/bin/env python3
import sys

filepath = "/root/limitless-ai/risk_manager.py"

with open(filepath, "r") as f:
    lines = f.readlines()

# Find line 382 (index 381) and check what it has
for i in range(380, 385):
    print(f"Line {i + 1}: {repr(lines[i])}")

# Fix line 382 - change stop_3ct_3ct_3ct to stop_3ct_3ct_3ct (the actual variable name)
# The variable on line 373 is stop_3ct_3ct_3ct
lines[381] = '        "stop_3ct_3ct_3ct": stop_3ct_3ct_3ct,\n'

with open(filepath, "w") as f:
    f.writelines(lines)

print("Fixed!")
