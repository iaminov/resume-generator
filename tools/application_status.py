#!/usr/bin/env python3
"""Report the state of a job search: what is live, what has gone quiet, what is stale.

Answers the questions that otherwise require reading every application record by
hand -- what is still outstanding, which ones have had no movement in weeks,
which follow-ups are overdue, and which generated documents were built from a
profile that has since changed.

Usage:
    python3 tools/application_status.py                    # active profile
    python3 tools/application_status.py --slug jane-doe
    python3 tools/application_status.py --stale-days 21    # tighter quiet threshold
    python3 tools/application_status.py --json             # machine-readable

Staleness is computed, not guessed: an application counts as quiet when its most
recent activity predates the threshold and its status is not terminal. Document
freshness compares each generated file's date against profile.json's
last_updated, since a resume built from an older profile no longer reflects what
the profile says.
"""
import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from common import PROFILES_DIR, get_active_slug, relative_to_root

# Statuses that need no chasing -- the outcome is already known.
TERMINAL = {"accepted", "rejected", "withdrawn"}
# Not terminal, but already flagged as gone quiet; do not double-report.
DORMANT = {"ghosted", "draft"}

DEFAULT_STALE_DAYS = 30
DATE_IN_FILENAME = re.compile(r"(\d{4}-\d{2}-\d{2})")


def _parse(stamp):
    """Parse the ISO forms these records actually contain, or return None."""
    if not stamp:
        return None
    text = str(stamp).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        try:
            parsed = datetime.strptime(str(stamp)[:10], "%Y-%m-%d")
        except ValueError:
            return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _last_movement(record):
    """Most recent timestamp anywhere in the record."""
    stamps = []
    for entry in record.get("status_history") or []:
        stamps.append(_parse(entry.get("date")))
    for entry in record.get("activity_log") or []:
        stamps.append(_parse(entry.get("date")))
    for entry in record.get("interviews") or []:
        stamps.append(_parse(entry.get("date")))
    stamps.append(_parse(record.get("last_updated")))
    stamps.append(_parse(record.get("created_date")))
    stamps = [s for s in stamps if s]
    return max(stamps) if stamps else None


def _overdue_follow_ups(record, now):
    out = []
    for item in record.get("follow_ups") or []:
        if item.get("completed"):
            continue
        due = _parse(item.get("due_date") or item.get("date"))
        if due and due < now:
            out.append({
                "due": due.strftime("%Y-%m-%d"),
                "days_overdue": (now - due).days,
                "action": item.get("action") or item.get("note") or "(unspecified)",
            })
    return out


def summarise(slug, stale_days=DEFAULT_STALE_DAYS, now=None):
    now = now or datetime.now(timezone.utc)
    root = PROFILES_DIR / slug
    if not root.exists():
        raise ValueError(f"profile not found: {slug}")

    profile_path = root / "profile.json"
    profile_updated = None
    if profile_path.exists():
        try:
            profile_updated = _parse(
                json.loads(profile_path.read_text(encoding="utf-8")).get("last_updated")
            )
        except (json.JSONDecodeError, OSError):
            pass

    applications, unreadable = [], []
    for path in sorted((root / "applications").glob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            unreadable.append({"file": path.name, "error": str(e)})
            continue

        moved = _last_movement(record)
        idle = (now - moved).days if moved else None
        status = record.get("status", "")
        applications.append({
            "file": path.name,
            "company": record.get("company"),
            "role": record.get("role"),
            "status": status,
            "terminal": status in TERMINAL,
            "last_movement": moved.strftime("%Y-%m-%d") if moved else None,
            "days_idle": idle,
            "quiet": (
                status not in TERMINAL and status not in DORMANT
                and idle is not None and idle >= stale_days
            ),
            "overdue_follow_ups": _overdue_follow_ups(record, now),
            "has_cover_letter": bool(record.get("cover_letter_file")),
        })

    # Generated documents older than the profile they were built from.
    stale_documents = []
    if profile_updated:
        for folder in ("output/output-generated-resumes", "output/output-cover-letters"):
            for path in sorted((root / folder).glob("*.docx")):
                match = DATE_IN_FILENAME.search(path.name)
                built = _parse(match.group(1)) if match else None
                if built and built < profile_updated:
                    stale_documents.append({
                        "file": relative_to_root(path),
                        "built": built.strftime("%Y-%m-%d"),
                        "days_behind_profile": (profile_updated - built).days,
                    })

    active = [a for a in applications if not a["terminal"]]
    return {
        "profile": slug,
        "generated": now.strftime("%Y-%m-%d"),
        "profile_last_updated": profile_updated.strftime("%Y-%m-%d") if profile_updated else None,
        "totals": {
            "applications": len(applications),
            "active": len(active),
            "quiet": sum(1 for a in applications if a["quiet"]),
            "overdue_follow_ups": sum(len(a["overdue_follow_ups"]) for a in applications),
            "stale_documents": len(stale_documents),
        },
        "by_status": {
            s: sum(1 for a in applications if a["status"] == s)
            for s in sorted({a["status"] for a in applications})
        },
        "applications": sorted(
            applications, key=lambda a: (a["terminal"], -(a["days_idle"] or 0))
        ),
        "stale_documents": stale_documents,
        "unreadable": unreadable,
        "stale_threshold_days": stale_days,
    }


def render(summary):
    lines = []
    t = summary["totals"]
    lines.append(f"Job search — {summary['profile']}  (as of {summary['generated']})")
    lines.append("")
    lines.append(
        f"  {t['applications']} application(s), {t['active']} active, "
        f"{t['quiet']} gone quiet"
    )
    if summary["by_status"]:
        lines.append("  " + ", ".join(f"{k}: {v}" for k, v in summary["by_status"].items()))

    if t["quiet"]:
        lines.append("")
        lines.append(f"  Quiet for {summary['stale_threshold_days']}+ days:")
        for a in summary["applications"]:
            if a["quiet"]:
                lines.append(
                    f"    {a['days_idle']:>4}d  {a['company']} — {a['role']} ({a['status']})"
                )

    if t["overdue_follow_ups"]:
        lines.append("")
        lines.append("  Overdue follow-ups:")
        for a in summary["applications"]:
            for f in a["overdue_follow_ups"]:
                lines.append(
                    f"    {f['days_overdue']:>4}d  {a['company']}: {f['action']}"
                )

    if t["stale_documents"]:
        lines.append("")
        lines.append("  Built from an older profile than the current one:")
        for d in summary["stale_documents"]:
            lines.append(f"    {d['days_behind_profile']:>4}d  {Path(d['file']).name}")

    if summary["unreadable"]:
        lines.append("")
        lines.append("  Unreadable records:")
        for u in summary["unreadable"]:
            lines.append(f"    {u['file']}: {u['error']}")

    if not any((t["quiet"], t["overdue_follow_ups"], t["stale_documents"], summary["unreadable"])):
        lines.append("")
        lines.append("  Nothing needs attention.")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Report the state of a job search")
    parser.add_argument("--slug", help="Profile to report on (defaults to active)")
    parser.add_argument("--stale-days", type=int, default=DEFAULT_STALE_DAYS,
                        help=f"Days of no movement before an application counts as quiet "
                             f"(default {DEFAULT_STALE_DAYS})")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    args = parser.parse_args()

    slug = args.slug or get_active_slug()
    if not slug:
        print("Error: no active profile; pass --slug or run profile_switch.py",
              file=sys.stderr)
        sys.exit(1)

    try:
        summary = summarise(slug, args.stale_days)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(summary, indent=2) if args.json else render(summary))


if __name__ == "__main__":
    main()
