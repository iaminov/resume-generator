#!/usr/bin/env python3
"""Compare two generated documents by their content sidecars.

A .docx cannot be diffed usefully, and `git diff` on the JSON reports a wall of
reflowed lines. This answers the question actually being asked: what did this
version say that the other did not?

Usage:
    python3 tools/diff_content.py old.content.json new.content.json
    python3 tools/diff_content.py old.content.json new.content.json --json

Works on both resume and cover-letter sidecars; the shape is detected from the
keys present.
"""
import argparse
import difflib
import json
import sys
from pathlib import Path

# Sections compared as ordered lists of strings.
LIST_SECTIONS = ("body",)
# Sections compared entry by entry, keyed by a human-meaningful label.
KEYED_SECTIONS = {
    "experience": ("title", "company"),
    "education": ("degree", "institution"),
    "projects": ("name",),
    "certifications": ("name",),
    "publications": ("title",),
    "awards": ("name",),
}


def load(path):
    path = Path(path)
    if not path.exists():
        raise ValueError(f"not found: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"invalid JSON in {path.name}: {e}") from e


def _label(entry, keys):
    parts = [str(entry.get(k)) for k in keys if entry.get(k)]
    return " — ".join(parts) or "(unlabelled)"


def _skills_map(data):
    return {
        g.get("category", "?"): list(g.get("items") or [])
        for g in (data.get("skills") or [])
    }


def _bullets_map(data, section, keys):
    out = {}
    for entry in data.get(section) or []:
        if isinstance(entry, dict):
            out[_label(entry, keys)] = list(entry.get("bullets") or [])
    return out


def compare(old, new):
    changes = {"summary": None, "skills": {}, "sections": {}, "layout": None, "scalar": {}}

    for field in ("name", "summary", "salutation", "closing", "signature", "date"):
        a, b = (old.get(field) or "").strip(), (new.get(field) or "").strip()
        if a != b:
            changes["scalar"][field] = {"old": a, "new": b}
    changes["summary"] = changes["scalar"].pop("summary", None)

    if (old.get("layout") or {}) != (new.get("layout") or {}):
        changes["layout"] = {"old": old.get("layout"), "new": new.get("layout")}

    # Skills, by category.
    a_skills, b_skills = _skills_map(old), _skills_map(new)
    for cat in sorted(set(a_skills) | set(b_skills)):
        a, b = set(a_skills.get(cat, [])), set(b_skills.get(cat, []))
        if a != b:
            changes["skills"][cat] = {
                "added": sorted(b - a),
                "removed": sorted(a - b),
            }

    # Free-text list sections (cover letter bodies).
    for section in LIST_SECTIONS:
        a, b = old.get(section) or [], new.get(section) or []
        if a != b:
            changes["sections"][section] = {
                "added": [x for x in b if x not in a],
                "removed": [x for x in a if x not in b],
            }

    # Keyed sections, comparing bullets within each entry.
    for section, keys in KEYED_SECTIONS.items():
        a_entries = _bullets_map(old, section, keys)
        b_entries = _bullets_map(new, section, keys)
        a_labels, b_labels = set(a_entries), set(b_entries)
        section_changes = {}

        for label in sorted(b_labels - a_labels):
            section_changes[label] = {"status": "added"}
        for label in sorted(a_labels - b_labels):
            section_changes[label] = {"status": "removed"}
        for label in sorted(a_labels & b_labels):
            a, b = a_entries[label], b_entries[label]
            if a == b:
                continue
            added = [x for x in b if x not in a]
            removed = [x for x in a if x not in b]
            reworded = []
            for gone in list(removed):
                match = difflib.get_close_matches(gone, added, n=1, cutoff=0.6)
                if match:
                    reworded.append({"from": gone, "to": match[0]})
                    removed.remove(gone)
                    added.remove(match[0])
            entry = {"status": "changed"}
            if added:
                entry["added"] = added
            if removed:
                entry["removed"] = removed
            if reworded:
                entry["reworded"] = reworded
            section_changes[label] = entry

        if section_changes:
            changes["sections"][section] = section_changes

    return changes


def render(changes, old_name, new_name):
    lines = [f"{old_name}  ->  {new_name}", ""]
    empty = True

    if changes["summary"]:
        empty = False
        lines.append("SUMMARY changed:")
        lines.append(f"  - {changes['summary']['old'][:160]}")
        lines.append(f"  + {changes['summary']['new'][:160]}")
        lines.append("")

    for field, change in changes["scalar"].items():
        empty = False
        lines.append(f"{field}: {change['old']!r} -> {change['new']!r}")

    if changes["layout"]:
        empty = False
        lines.append(f"layout: {changes['layout']['old']} -> {changes['layout']['new']}")
        lines.append("")

    if changes["skills"]:
        empty = False
        lines.append("SKILLS:")
        for cat, change in changes["skills"].items():
            for item in change["added"]:
                lines.append(f"  + {cat}: {item}")
            for item in change["removed"]:
                lines.append(f"  - {cat}: {item}")
        lines.append("")

    for section, content in changes["sections"].items():
        empty = False
        lines.append(f"{section.upper()}:")
        if isinstance(content, dict) and "added" in content and "removed" in content:
            for item in content["added"]:
                lines.append(f"  + {item[:150]}")
            for item in content["removed"]:
                lines.append(f"  - {item[:150]}")
        else:
            for label, entry in content.items():
                lines.append(f"  {label} [{entry['status']}]")
                for item in entry.get("added", []):
                    lines.append(f"    + {item[:140]}")
                for item in entry.get("removed", []):
                    lines.append(f"    - {item[:140]}")
                for pair in entry.get("reworded", []):
                    lines.append(f"    ~ {pair['from'][:70]}")
                    lines.append(f"      -> {pair['to'][:70]}")
        lines.append("")

    if empty:
        lines.append("No differences.")
    return "\n".join(lines).rstrip() + "\n"


def main():
    parser = argparse.ArgumentParser(
        description="Compare two generated documents by their content sidecars"
    )
    parser.add_argument("old", help="Earlier .content.json")
    parser.add_argument("new", help="Later .content.json")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    args = parser.parse_args()

    try:
        old, new = load(args.old), load(args.new)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    changes = compare(old, new)
    if args.json:
        print(json.dumps(changes, indent=2, ensure_ascii=False))
    else:
        print(render(changes, Path(args.old).name, Path(args.new).name))


if __name__ == "__main__":
    main()
