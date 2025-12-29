#!/usr/bin/env python3
"""Get current version from manifest.json."""

import json
from pathlib import Path

manifest_path = Path("custom_components/israel_transportation/manifest.json")
manifest = json.loads(manifest_path.read_text())
print(manifest["version"])
