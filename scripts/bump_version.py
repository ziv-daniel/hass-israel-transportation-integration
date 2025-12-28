#!/usr/bin/env python3
"""Bump version in manifest.json."""

import json
import sys
from pathlib import Path

if len(sys.argv) != 2:
    print("Usage: bump_version.py NEW_VERSION")
    sys.exit(1)

new_version = sys.argv[1]
manifest_path = Path("custom_components/silent_bus/manifest.json")

manifest = json.loads(manifest_path.read_text())
manifest["version"] = new_version
manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

print(f"Updated version to {new_version}")
