#!/usr/bin/env python3
"""Add automated update entry to CHANGELOG.md."""

import argparse
from datetime import datetime
from pathlib import Path

def update_changelog(version: str, message: str):
    """Add new version entry to CHANGELOG.md.

    Args:
        version: Version number (e.g., "1.3.2")
        message: Change description
    """
    changelog_path = Path("CHANGELOG.md")
    content = changelog_path.read_text()

    # Find insertion point (after # Changelog header)
    lines = content.splitlines()
    insert_idx = 0
    for i, line in enumerate(lines):
        if line.startswith("## ["):
            insert_idx = i
            break

    # Create new entry
    today = datetime.now().strftime("%Y-%m-%d")
    new_entry = f"""## [{version}] - {today}

### Changed
- {message}
- Updated Israeli transit station data from government GTFS feed
- Station count: ~30,000 stops across all major cities

"""

    # Insert new entry
    lines.insert(insert_idx, new_entry)

    # Write back
    changelog_path.write_text('\n'.join(lines))
    print(f"Updated CHANGELOG.md with version {version}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--message", required=True)
    args = parser.parse_args()

    update_changelog(args.version, args.message)
