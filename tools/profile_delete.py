#!/usr/bin/env python3
"""Delete a person's profile directory and all associated data.

Usage:
    python3 tools/profile_delete.py jane-doe          # show what would be deleted
    python3 tools/profile_delete.py jane-doe --confirm # actually delete
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
PROFILES_DIR = DATA_DIR / "profiles"
ACTIVE_PROFILE_FILE = DATA_DIR / ".active-profile"


def get_active_slug() -> str | None:
    if ACTIVE_PROFILE_FILE.exists():
        slug = ACTIVE_PROFILE_FILE.read_text(encoding="utf-8").strip()
        return slug if slug else None
    return None


def count_files(directory: Path, pattern: str = "*") -> int:
    """Count files matching pattern, excluding .gitkeep."""
    if not directory.exists():
        return 0
    return len([f for f in directory.glob(pattern) if f.name != ".gitkeep" and f.is_file()])


def inventory(profile_dir: Path) -> dict:
    """Build an inventory of what exists in the profile directory."""
    return {
        "has_profile_json": (profile_dir / "profile.json").exists(),
        "input_resumes": count_files(profile_dir / "input" / "input-resumes"),
        "input_job_postings": count_files(profile_dir / "input" / "input-job-postings"),
        "applications": count_files(profile_dir / "applications", "*.json"),
        "output_job_descriptions": count_files(profile_dir / "output" / "output-job-descriptions", "*.json"),
        "output_generated_resumes": count_files(profile_dir / "output" / "output-generated-resumes", "*.docx"),
    }


def main():
    parser = argparse.ArgumentParser(description="Delete a person's profile directory")
    parser.add_argument("slug", help="Profile slug to delete")
    parser.add_argument("--confirm", action="store_true",
                        help="Actually delete (without this flag, only shows what would be deleted)")
    args = parser.parse_args()

    profile_dir = PROFILES_DIR / args.slug
    if not profile_dir.exists() or not profile_dir.is_dir():
        print(f"Error: Profile '{args.slug}' not found in {PROFILES_DIR}", file=sys.stderr)
        sys.exit(1)

    is_active = get_active_slug() == args.slug
    inv = inventory(profile_dir)

    if not args.confirm:
        # Dry run — show what would be deleted
        result = {
            "status": "dry_run",
            "slug": args.slug,
            "is_active": is_active,
            "inventory": inv,
            "message": f"Run with --confirm to delete: python3 tools/profile_delete.py {args.slug} --confirm",
        }
        print(json.dumps(result, indent=2))
        sys.exit(0)

    # Actually delete
    shutil.rmtree(profile_dir)

    # Clear active profile if this was it
    active_cleared = False
    if is_active:
        ACTIVE_PROFILE_FILE.write_text("", encoding="utf-8")
        active_cleared = True

    result = {
        "status": "deleted",
        "slug": args.slug,
        "inventory": inv,
        "active_cleared": active_cleared,
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
