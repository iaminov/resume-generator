#!/usr/bin/env python3
"""Create a new person profile directory and set it as the active profile.

Usage:
    python3 tools/profile_create.py "Jane Doe"
    python3 tools/profile_create.py --slug jane-doe "Jane Doe"
"""
import argparse
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
PROFILES_DIR = DATA_DIR / "profiles"
ACTIVE_PROFILE_FILE = DATA_DIR / ".active-profile"

SUBDIRS = [
    "input/input-resumes",
    "input/input-job-postings",
    "applications",
    "output/output-job-descriptions",
    "output/output-generated-resumes",
]


def name_to_slug(name: str) -> str:
    """Convert a full name to a URL-safe slug."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug


def main():
    parser = argparse.ArgumentParser(description="Create a new person profile directory")
    parser.add_argument("name", help="Person's full name (e.g., 'Jane Doe')")
    parser.add_argument("--slug", help="Override the auto-generated slug")
    args = parser.parse_args()

    slug = args.slug or name_to_slug(args.name)

    if not re.match(r"^[a-z0-9-]+$", slug):
        print(f"Error: Invalid slug '{slug}'. Must match ^[a-z0-9-]+$", file=sys.stderr)
        sys.exit(1)

    profile_dir = PROFILES_DIR / slug

    if profile_dir.exists():
        print(f"Error: Profile directory already exists: {profile_dir}", file=sys.stderr)
        print(f"To switch to it, run: python3 tools/profile_switch.py {slug}", file=sys.stderr)
        sys.exit(1)

    # Create directory structure
    profile_dir.mkdir(parents=True, exist_ok=True)
    for subdir in SUBDIRS:
        sub_path = profile_dir / subdir
        sub_path.mkdir(parents=True, exist_ok=True)
        (sub_path / ".gitkeep").touch()

    # Set as active profile
    ACTIVE_PROFILE_FILE.write_text(slug, encoding="utf-8")

    # Output result as JSON for easy parsing by caller
    result = {
        "status": "created",
        "name": args.name,
        "slug": slug,
        "profile_dir": str(profile_dir.relative_to(PROJECT_ROOT)),
        "active": True,
        "subdirs": [str((profile_dir / d).relative_to(PROJECT_ROOT)) for d in SUBDIRS],
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
