#!/usr/bin/env python3
"""Shared paths and active-profile helpers for the scripts in tools/.

Every tool needs the same four locations and most need to read or write the
active profile. Keeping that in one place means the layout is defined once, and
the active-profile convention from .claude/rules/data-integrity.md is enforced
identically everywhere rather than re-implemented per script.

This module is imported as a sibling (`from common import ...`), which works
because running `python3 tools/<script>.py` puts tools/ on sys.path.
"""
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
PROFILES_DIR = DATA_DIR / "profiles"
ACTIVE_PROFILE_FILE = DATA_DIR / ".active-profile"

# Overrides the active-profile file for one process. data/.active-profile is
# global state, so two sessions working on different people would otherwise
# fight over it; this lets each pin its own without touching the shared file.
PROFILE_ENV_VAR = "RESUME_AI_PROFILE"

# Current schema version. Bump the MAJOR when a change breaks existing
# documents, the MINOR when it is additive.
SCHEMA_VERSION = "1.0"


def get_active_slug() -> str | None:
    """Return the active profile slug, or None if unset.

    Checks the RESUME_AI_PROFILE environment variable first, so a single process
    can pin a profile without disturbing the shared file. Then falls back to
    data/.active-profile.

    An absent file and an empty one both mean "no active profile" -- callers
    should not have to distinguish, since profile_delete blanks the file rather
    than removing it.
    """
    override = os.environ.get(PROFILE_ENV_VAR, "").strip()
    if override:
        return override
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


def resolve_slug(explicit: str | None = None) -> str:
    """Resolve which profile to operate on, or raise with actionable guidance.

    Precedence: an explicit --slug, then RESUME_AI_PROFILE, then
    data/.active-profile, then a sole existing profile.
    """
    if explicit:
        return explicit
    slug = get_active_slug()
    if slug:
        return slug
    if PROFILES_DIR.exists():
        candidates = [
            d.name for d in sorted(PROFILES_DIR.iterdir())
            if d.is_dir() and not d.name.startswith(".")
        ]
        if len(candidates) == 1:
            return candidates[0]
        if not candidates:
            raise ValueError(
                "no profiles exist; create one with tools/profile_create.py"
            )
        raise ValueError(
            f"no active profile and {len(candidates)} exist ({', '.join(candidates)}); "
            f"pass --slug, set {PROFILE_ENV_VAR}, or run tools/profile_switch.py"
        )
    raise ValueError("no profiles directory; create a profile first")
