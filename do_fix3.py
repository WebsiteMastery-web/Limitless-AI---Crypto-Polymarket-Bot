#!/usr/bin/env python3
filepath = "/root/limitless-ai/risk_manager.py"

with open(filepath, "r") as f:
    lines = f.readlines()

# Find and fix lines
for i, line in enumerate(lines):
    if i == 381 and "stop_3ct_3ct_3ct" in line:
        lines[i] = '        "stop_3ct_3ct_3ct": 3.5,\n'
        print(f"Fixed line {i + 1}")

with open(filepath, "w") as f:
    f.writelines(lines)

print("Done")
