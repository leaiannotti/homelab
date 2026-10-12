#!/usr/bin/env python3
"""Mask KEY=value lines in `ansible-playbook --diff` output.

Values are replaced by a short sha256 prefix, so you can tell whether a value
changed (different hash) or only moved (same hash) without exposing secrets.

Usage:
  ansible-playbook ... --check --diff | ./mask-env-diff.py
"""
import hashlib
import re
import sys

LINE = re.compile(r"^([ +-]?)([A-Za-z_][A-Za-z0-9_]*)=(.*)$")

for line in sys.stdin:
    m = LINE.match(line.rstrip("\n"))
    if m:
        digest = hashlib.sha256(m[3].encode()).hexdigest()[:8]
        print(f"{m[1]}{m[2]}=<{digest}>")
    else:
        print(line, end="")
