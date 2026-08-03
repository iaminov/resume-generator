#!/usr/bin/env python3
"""Text metrics and page verification shared by the document generators.

Two jobs, both independent of what kind of document is being produced:

1. **Text metrics** -- measuring how many lines a string occupies at a given
   font size and column width. python-docx cannot paginate, so a generator that
   wants to predict height before writing the file has to compute it.

2. **Page verification** -- rendering a finished .docx and reporting how many
   pages it really came to, and how full the last one is. Estimation is
   approximate; when the number matters, render and look.

This lives apart from the generators so that neither has to import the other.
Both are imported as siblings, which works because running tools/<script>.py
puts tools/ on sys.path.
"""
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

# Approximate line-height multiplier for Calibri at single spacing.
LINE_HEIGHT = 1.22


def _font_loader():
    """Return a callable (size_pt, bold) -> PIL font, or None if unavailable."""
    try:
        from PIL import ImageFont
    except ImportError:
        return None

    candidates = {
        False: ["calibri.ttf", "Calibri.ttf", "arial.ttf", "DejaVuSans.ttf"],
        True: ["calibrib.ttf", "Calibrib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"],
    }
    search_dirs = [
        Path('C:\\Windows\\Fonts'),
        Path("/usr/share/fonts/truetype/dejavu"),
        Path("/Library/Fonts"),
        Path("/System/Library/Fonts/Supplemental"),
    ]
    resolved = {}
    for bold, names in candidates.items():
        for directory in search_dirs:
            for name in names:
                candidate = directory / name
                if candidate.exists():
                    resolved[bold] = str(candidate)
                    break
            if bold in resolved:
                break
    if not resolved:
        return None

    cache = {}

    def load(size_pt, bold=False):
        path = resolved.get(bold) or next(iter(resolved.values()))
        # Render at 4x for sub-point metric precision, then scale back.
        key = (path, round(size_pt * 4))
        if key not in cache:
            try:
                cache[key] = ImageFont.truetype(path, int(size_pt * 4))
            except OSError:
                return None
        return cache[key]

    return load


_LOAD_FONT = _font_loader()


def text_width_pt(text, size_pt, bold=False):
    """Width of `text` in points, via font metrics when available."""
    if _LOAD_FONT is not None:
        font = _LOAD_FONT(size_pt, bold)
        if font is not None:
            return font.getlength(text) / 4.0
    # Fallback: Calibri averages roughly 0.48 em per character in prose.
    return len(text) * size_pt * 0.48


def wrapped_lines(text, size_pt, avail_pt, bold=False, indent_pt=0.0):
    """Number of rendered lines `text` occupies, by greedy word wrap."""
    avail = max(avail_pt - indent_pt, 1.0)
    words = text.split()
    if not words:
        return 1
    space = text_width_pt(" ", size_pt, bold)
    lines, current = 1, 0.0
    for word in words:
        width = text_width_pt(word, size_pt, bold)
        if current and current + space + width > avail:
            lines += 1
            current = width
        else:
            current += (space if current else 0.0) + width
    return lines


def verify_layout(docx_path):
    """Return (page_count, last_page_fill) for a generated .docx, or (None, None).

    `last_page_fill` is the final page's line count as a fraction of the fullest
    page, so a trailing page holding two lines of a forty-line layout scores
    about 0.05. Converts via LibreOffice when installed; optional by design, so
    callers treat None as "unknown" rather than as an error.
    """
    pdf_bytes = _render_pdf(docx_path)
    if pdf_bytes is None:
        return None, None
    pages = len(re.findall(rb"/Type\s*/Page[^s]", pdf_bytes)) or None
    if pages is None:
        return None, None
    if pages == 1:
        return 1, 1.0

    try:
        import io

        import pdfplumber

        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            counts = [
                len((page.extract_text() or "").splitlines()) for page in pdf.pages
            ]
    except Exception:
        return pages, None

    fullest = max(counts) if counts else 0
    if not fullest:
        return pages, None
    return pages, counts[-1] / fullest


def _render_pdf(docx_path):
    """Render a .docx to PDF bytes via LibreOffice, or None if unavailable.

    LibreOffice rather than Word: it runs headless on every platform, needs no
    licence, and will not block on a modal dialog the way COM automation can.
    Its layout is very close to Word's but not identical, so a document sitting
    exactly on a page boundary may still differ by a line.
    """
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if soffice is None:
        for candidate in (
            r"C:\Program Files\LibreOffice\program\soffice.exe",
            r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
            "/Applications/LibreOffice.app/Contents/MacOS/soffice",
        ):
            if Path(candidate).exists():
                soffice = candidate
                break
    if soffice is None:
        return None

    docx_path = Path(docx_path)
    with tempfile.TemporaryDirectory() as tmp:
        try:
            subprocess.run(
                [soffice, "--headless", "--convert-to", "pdf", "--outdir", tmp,
                 str(docx_path)],
                check=True, capture_output=True, timeout=120,
            )
        except (subprocess.SubprocessError, OSError):
            return None
        pdf = Path(tmp) / (docx_path.stem + ".pdf")
        if not pdf.exists():
            return None
        return pdf.read_bytes()


def verify_page_count(docx_path):
    """Return the true page count of a generated .docx, or None if unavailable."""
    return verify_layout(docx_path)[0]
