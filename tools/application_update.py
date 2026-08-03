#!/usr/bin/env python3
"""Update an application record safely: status, activity log, follow-ups.

track-application asks for a valid status transition, an append-only history,
and a timestamp on every change. Those are deterministic rules, and re-deriving
them by hand on each edit is how a record ends up with a status that skips a
stage, a history entry silently rewritten, or a document that no longer
validates. This does the mechanical part.

Usage:
    # what can this record move to next?
    python3 tools/application_update.py rec.json --show

    # advance the status (validates the transition, appends history + activity)
    python3 tools/application_update.py rec.json --status phone_interview
    python3 tools/application_update.py rec.json --status offer --notes "verbal, written to follow"

    # just journal something
    python3 tools/application_update.py rec.json --log "Recruiter emailed to schedule screen"

    # real life is messier than the graph
    python3 tools/application_update.py rec.json --status offer --force

The file is validated against schemas/application.schema.json before and after,
and written atomically, so a failure leaves the original untouched.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from common import relative_to_root
from validate import validate_file

# Which statuses may follow which. Terminal states have no successors; `ghosted`
# is deliberately revivable, because employers do resurface after months of
# silence and the record should be able to say so without --force.
TRANSITIONS = {
    "draft": {"ready", "applied", "withdrawn"},
    "ready": {"applied", "withdrawn"},
    "applied": {"screening", "phone_interview", "rejected", "ghosted", "withdrawn"},
    "screening": {"phone_interview", "technical_interview", "rejected", "ghosted", "withdrawn"},
    "phone_interview": {"technical_interview", "onsite_interview", "offer", "rejected", "ghosted", "withdrawn"},
    "technical_interview": {"onsite_interview", "offer", "rejected", "ghosted", "withdrawn"},
    "onsite_interview": {"offer", "rejected", "ghosted", "withdrawn"},
    "offer": {"accepted", "rejected", "withdrawn"},
    "accepted": set(),
    "rejected": set(),
    "withdrawn": set(),
    "ghosted": {"screening", "phone_interview", "technical_interview",
                "onsite_interview", "offer", "rejected", "withdrawn"},
}

TERMINAL = {status for status, nxt in TRANSITIONS.items() if not nxt}


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load(path: Path) -> dict:
    if not path.exists():
        raise ValueError(f"application record not found: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"invalid JSON in {path.name}: {e}") from e


def check_transition(current: str, new: str, force: bool = False) -> str | None:
    """Return a warning string if the move is irregular, else None. Raises if illegal."""
    if current == new:
        raise ValueError(f"already at status '{new}' — nothing to change")
    if current not in TRANSITIONS:
        raise ValueError(f"record has unknown current status '{current}'")
    if new not in TRANSITIONS:
        raise ValueError(
            f"unknown status '{new}'; choose from {', '.join(sorted(TRANSITIONS))}"
        )

    allowed = TRANSITIONS[current]
    if new in allowed:
        return None

    detail = (
        f"'{current}' is terminal" if current in TERMINAL
        else f"from '{current}' the usual next steps are {', '.join(sorted(allowed))}"
    )
    if not force:
        raise ValueError(
            f"'{current}' -> '{new}' is not a normal transition ({detail}). "
            f"Re-run with --force if it really happened."
        )
    return f"forced an irregular transition '{current}' -> '{new}' ({detail})"


def apply_status(record: dict, new_status: str, notes: str = None, force: bool = False):
    """Move the record to a new status, appending rather than rewriting."""
    current = record.get("status", "")
    warning = check_transition(current, new_status, force)

    stamp = now_iso()
    entry = {"status": new_status, "date": stamp}
    if notes:
        entry["notes"] = notes

    # status_history is append-only: never touch what is already there.
    record.setdefault("status_history", []).append(entry)
    record["status"] = new_status

    log = f"Status changed from {current} to {new_status}"
    if notes:
        log += f" — {notes}"
    record.setdefault("activity_log", []).append({"date": stamp, "entry": log})
    record["last_updated"] = stamp
    return warning


def apply_log(record: dict, text: str):
    stamp = now_iso()
    record.setdefault("activity_log", []).append({"date": stamp, "entry": text})
    record["last_updated"] = stamp


def write_atomically(path: Path, record: dict):
    """Write via a temp file so a failure cannot truncate the original."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def main():
    parser = argparse.ArgumentParser(
        description="Update an application record's status or activity log"
    )
    parser.add_argument("record", help="Path to the application JSON file")
    parser.add_argument("--status", help="New status to move to")
    parser.add_argument("--notes", help="Optional note attached to the status change")
    parser.add_argument("--log", help="Append a free-text entry to the activity log")
    parser.add_argument("--force", action="store_true",
                        help="Allow a transition the graph does not consider normal")
    parser.add_argument("--show", action="store_true",
                        help="Report current status and the valid next steps")
    args = parser.parse_args()

    path = Path(args.record)
    try:
        record = load(path)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.show or not (args.status or args.log):
        current = record.get("status", "")
        print(json.dumps({
            "file": relative_to_root(path),
            "company": record.get("company"),
            "role": record.get("role"),
            "status": current,
            "terminal": current in TERMINAL,
            "valid_next": sorted(TRANSITIONS.get(current, [])),
            "history_entries": len(record.get("status_history", [])),
            "activity_entries": len(record.get("activity_log", [])),
        }, indent=2))
        return

    # Refuse to build on a record that is already broken -- otherwise the fault
    # gets attributed to this edit.
    before = validate_file(path)
    if not before["valid"]:
        print(json.dumps({
            "status": "aborted",
            "reason": "record does not validate before editing; fix it first",
            "detail": before.get("errors") or before.get("error"),
        }, indent=2), file=sys.stderr)
        sys.exit(1)

    warning = None
    try:
        if args.status:
            warning = apply_status(record, args.status, args.notes, args.force)
        if args.log:
            apply_log(record, args.log)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    write_atomically(path, record)

    after = validate_file(path)
    if not after["valid"]:
        print(json.dumps({
            "status": "invalid_after_write",
            "file": relative_to_root(path),
            "errors": after.get("errors") or after.get("error"),
        }, indent=2), file=sys.stderr)
        sys.exit(1)

    result = {
        "status": "updated",
        "file": relative_to_root(path),
        "current_status": record["status"],
        "valid_next": sorted(TRANSITIONS.get(record["status"], [])),
        "history_entries": len(record.get("status_history", [])),
        "activity_entries": len(record.get("activity_log", [])),
        "validated": True,
    }
    if warning:
        result["warning"] = warning
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
