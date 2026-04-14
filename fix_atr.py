#!/usr/bin/env python3
import re

with open("/root/limitless-ai/risk_manager.py", "r") as f:
    content = f.read()

# Find and print lines around the issue
lines = content.split("\n")
for i, line in enumerate(lines):
    if "stop_loss_pct" in line and i > 370 and i < 390:
        print(f"Line {i + 1}: {repr(line)}")

# Fix: The issue is line 382 has stop_loss_pct but should be stop_pct
# Let's find it and fix it
content = content.replace(
    '"stop_loss_pct": stop_loss_pct,', '"stop_loss_pct": stop_pct,'
)

with open("/root/limitless-ai/risk_manager.py", "w") as f:
    f.write(content)

print("Fixed!")
