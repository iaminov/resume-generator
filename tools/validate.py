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
import re
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


# --------------------------------------------------------------------------
# Strict checks
#
# data-integrity.md states requirements JSON Schema cannot express: every entry
# traces to a source file, dates are ISO 8601, proficiency is inferred from
# evidence rather than assumed. A document can satisfy the schema completely and
# still break all three, so these are checked separately.
# --------------------------------------------------------------------------

ISO_DATE = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")


def _iso_date_problems(entries, label, fields=("start_date", "end_date", "date_obtained")):
    problems = []
    for i, entry in enumerate(entries or []):
        if not isinstance(entry, dict):
            continue
        for field in fields:
            value = entry.get(field)
            if value in (None, ""):
                continue
            if not ISO_DATE.match(str(value)):
                problems.append({
                    "path": f"{label}[{i}].{field}",
                    "message": f"'{value}' is not ISO 8601 (YYYY, YYYY-MM or YYYY-MM-DD)",
                })
    return problems


def strict_profile_problems(data: dict) -> list:
    """Requirements from data-integrity.md that the schema cannot enforce."""
    problems = []

    for label in ("skills", "experience", "education", "certifications", "projects"):
        for i, entry in enumerate(data.get(label) or []):
            if not isinstance(entry, dict):
                continue
            if not (entry.get("source_file") or "").strip():
                name = entry.get("name") or entry.get("company") or entry.get("institution") or "?"
                problems.append({
                    "path": f"{label}[{i}].source_file",
                    "message": f"missing source_file (entry: {name!r}) — every entry must "
                               f"trace to an input resume",
                })
            if "/" in str(entry.get("source_file") or "") or "\\" in str(entry.get("source_file") or ""):
                problems.append({
                    "path": f"{label}[{i}].source_file",
                    "message": "source_file must be a bare filename, not a path",
                })

    problems += _iso_date_problems(data.get("experience"), "experience")
    problems += _iso_date_problems(data.get("education"), "education")
    problems += _iso_date_problems(data.get("certifications"), "certifications")

    for i, skill in enumerate(data.get("skills") or []):
        if not isinstance(skill, dict):
            continue
        if skill.get("proficiency") and not (skill.get("evidence") or "").strip():
            problems.append({
                "path": f"skills[{i}].evidence",
                "message": f"skill {skill.get('name')!r} claims proficiency "
                           f"{skill.get('proficiency')!r} with no evidence — proficiency "
                           f"must be inferred from evidence, not assumed",
            })

    for i, exp in enumerate(data.get("experience") or []):
        if not isinstance(exp, dict):
            continue
        if exp.get("is_current") and exp.get("end_date"):
            problems.append({
                "path": f"experience[{i}]",
                "message": "marked is_current but has an end_date",
            })
        start, end = exp.get("start_date"), exp.get("end_date")
        if start and end and str(end) < str(start):
            problems.append({
                "path": f"experience[{i}]",
                "message": f"end_date {end} precedes start_date {start}",
            })

    return problems


def strict_application_problems(data: dict) -> list:
    problems = []
    history = data.get("status_history") or []
    if history and data.get("status") and history[-1].get("status") != data["status"]:
        problems.append({
            "path": "status",
            "message": f"status {data['status']!r} does not match the last "
                       f"status_history entry {history[-1].get('status')!r}",
        })
    dates = [h.get("date") for h in history if h.get("date")]
    if dates != sorted(dates):
        problems.append({
            "path": "status_history",
            "message": "entries are not in chronological order — history is append-only",
        })
    for field in ("resume_file", "cover_letter_file", "job_description_file", "profile_file"):
        value = data.get(field)
        if value and (str(value).startswith("/") or ":" in str(value)[:3]):
            problems.append({
                "path": field,
                "message": f"{value!r} looks absolute; paths are relative to the profile directory",
            })
    return problems


STRICT_CHECKS = {
    "profile": strict_profile_problems,
    "application": strict_application_problems,
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


def validate_file(path: Path, schema_name: str = None, strict: bool = False) -> dict:
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
        if strict and name in STRICT_CHECKS and isinstance(data, dict):
            strict_problems = STRICT_CHECKS[name](data)
            if strict_problems:
                result["valid"] = False
                result["strict_errors"] = strict_problems[:30]
                if len(strict_problems) > 30:
                    result["strict_errors_truncated"] = len(strict_problems) - 30
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
    parser.add_argument(
        "--strict", action="store_true",
        help="Also check the data-integrity rules the schema cannot express: "
             "source_file on every entry, ISO 8601 dates, evidence behind every "
             "proficiency, status matching status_history",
    )
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

    results = [validate_file(p, args.schema, strict=args.strict) for p in targets]
    failed = [r for r in results if not r["valid"]]

    print(json.dumps({
        "status": "valid" if not failed else "invalid",
        "strict": args.strict,
        "checked": len(results),
        "failed": len(failed),
        "results": results if failed else [
            {"file": r["file"], "schema": r["schema"], "valid": True} for r in results
        ],
    }, indent=2))

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
