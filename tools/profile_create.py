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

from common import PROFILES_DIR, PROJECT_ROOT, set_active_slug

SUBDIRS = [
    "input/input-resumes",
    "input/input-job-postings",
    "input/input-job-postings/processed",
    "input/input-voice-samples",
    "applications",
    "output/output-job-descriptions",
    "output/output-generated-resumes",
    "output/output-cover-letters",
]


VOICE_SAMPLES_README = """# Voice Samples (optional)

Drop your own writing here and `/create-cover-letter` will match how you
actually write instead of using a generic professional voice.

**This folder is optional.** Leave it empty and cover letters still work — you
will simply get a clear, neutral default voice.

## What to put here

- A past cover letter is ideal — same format, same register.
- Anything substantial you wrote also works: a personal statement, a detailed
  email, a blog post, a long message explaining something you built.
- PDF, DOCX, TXT, and MD are all readable.
- One good sample is enough; more is better. Under ~150 words gives a weak
  signal.

## Two rules

1. **It must be your own writing.** An article you saved or an email someone
   sent you is not your voice.
2. **Samples supply voice only, never facts.** Every factual claim in a
   generated letter is checked against `profile.json`, so a stale or
   embellished claim in an old letter will not make it through.
"""


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

    # The voice-samples folder is optional, so its purpose is not self-evident
    # from the name alone. Leave a note explaining it rather than an empty dir.
    (profile_dir / "input" / "input-voice-samples" / "README.md").write_text(
        VOICE_SAMPLES_README, encoding="utf-8"
    )

    # Set as active profile
    set_active_slug(slug)

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
