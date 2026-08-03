#!/usr/bin/env python3
"""Convert a DOCX file to Markdown, preserving structure for AI consumption.

Usage:
    python3 tools/docx_to_md.py input.docx              # prints to stdout
    python3 tools/docx_to_md.py input.docx output.md     # writes to file
    python3 tools/docx_to_md.py input.docx --json        # markdown + skip report

Extraction is deliberately greedy: body text, tables (including nested ones and
tables inside headers and footers), text boxes, and headers/footers are all
pulled out, in document order.

Because no extractor can anticipate every construct Word emits, conversion ends
with a **failsafe**: every text node in the file is compared against what came
out, and anything that did not make it is reported. A resume silently losing its
contact details or a whole employer is far worse than a noisy warning, and this
repo builds a profile -- the source of truth for everything else -- from this
output.
"""
import argparse
import json
import re
import sys
from pathlib import Path

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

# Text this short is usually punctuation or a stray space; reporting it as
# "skipped" would bury real losses in noise.
MIN_REPORTABLE = 3


def para_to_md(para):
    """Convert a single paragraph to markdown."""
    text = para.text.strip()
    if not text:
        return ""

    style = (para.style.name or "").lower()

    if style.startswith("heading"):
        try:
            level = int(style.replace("heading", "").strip())
        except ValueError:
            level = 1
        return f"{'#' * level} {text}"

    if style.startswith("list") or (
        para._element.pPr is not None
        and para._element.pPr.find(f"{W}numPr") is not None
    ):
        return f"- {text}"

    if style == "title":
        return f"# {text}"
    if style == "subtitle":
        return f"## {text}"

    return text


def _row_cells(row):
    """Cell texts for one row, with merged cells collapsed.

    python-docx repeats a merged cell once per grid column it spans, so a
    two-column merge would otherwise emit its text twice.
    """
    seen = set()
    out = []
    for cell in row.cells:
        key = id(cell._tc)
        if key in seen:
            continue
        seen.add(key)
        out.append(cell.text.strip())
    return out


def _table_to_md(table, depth=0):
    """Render a table, recursing into any nested inside its cells."""
    lines = []
    for row in table.rows:
        cells = [c for c in _row_cells(row) if c]
        if cells:
            lines.append(" | ".join(cells))
        for cell in row.cells:
            for nested in cell.tables:
                lines.extend(_table_to_md(nested, depth + 1))
    return lines


def _iter_block_items(parent_elm, parent):
    """Yield paragraphs and tables from a container in document order.

    Iterating doc.paragraphs and then doc.tables separately loses position: a
    table sitting between two headings ends up after both of them, which
    scrambles a resume that uses tables for layout.
    """
    for child in parent_elm.iterchildren():
        if child.tag == f"{W}p":
            yield Paragraph(child, parent)
        elif child.tag == f"{W}tbl":
            yield Table(child, parent)
        elif child.tag == f"{W}sdt":
            # Content controls wrap real content; descend rather than skip.
            content = child.find(f"{W}sdtContent")
            if content is not None:
                yield from _iter_block_items(content, parent)


def _render_container(parent_elm, parent):
    lines = []
    for block in _iter_block_items(parent_elm, parent):
        if isinstance(block, Paragraph):
            lines.append(para_to_md(block))
        else:
            lines.extend(_table_to_md(block))
            lines.append("")
    return lines


def _textbox_lines(element):
    """Text boxes live in w:txbxContent and are unreachable from doc.paragraphs.

    Applies to headers and footers as much as the body -- a resume with its
    contact block in a floating text box in the header is not unusual.
    """
    lines = []
    for txbx in element.iter(f"{W}txbxContent"):
        for para in txbx.iter(f"{W}p"):
            text = "".join(node.text or "" for node in para.iter(f"{W}t")).strip()
            if text:
                lines.append(text)
    return lines


def _all_text_nodes(doc):
    """Every text node in body, headers and footers -- the failsafe's baseline."""
    texts = []
    parts = [doc.element.body]
    for section in doc.sections:
        for hf in (section.header, section.first_page_header, section.even_page_header,
                   section.footer, section.first_page_footer, section.even_page_footer):
            if hf is not None:
                parts.append(hf._element)
    for part in parts:
        for node in part.iter(f"{W}t"):
            if node.text and node.text.strip():
                texts.append(node.text.strip())
    return texts


def _normalise(text):
    return re.sub(r"\s+", " ", text).strip().lower()


def convert(docx_path):
    """Convert a DOCX. Returns (markdown, skipped) where skipped lists any text
    present in the file that did not reach the output."""
    doc = Document(str(docx_path))
    lines = []

    # Headers first: contact details often live there.
    header_lines = []
    footer_lines = []
    for section in doc.sections:
        for header in (section.first_page_header, section.header, section.even_page_header):
            if header is not None:
                header_lines.extend(_render_container(header._element, header))
                header_lines.extend(_textbox_lines(header._element))
        for footer in (section.first_page_footer, section.footer, section.even_page_footer):
            if footer is not None:
                footer_lines.extend(_render_container(footer._element, footer))
                footer_lines.extend(_textbox_lines(footer._element))

    lines.extend(header_lines)
    if header_lines:
        lines.append("")
    lines.extend(_render_container(doc.element.body, doc))
    lines.extend(_textbox_lines(doc.element.body))
    if footer_lines:
        lines.append("")
        lines.extend(footer_lines)

    # Collapse runs of blank lines.
    output = []
    prev_blank = False
    for line in lines:
        if line == "":
            if not prev_blank and output:
                output.append("")
            prev_blank = True
        else:
            output.append(line)
            prev_blank = False

    markdown = "\n".join(output).strip() + "\n"

    # Failsafe: anything in the file that is not in the output.
    haystack = _normalise(markdown)
    skipped = []
    for text in _all_text_nodes(doc):
        if len(text) < MIN_REPORTABLE:
            continue
        if _normalise(text) not in haystack:
            skipped.append(text)

    # De-duplicate while keeping order.
    seen = set()
    skipped = [t for t in skipped if not (t in seen or seen.add(t))]
    return markdown, skipped


def docx_to_md(docx_path):
    """Convert a DOCX to a markdown string (skip report discarded)."""
    return convert(docx_path)[0]


def main():
    parser = argparse.ArgumentParser(description="Convert a DOCX file to Markdown")
    parser.add_argument("input", help="Path to the .docx file")
    parser.add_argument("output", nargs="?", help="Optional .md output path")
    parser.add_argument("--json", action="store_true",
                        help="Emit a JSON result including the skip report")
    args = parser.parse_args()

    docx_path = Path(args.input)
    if not docx_path.exists():
        print(f"Error: {docx_path} not found", file=sys.stderr)
        sys.exit(1)

    markdown, skipped = convert(docx_path)

    if args.output:
        Path(args.output).write_text(markdown, encoding="utf-8")

    if args.json:
        print(json.dumps({
            "status": "converted",
            "input": str(docx_path),
            "output": args.output,
            "characters": len(markdown),
            "skipped_count": len(skipped),
            "skipped": skipped,
        }, indent=2, ensure_ascii=False))
    else:
        if not args.output:
            print(markdown)
        if skipped:
            print(
                f"\nWarning: {len(skipped)} text fragment(s) could not be extracted "
                f"and are missing from the output:",
                file=sys.stderr,
            )
            for text in skipped[:20]:
                print(f"  - {text[:120]}", file=sys.stderr)
            if len(skipped) > 20:
                print(f"  ... and {len(skipped) - 20} more", file=sys.stderr)


if __name__ == "__main__":
    main()
