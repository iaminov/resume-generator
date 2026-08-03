#!/usr/bin/env python3
"""Shared paths and active-profile helpers for the scripts in tools/.

Every tool needs the same four locations and most need to read or write the
active profile. Keeping that in one place means the layout is defined once, and
the active-profile convention from .claude/rules/data-integrity.md is enforced
identically everywhere rather than re-implemented per script.

This module is imported as a sibling (`from common import ...`), which works
because running `python3 tools/<script>.py` puts tools/ on sys.path.
"""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
PROFILES_DIR = DATA_DIR / "profiles"
ACTIVE_PROFILE_FILE = DATA_DIR / ".active-profile"


def get_active_slug() -> str | None:
    """Return the active profile slug, or None if unset.

    An absent file and an empty one both mean "no active profile" -- callers
    should not have to distinguish, since profile_delete blanks the file rather
    than removing it.
    """
    if ACTIVE_PROFILE_FILE.exists():
        slug = ACTIVE_PROFILE_FILE.read_text(encoding="utf-8").strip()
        return slug or None
    return None


def set_active_slug(slug: str) -> None:
    """Set the active profile. Pass "" to clear it."""
    ACTIVE_PROFILE_FILE.parent.mkdir(parents=True, exist_ok=True)
    ACTIVE_PROFILE_FILE.write_text(slug, encoding="utf-8")


def profile_dir(slug: str) -> Path:
    """Return the root directory for a profile. Does not check existence."""
    return PROFILES_DIR / slug


def relative_to_root(path: Path) -> str:
    """Render a path relative to the project root for display in JSON output."""
    path = Path(path)
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)
