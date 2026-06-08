#!/usr/bin/env python3
"""Convert a DOCX file to Markdown, preserving structure for AI consumption.

Usage:
    python3 tools/docx_to_md.py input.docx              # prints to stdout
    python3 tools/docx_to_md.py input.docx output.md     # writes to file
"""
import sys
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH


def para_to_md(para):
    """Convert a single paragraph to markdown."""
    text = para.text.strip()
    if not text:
        return ""

    style = (para.style.name or "").lower()

    # Headings
    if style.startswith("heading"):
        try:
            level = int(style.replace("heading", "").strip())
        except ValueError:
            level = 1
        return f"{'#' * level} {text}"

    # List items
    if style.startswith("list") or para._element.pPr is not None and para._element.pPr.find(
        "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}numPr"
    ) is not None:
        return f"- {text}"

    # Title / subtitle (common in resumes)
    if style == "title":
        return f"# {text}"
    if style == "subtitle":
        return f"## {text}"

    return text


def docx_to_md(docx_path):
    """Extract a DOCX file to markdown string."""
    doc = Document(docx_path)
    lines = []

    # Extract document body
    for para in doc.paragraphs:
        md = para_to_md(para)
        lines.append(md)

    # Extract tables (some resumes use tables for layout)
    for table in doc.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                lines.append(" | ".join(cells))
        lines.append("")

    # Extract headers/footers (contact info often lives here)
    for section in doc.sections:
        for header in [section.header, section.first_page_header]:
            if header and header.paragraphs:
                header_text = [p.text.strip() for p in header.paragraphs if p.text.strip()]
                if header_text:
                    lines.insert(0, "")
                    for ht in reversed(header_text):
                        lines.insert(0, ht)

        for footer in [section.footer, section.first_page_footer]:
            if footer and footer.paragraphs:
                footer_text = [p.text.strip() for p in footer.paragraphs if p.text.strip()]
                if footer_text:
                    lines.append("")
                    lines.extend(footer_text)

    # Clean up excessive blank lines
    output = []
    prev_blank = False
    for line in lines:
        if line == "":
            if not prev_blank:
                output.append("")
            prev_blank = True
        else:
            output.append(line)
            prev_blank = False

    return "\n".join(output).strip() + "\n"


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} input.docx [output.md]", file=sys.stderr)
        sys.exit(1)

    docx_path = Path(sys.argv[1])
    if not docx_path.exists():
        print(f"Error: {docx_path} not found", file=sys.stderr)
        sys.exit(1)

    md = docx_to_md(docx_path)

    if len(sys.argv) >= 3:
        out_path = Path(sys.argv[2])
        out_path.write_text(md, encoding="utf-8")
    else:
        print(md)


if __name__ == "__main__":
    main()
