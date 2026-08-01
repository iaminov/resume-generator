#!/usr/bin/env python3
"""Extract all resumes for a profile to readable text files.

Converts DOCX files to markdown alongside the originals. PDFs are left as-is
(Claude reads them natively). Outputs a JSON manifest of what was extracted.

Usage:
    python3 tools/extract_resumes.py                  # uses active profile
    python3 tools/extract_resumes.py --slug jane-doe   # specific profile
"""
import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
PROFILES_DIR = DATA_DIR / "profiles"
ACTIVE_PROFILE_FILE = DATA_DIR / ".active-profile"

# Import the docx converter from sibling module
from docx_to_md import docx_to_md


def get_active_slug() -> str | None:
    if ACTIVE_PROFILE_FILE.exists():
        slug = ACTIVE_PROFILE_FILE.read_text(encoding="utf-8").strip()
        return slug if slug else None
    return None


def main():
    parser = argparse.ArgumentParser(description="Extract all resumes for a profile")
    parser.add_argument("--slug", help="Profile slug (defaults to active profile)")
    args = parser.parse_args()

    slug = args.slug or get_active_slug()
    if not slug:
        print("Error: No active profile set. Run profile_switch.py or pass --slug.", file=sys.stderr)
        sys.exit(1)

    source_dir = PROFILES_DIR / slug / "input" / "input-resumes"
    if not source_dir.exists():
        print(f"Error: {source_dir} does not exist.", file=sys.stderr)
        sys.exit(1)

    pdfs = sorted(source_dir.glob("*.pdf"))
    docx_files = sorted(source_dir.glob("*.docx"))

    if not pdfs and not docx_files:
        print(json.dumps({
            "status": "empty",
            "slug": slug,
            "message": f"No PDF or DOCX files found in {source_dir.relative_to(PROJECT_ROOT)}",
        }, indent=2))
        sys.exit(0)

    extracted = []
    errors = []

    for docx_path in docx_files:
        md_path = docx_path.with_suffix(".md")
        try:
            md_text = docx_to_md(str(docx_path))
            md_path.write_text(md_text, encoding="utf-8")
            extracted.append({
                "source": docx_path.name,
                "extracted": md_path.name,
                "type": "docx",
                "size_chars": len(md_text),
            })
        except Exception as e:
            errors.append({
                "source": docx_path.name,
                "error": str(e),
            })

    # PDFs don't need extraction — Claude reads them natively via Read tool
    pdf_entries = [{"source": p.name, "type": "pdf", "note": "read directly with Read tool"} for p in pdfs]

    result = {
        "status": "extracted",
        "slug": slug,
        "source_dir": str(source_dir.relative_to(PROJECT_ROOT)),
        "docx_extracted": len(extracted),
        "pdfs_available": len(pdfs),
        "errors": errors,
        "files": extracted + pdf_entries,
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
