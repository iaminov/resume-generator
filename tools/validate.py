#!/usr/bin/env python3
"""Validate profile, application, and job-description JSON against the schemas.

.claude/rules/data-integrity.md requires every JSON file written under
data/profiles/ to validate before it is saved. This makes that check runnable
instead of relying on whoever is driving to remember an ad-hoc snippet.

Usage:
    python3 tools/validate.py data/profiles/jane-doe/profile.json
    python3 tools/validate.py data/profiles/jane-doe/applications/*.json
    python3 tools/validate.py --schema application some-record.json
    python3 tools/validate.py --all                  # every JSON in every profile
    python3 tools/validate.py --all --slug jane-doe  # one profile

Exits 0 when everything validates, 1 otherwise, so it can gate a workflow.
Errors report the failing JSON path (e.g. projects[1].url) rather than dumping
the whole document.
"""
import argparse
import json
import sys
from pathlib import Path

import jsonschema

from common import PROFILES_DIR, PROJECT_ROOT, relative_to_root

SCHEMA_DIR = PROJECT_ROOT / "schemas"

SCHEMAS = {
    "profile": SCHEMA_DIR / "profile.schema.json",
    "application": SCHEMA_DIR / "application.schema.json",
    "job-description": SCHEMA_DIR / "job-description.schema.json",
}


def infer_schema(path: Path):
    """Pick a schema from where the file sits, then from what it contains.

    Location is checked first because it is the convention the repo actually
    enforces; content sniffing is a fallback for files being validated before
    they are moved into place.
    """
    parts = [p.lower() for p in path.parts]
    if path.name == "profile.json":
        return "profile"
    if "applications" in parts:
        return "application"
    if "output-job-descriptions" in parts:
        return "job-description"

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    if "person_slug" in data or "professional_summary" in data:
        return "profile"
    if "status_history" in data or "resume_file" in data:
        return "application"
    if "required_skills" in data or "role_summary" in data:
        return "job-description"
    return None


def load_schema(name: str) -> dict:
    return json.loads(SCHEMAS[name].read_text(encoding="utf-8"))


def validate_file(path: Path, schema_name: str = None) -> dict:
    """Validate one file. Returns a result dict; never raises for bad data."""
    result = {"file": relative_to_root(path), "schema": schema_name, "valid": False}

    if not path.exists():
        result["error"] = "file not found"
        return result

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        result["error"] = f"invalid JSON: {e}"
        return result

    name = schema_name or infer_schema(path)
    result["schema"] = name
    if name is None:
        result["error"] = (
            "could not tell which schema applies; pass --schema "
            f"({', '.join(SCHEMAS)})"
        )
        return result

    validator = jsonschema.Draft7Validator(load_schema(name))
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path))
    if not errors:
        result["valid"] = True
        return result

    result["errors"] = [
        {
            "path": ".".join(str(p) for p in e.absolute_path) or "(root)",
            "message": e.message,
        }
        for e in errors[:20]
    ]
    if len(errors) > 20:
        result["errors_truncated"] = len(errors) - 20
    return result


def collect_all(slug: str = None) -> list:
    """Every JSON file under data/profiles/ that a schema covers."""
    roots = [PROFILES_DIR / slug] if slug else (
        sorted(p for p in PROFILES_DIR.iterdir() if p.is_dir())
        if PROFILES_DIR.exists() else []
    )
    found = []
    for root in roots:
        if (root / "profile.json").exists():
            found.append(root / "profile.json")
        for sub in ("applications", "output/output-job-descriptions"):
            found.extend(sorted((root / sub).glob("*.json")))
    return found


def main():
    parser = argparse.ArgumentParser(
        description="Validate profile data against the JSON schemas"
    )
    parser.add_argument("files", nargs="*", help="JSON files to validate")
    parser.add_argument(
        "--schema", choices=sorted(SCHEMAS),
        help="Force a schema instead of inferring it",
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Validate every schema-covered JSON file under data/profiles/",
    )
    parser.add_argument("--slug", help="Limit --all to one profile")
    args = parser.parse_args()

    if args.all:
        targets = collect_all(args.slug)
    elif args.files:
        targets = [Path(f) for f in args.files]
    else:
        parser.error("pass one or more files, or --all")

    if not targets:
        print(json.dumps({"status": "nothing_to_validate", "checked": 0}, indent=2))
        return

    results = [validate_file(p, args.schema) for p in targets]
    failed = [r for r in results if not r["valid"]]

    print(json.dumps({
        "status": "valid" if not failed else "invalid",
        "checked": len(results),
        "failed": len(failed),
        "results": results if failed else [
            {"file": r["file"], "schema": r["schema"], "valid": True} for r in results
        ],
    }, indent=2))

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
