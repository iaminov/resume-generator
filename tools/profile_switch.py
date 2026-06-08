#!/usr/bin/env python3
"""Switch the active profile or list available profiles.

Usage:
    python3 tools/profile_switch.py              # list profiles
    python3 tools/profile_switch.py jane-doe       # switch to jane-doe
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
PROFILES_DIR = DATA_DIR / "profiles"
ACTIVE_PROFILE_FILE = DATA_DIR / ".active-profile"


def get_active_slug() -> Optional[str]:
    """Read the current active profile slug."""
    if ACTIVE_PROFILE_FILE.exists():
        slug = ACTIVE_PROFILE_FILE.read_text(encoding="utf-8").strip()
        return slug if slug else None
    return None


def list_profiles() -> List[Dict[str, Any]]:
    """List all profile directories with their status."""
    if not PROFILES_DIR.exists():
        return []

    active = get_active_slug()
    profiles = []

    for entry in sorted(PROFILES_DIR.iterdir()):
        if not entry.is_dir() or entry.name.startswith("."):
            continue

        profile_json = entry / "profile.json"
        has_profile = profile_json.exists()

        # Try to read name from profile.json
        name = None
        if has_profile:
            try:
                data = json.loads(profile_json.read_text(encoding="utf-8"))
                name = data.get("name", {}).get("full")
            except (json.JSONDecodeError, KeyError):
                pass

        # Count files in subdirs
        source_count = len(list((entry / "source-resumes").glob("*"))) if (entry / "source-resumes").exists() else 0
        source_count -= 1 if (entry / "source-resumes" / ".gitkeep").exists() else 0
        app_count = len(list((entry / "applications").glob("*.json"))) if (entry / "applications").exists() else 0

        profiles.append({
            "slug": entry.name,
            "name": name,
            "active": entry.name == active,
            "has_profile": has_profile,
            "source_resumes": max(0, source_count),
            "applications": app_count,
        })

    return profiles


def main():
    parser = argparse.ArgumentParser(description="Switch active profile or list profiles")
    parser.add_argument("slug", nargs="?", help="Profile slug to switch to (omit to list)")
    args = parser.parse_args()

    if args.slug is None:
        # List mode
        profiles = list_profiles()
        if not profiles:
            print(json.dumps({"status": "empty", "message": "No profiles found. Run profile_create.py first."}, indent=2))
            sys.exit(0)

        print(json.dumps({"status": "list", "profiles": profiles}, indent=2))
        sys.exit(0)

    # Switch mode
    target_dir = PROFILES_DIR / args.slug
    if not target_dir.exists() or not target_dir.is_dir():
        print(f"Error: Profile '{args.slug}' not found in {PROFILES_DIR}", file=sys.stderr)
        available = [d.name for d in PROFILES_DIR.iterdir() if d.is_dir() and not d.name.startswith(".")]
        if available:
            print(f"Available profiles: {', '.join(available)}", file=sys.stderr)
        sys.exit(1)

    previous = get_active_slug()
    ACTIVE_PROFILE_FILE.write_text(args.slug, encoding="utf-8")

    result = {
        "status": "switched",
        "slug": args.slug,
        "previous": previous,
        "has_profile": (target_dir / "profile.json").exists(),
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
