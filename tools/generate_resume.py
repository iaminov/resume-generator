#!/usr/bin/env python3
"""Generate a .docx resume from a JSON content file.

This script is a GENERIC formatter. It takes structured JSON describing
the tailored resume content (already selected and written by Claude) and
produces a formatted Word document. It does NOT contain any person-specific
content — all content comes from the JSON input.

Usage:
    python3 tools/generate_resume.py content.json output.docx
    python3 tools/generate_resume.py content.json output.docx --template templates/default.docx
    python3 tools/generate_resume.py content.json output.docx --target-pages 1
    python3 tools/generate_resume.py content.json output.docx --density compact

Spacing adapts to the resume in hand rather than being fixed. Three presets --
normal, compact, dense -- vary margins and section spacing only; body and
heading font sizes never change, since shrinking type to force a fit is what
makes a resume look crammed. All three stay within the margin bounds documented
in .claude/rules/resume-formatting.md.

A fourth preset, `ultra`, goes past those bounds: 0.30in margins and every font
scaled to 95%. It is opt-in only -- automatic selection never reaches it -- and
exists for a candidate who has weighed the tradeoff and chosen to keep content
that roomier type would cost them. Prefer cutting weak content first.

Selection, in precedence order:
  1. --density / --target-pages on the command line
  2. an optional "layout" object in the JSON content
  3. automatic: start at `normal`, and tighten only to reclaim a trailing page
     that would hold just a few lines

Where LibreOffice is installed, both the page goal and the trailing-page check
are settled by rendering the document rather than by the estimator, which runs
about 10% optimistic and cannot be trusted to spot a straggler on its own.

JSON input format:
{
  "name": "Full Name",
  "layout": { "density": "auto", "target_pages": 1 },
  "contact": {
    "email": "...", "phone": "...", "location": "...",
    "linkedin": "...", "github": "...", "portfolio": "..."
  },
  "summary": "Professional summary text...",
  "skills": [
    { "category": "Languages", "items": ["Python", "Go", "Java"] },
    { "category": "Cloud", "items": ["AWS", "GCP", "Kubernetes"] }
  ],
  "experience": [
    {
      "title": "Senior Staff Engineer",
      "company": "Acme Corp",
      "location": "New York, NY",
      "dates": "2022 - Present",
      "bullets": ["Led migration...", "Reduced costs by 40%..."]
    }
  ],
  "earlier_career": [
    { "title": "Software Engineer", "company": "OldCo" },
    { "title": "Junior Developer", "company": "StartupX" }
  ],
  "education": [
    { "degree": "B.S. Computer Science", "institution": "MIT",
      "dates": "2010", "details": ["GPA: 3.8"] }
  ],
  "certifications": [
    { "name": "AWS Solutions Architect Professional", "date": "2023" }
  ],
  "projects": [
    { "name": "Tool Name", "description": "Built a...", "technologies": "Go, gRPC" }
  ],
  "publications": [
    { "title": "Article Title", "venue": "InfoQ, 2023" }
  ],
  "awards": [
    { "name": "Patent: ...", "details": "US Patent 12345, 2022" }
  ]
}

Sections with empty/missing data are skipped automatically.
"""
import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path

from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from layout import (
    LINE_HEIGHT,
    metrics_source,
    open_base_document,
    verify_layout,
    verify_page_count,
    wrapped_lines,
)

# Formatting constants (from resume-formatting.md)
FONT_NAME = "Calibri"
NAME_SIZE = Pt(18)
SECTION_HEADING_SIZE = Pt(11)
BODY_SIZE = Pt(10)
CONTACT_SIZE = Pt(10)
ROLE_TITLE_SIZE = Pt(10.5)
COLOR_HEADING = RGBColor(0x1A, 0x1A, 0x1A)
COLOR_BODY = RGBColor(0x00, 0x00, 0x00)
COLOR_META = RGBColor(0x55, 0x55, 0x55)
COLOR_LINK = RGBColor(0x26, 0x5B, 0x8C)
BORDER_COLOR = "999999"

# Page geometry (US Letter)
PAGE_WIDTH_IN = 8.5
PAGE_HEIGHT_IN = 11.0

# Left indent applied by the "List Bullet" style, in points.
BULLET_INDENT_PT = 18.0

# Pure text-metric summing consistently lands about 10% under what Word and
# LibreOffice actually produce: they break lines slightly differently, apply
# widow/orphan control, and keep headings with the block below. Measured across
# nine renders (three documents x three presets) the shortfall ranged from 6%
# to 14%. This nudges the estimate into the right neighbourhood; it is not a
# substitute for verify_page_count() when the exact number matters.
ESTIMATE_CALIBRATION = 1.10


@dataclass(frozen=True)
class Density:
    """A spacing preset.

    The three presets on the automatic ladder stay inside the bounds documented
    in resume-formatting.md (0.5-0.75in margins) and all leave `font_scale` at
    1.0, so tightening density to win a page never shrinks type: doing that is
    what makes a resume look crammed, and the formatting rules prohibit it.

    `font_scale` exists for the one case the rules do allow -- a candidate who
    has looked at the tradeoff and chosen more content over roomier type. It
    scales every font size uniformly, so the size relationships between name,
    headings, role titles and body text are preserved rather than the body
    alone being squeezed. Presets carrying a scale below 1.0 are opt-in only
    (see OPT_IN_DENSITIES) and are never reachable by automatic tightening.
    """

    name: str
    margin_in: float
    heading_before: float
    heading_after: float
    role_before: float
    block_before: float
    block_after: float
    font_scale: float = 1.0

    def pt(self, size):
        """Scale a base font size for this preset.

        Rounded to the half-point, because that is the resolution Word stores
        font sizes at. Doing it here rather than leaving it to the writer keeps
        the hierarchy intact: scaling 11pt headings and 10.5pt role titles by
        0.95 lands them on 10.45 and 9.975, which silently collapse to the same
        stored size unless each is rounded on its own.
        """
        return Pt(round(size.pt * self.font_scale * 2) / 2)


DENSITIES = (
    Density("normal", 0.75, 10, 4, 8, 2, 4),
    Density("compact", 0.60, 8, 4, 7, 2, 3),
    Density("dense", 0.50, 6, 3, 6, 2, 2),
)

# Reachable only by naming them explicitly. `choose_density` never returns one,
# so no resume gets smaller type without someone asking for it.
OPT_IN_DENSITIES = (
    Density("ultra", 0.30, 5, 2, 5, 1, 2, font_scale=0.95),
)

DENSITY_BY_NAME = {d.name: d for d in DENSITIES + OPT_IN_DENSITIES}
DEFAULT_DENSITY = DENSITY_BY_NAME["normal"]

# A trailing page holding only a few lines looks unfinished; resume-formatting.md
# calls this out. When overflow is this small, auto mode tightens density to pull
# the content back onto the previous page.
STRAGGLER_PAGE_FRACTION = 0.15


# --------------------------------------------------------------------------
# Height estimation
#
# Walk the resume structure and sum the height of everything in it, using the
# text metrics in layout.py. The estimate only ever picks between density
# presets; it never alters content.
# --------------------------------------------------------------------------

def estimate_pages(data, density):
    """Estimate how many pages `data` occupies at `density`.

    Returns a float: 1.4 means "one page plus 40% of a second". This is an
    approximation used to choose between presets. Pagination also quantises --
    a heading cannot split from the block it introduces -- so treat the result
    as a guide. Use verify_page_count() when the exact number matters.
    """
    usable_w = (PAGE_WIDTH_IN - 2 * density.margin_in) * 72
    usable_h = (PAGE_HEIGHT_IN - 2 * density.margin_in) * 72

    # Every size below is passed through scaled() exactly once, so a preset
    # carrying font_scale < 1.0 shrinks the estimate the same way it shrinks
    # the rendered document.
    def scaled(size_pt):
        return size_pt * density.font_scale

    def line_h(size_pt):
        return size_pt * LINE_HEIGHT

    def heading():
        return (
            density.heading_before
            + line_h(scaled(SECTION_HEADING_SIZE.pt))
            + density.heading_after
        )

    def paragraph(text, size_pt=None, bold=False, indent_pt=0.0, before=None, after=None):
        size_pt = scaled(BODY_SIZE.pt if size_pt is None else size_pt)
        before = density.block_before if before is None else before
        after = density.block_after if after is None else after
        lines = wrapped_lines(text, size_pt, usable_w, bold, indent_pt)
        return before + lines * line_h(size_pt) + after

    total = 0.0

    # Header: name, then optional contact and link lines.
    total += line_h(scaled(NAME_SIZE.pt)) + 2
    contact = data.get("contact") or {}
    if any(contact.get(f) for f in ("email", "phone", "location")):
        total += line_h(scaled(CONTACT_SIZE.pt)) + 2
    if any(contact.get(f) for f in ("linkedin", "github", "portfolio")):
        total += line_h(scaled(CONTACT_SIZE.pt)) + 4

    if (data.get("summary") or "").strip():
        total += heading() + paragraph(data["summary"].strip())

    skills = data.get("skills") or []
    if skills:
        total += heading()
        for group in skills:
            items = group.get("items") or []
            if not items:
                continue
            text = ", ".join(items) if isinstance(items, list) else str(items)
            total += paragraph("{}: {}".format(group.get("category", ""), text), after=1)

    experience = data.get("experience") or []
    if experience:
        total += heading()
        for role in experience:
            # Title/date line and the company/location line share one paragraph.
            total += (
                density.role_before
                + line_h(scaled(ROLE_TITLE_SIZE.pt))
                + line_h(scaled(BODY_SIZE.pt))
                + 2
            )
            for bullet in role.get("bullets") or []:
                total += paragraph(bullet, indent_pt=BULLET_INDENT_PT, before=1, after=1)

    earlier = data.get("earlier_career")
    if earlier:
        total += heading()
        if isinstance(earlier, str):
            total += paragraph(earlier)
        else:
            entries = []
            for role in earlier:
                title, company = role.get("title", ""), role.get("company", "")
                entries.append(f"{title} at {company}" if title and company else company)
            total += paragraph(" | ".join(e for e in entries if e))

    education = data.get("education") or []
    if education:
        total += heading()
        for edu in education:
            line = "{} {}".format(edu.get("degree", ""), edu.get("institution", "")).strip()
            total += paragraph(line, after=2)
            total += len(edu.get("details") or []) * line_h(scaled(BODY_SIZE.pt))

    for key in ("certifications", "publications", "awards"):
        entries = data.get(key) or []
        if not entries:
            continue
        total += heading()
        for entry in entries:
            parts = [entry.get("name") or entry.get("title") or ""]
            for extra in ("issuer", "venue", "details", "date"):
                if entry.get(extra):
                    parts.append(str(entry[extra]))
            total += paragraph(" - ".join(p for p in parts if p), before=1, after=1)

    projects = data.get("projects") or []
    if projects:
        total += heading()
        for proj in projects:
            parts = [proj.get("name", "")]
            if proj.get("description"):
                parts.append(proj["description"])
            if proj.get("technologies"):
                parts.append("({})".format(proj["technologies"]))
            total += paragraph(" - ".join(p for p in parts if p), after=2)

    return (total / usable_h) * ESTIMATE_CALIBRATION


def choose_density(data, target_pages=None, requested="auto"):
    """Pick a spacing preset for this specific resume.

    - An explicit preset name is honoured as given.
    - With a `target_pages` goal, use the loosest preset that meets it.
    - With no goal, start at `normal` and tighten only to reclaim a trailing
      page holding just a few lines.

    Returns (density, note); the note explains the choice in the CLI report.
    """
    if requested and requested != "auto":
        if requested not in DENSITY_BY_NAME:
            raise ValueError(
                "unknown density '{}'; choose from {} or 'auto'".format(
                    requested, ", ".join(DENSITY_BY_NAME)
                )
            )
        return DENSITY_BY_NAME[requested], f"density '{requested}' requested explicitly"

    if target_pages:
        for density in DENSITIES:
            estimate = estimate_pages(data, density)
            if estimate <= target_pages:
                return density, (
                    f"auto: loosest preset fitting {target_pages} page(s) (estimated {estimate:.2f})"
                )
        tightest = DENSITIES[-1]
        return tightest, (
            f"auto: content exceeds {target_pages} page(s) even at '{tightest.name}' (estimated {estimate_pages(data, tightest):.2f}) - trim content"
        )

    estimate = estimate_pages(data, DEFAULT_DENSITY)
    overflow = estimate - math.floor(estimate)
    if math.floor(estimate) >= 1 and 0 < overflow <= STRAGGLER_PAGE_FRACTION:
        goal = math.floor(estimate)
        for density in DENSITIES:
            if estimate_pages(data, density) <= goal:
                return density, (
                    f"auto: tightened to '{density.name}' to reclaim a trailing page holding "
                    f"only {overflow:.0%} of a page"
                )
    return DEFAULT_DENSITY, f"auto: '{DEFAULT_DENSITY.name}' (estimated {estimate:.2f} pages)"


def set_font(run, size=None, bold=False, color=COLOR_BODY, density=DEFAULT_DENSITY):
    """Apply font formatting to a run, scaled for `density`."""
    run.font.name = FONT_NAME
    run.font.size = density.pt(BODY_SIZE if size is None else size)
    run.font.bold = bold
    run.font.color.rgb = color


def add_section_heading(doc, text, density=DEFAULT_DENSITY):
    """Add a section heading with a bottom border line."""
    para = doc.add_paragraph()
    para.paragraph_format.space_before = Pt(density.heading_before)
    para.paragraph_format.space_after = Pt(density.heading_after)

    run = para.add_run(text.upper())
    set_font(run, size=SECTION_HEADING_SIZE, bold=True, color=COLOR_HEADING, density=density)

    # Bottom border
    pPr = para._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "4")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), BORDER_COLOR)
    pBdr.append(bottom)
    pPr.append(pBdr)

    return para


def content_width(doc):
    """Usable text width of the page, i.e. page width minus both margins."""
    section = doc.sections[0]
    return section.page_width - section.left_margin - section.right_margin


def add_right_tab(doc, para):
    """Set a right-aligned tab stop at the right margin.

    Text after a tab character then aligns flush to the right edge of the
    page, producing a clean vertical column of dates without using a table.
    Tables are avoided deliberately: some ATS parsers reorder or drop table
    cells, whereas tab stops keep the document single-column and parseable.
    """
    para.paragraph_format.tab_stops.add_tab_stop(
        content_width(doc), WD_TAB_ALIGNMENT.RIGHT
    )
    return para


def add_bullet(doc, text, density=DEFAULT_DENSITY):
    """Add a bullet point paragraph."""
    para = doc.add_paragraph(style="List Bullet")
    para.paragraph_format.space_before = Pt(1)
    para.paragraph_format.space_after = Pt(1)
    para.clear()
    run = para.add_run(text)
    set_font(run, density=density)
    return para


def build_name_header(doc, data, density=DEFAULT_DENSITY):
    """Add candidate name and contact info."""
    # Name
    para = doc.add_paragraph()
    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    para.paragraph_format.space_after = Pt(2)
    run = para.add_run(data["name"].upper())
    set_font(run, size=NAME_SIZE, bold=True, density=density)

    # Contact line(s)
    contact = data.get("contact", {})
    primary = []
    links = []
    for field in ["email", "phone", "location"]:
        if contact.get(field):
            primary.append(contact[field])
    for field in ["linkedin", "github", "portfolio"]:
        if contact.get(field):
            links.append(contact[field])

    if primary:
        para = doc.add_paragraph()
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        para.paragraph_format.space_before = Pt(0)
        para.paragraph_format.space_after = Pt(2)
        run = para.add_run(" | ".join(primary))
        set_font(run, size=CONTACT_SIZE, density=density)

    if links:
        para = doc.add_paragraph()
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        para.paragraph_format.space_before = Pt(0)
        para.paragraph_format.space_after = Pt(4)
        run = para.add_run(" | ".join(links))
        set_font(run, size=CONTACT_SIZE, color=COLOR_LINK, density=density)


def build_summary(doc, data, density=DEFAULT_DENSITY):
    """Add professional summary."""
    text = (data.get("summary") or "").strip()
    if not text:
        return
    add_section_heading(doc, "Professional Summary", density)
    para = doc.add_paragraph()
    para.paragraph_format.space_before = Pt(density.block_before)
    para.paragraph_format.space_after = Pt(density.block_after)
    run = para.add_run(text)
    set_font(run, density=density)


def build_skills(doc, data, density=DEFAULT_DENSITY):
    """Add skills grouped by category."""
    skills = data.get("skills", [])
    if not skills:
        return
    add_section_heading(doc, "Technical Skills", density)
    for group in skills:
        category = group.get("category", "")
        items = group.get("items", [])
        if not items:
            continue
        para = doc.add_paragraph()
        para.paragraph_format.space_before = Pt(density.block_before)
        para.paragraph_format.space_after = Pt(1)
        cat_run = para.add_run(f"{category}: ")
        set_font(cat_run, bold=True, density=density)
        # items can be a list or a pre-formatted string
        items_text = ", ".join(items) if isinstance(items, list) else str(items)
        items_run = para.add_run(items_text)
        set_font(items_run, density=density)


def build_experience(doc, data, density=DEFAULT_DENSITY):
    """Add professional experience."""
    experience = data.get("experience", [])
    if not experience:
        return
    add_section_heading(doc, "Professional Experience", density)
    for role in experience:
        # Line 1: TITLE ......................................... dates
        para = doc.add_paragraph()
        para.paragraph_format.space_before = Pt(density.role_before)
        para.paragraph_format.space_after = Pt(2)
        add_right_tab(doc, para)

        title_run = para.add_run(role.get("title", "").upper())
        set_font(title_run, size=ROLE_TITLE_SIZE, bold=True, density=density)

        if role.get("dates"):
            date_run = para.add_run("\t" + role["dates"])
            set_font(date_run, color=COLOR_META, density=density)

        # Line 2: Company — Location
        meta_parts = [role.get("company", "")]
        if role.get("location"):
            meta_parts.append(role["location"])
        meta_parts = [p for p in meta_parts if p]
        if meta_parts:
            para.add_run("\n")
            meta_run = para.add_run(" — ".join(meta_parts))
            set_font(meta_run, color=COLOR_META, density=density)

        for bullet in role.get("bullets", []):
            add_bullet(doc, bullet, density)


def build_earlier_career(doc, data, density=DEFAULT_DENSITY):
    """Add earlier career as a compact one-liner: Title at Company, Title at Company."""
    roles = data.get("earlier_career", [])
    if not roles:
        return
    # Support legacy string format as fallback
    if isinstance(roles, str):
        roles = roles.strip()
        if not roles:
            return
        add_section_heading(doc, "Earlier Career", density)
        para = doc.add_paragraph()
        para.paragraph_format.space_before = Pt(density.block_before)
        para.paragraph_format.space_after = Pt(density.block_after)
        run = para.add_run(roles)
        set_font(run, density=density)
        return
    add_section_heading(doc, "Earlier Career", density)
    entries = []
    for role in roles:
        title = role.get("title", "")
        company = role.get("company", "")
        if title and company:
            entries.append(f"{title} at {company}")
        elif company:
            entries.append(company)
    if entries:
        para = doc.add_paragraph()
        para.paragraph_format.space_before = Pt(density.block_before)
        para.paragraph_format.space_after = Pt(density.block_after)
        run = para.add_run(" | ".join(entries))
        set_font(run, density=density)


def build_education(doc, data, density=DEFAULT_DENSITY):
    """Add education."""
    education = data.get("education", [])
    if not education:
        return
    add_section_heading(doc, "Education", density)
    for edu in education:
        para = doc.add_paragraph()
        para.paragraph_format.space_before = Pt(density.block_before)
        para.paragraph_format.space_after = Pt(2)
        add_right_tab(doc, para)
        degree = edu.get("degree", "")
        if degree:
            run = para.add_run(degree)
            set_font(run, bold=True, density=density)
        institution = edu.get("institution", "")
        if institution:
            run = para.add_run(f" \u2014 {institution}")
            set_font(run, density=density)
        dates = edu.get("dates", "")
        if dates:
            run = para.add_run("\t" + dates)
            set_font(run, color=COLOR_META, density=density)
        for detail in edu.get("details", []):
            d_para = doc.add_paragraph()
            d_para.paragraph_format.space_before = Pt(0)
            d_para.paragraph_format.space_after = Pt(0)
            run = d_para.add_run(f"  {detail}")
            set_font(run, color=COLOR_META, density=density)


def build_certifications(doc, data, density=DEFAULT_DENSITY):
    """Add certifications."""
    certs = data.get("certifications", [])
    if not certs:
        return
    add_section_heading(doc, "Certifications", density)
    for cert in certs:
        para = doc.add_paragraph()
        para.paragraph_format.space_before = Pt(1)
        para.paragraph_format.space_after = Pt(1)
        add_right_tab(doc, para)
        run = para.add_run(cert.get("name", ""))
        set_font(run, bold=True, density=density)
        issuer = cert.get("issuer", "")
        if issuer:
            run = para.add_run(f" — {issuer}")
            set_font(run, color=COLOR_META, density=density)
        date = cert.get("date", "")
        if date:
            run = para.add_run("\t" + date)
            set_font(run, color=COLOR_META, density=density)


def build_projects(doc, data, density=DEFAULT_DENSITY):
    """Add projects."""
    projects = data.get("projects", [])
    if not projects:
        return
    add_section_heading(doc, "Projects", density)
    for proj in projects:
        para = doc.add_paragraph()
        para.paragraph_format.space_before = Pt(density.block_before)
        para.paragraph_format.space_after = Pt(2)
        run = para.add_run(proj.get("name", ""))
        set_font(run, bold=True, density=density)
        desc = proj.get("description", "")
        if desc:
            run = para.add_run(f" \u2014 {desc}")
            set_font(run, density=density)
        tech = proj.get("technologies", "")
        if tech:
            run = para.add_run(f" ({tech})")
            set_font(run, color=COLOR_META, density=density)


def build_publications(doc, data, density=DEFAULT_DENSITY):
    """Add publications."""
    pubs = data.get("publications", [])
    if not pubs:
        return
    add_section_heading(doc, "Publications", density)
    for pub in pubs:
        para = doc.add_paragraph()
        para.paragraph_format.space_before = Pt(1)
        para.paragraph_format.space_after = Pt(1)
        run = para.add_run(pub.get("title", ""))
        set_font(run, bold=True, density=density)
        venue = pub.get("venue", "")
        if venue:
            run = para.add_run(f" \u2014 {venue}")
            set_font(run, color=COLOR_META, density=density)


def build_awards(doc, data, density=DEFAULT_DENSITY):
    """Add awards."""
    awards = data.get("awards", [])
    if not awards:
        return
    add_section_heading(doc, "Awards", density)
    for award in awards:
        para = doc.add_paragraph()
        para.paragraph_format.space_before = Pt(1)
        para.paragraph_format.space_after = Pt(1)
        run = para.add_run(award.get("name", ""))
        set_font(run, bold=True, density=density)
        details = award.get("details", "")
        if details:
            run = para.add_run(f" \u2014 {details}")
            set_font(run, color=COLOR_META, density=density)


def generate_resume(data, output_path, template_path=None, density=None,
                    target_pages=None, requested_density=None):
    """Generate the complete .docx resume from JSON data.

    Spacing adapts to the resume in hand. Preferences may be supplied three
    ways, in precedence order: the `density`/`target_pages` arguments (the CLI
    flags), a "layout" object in the JSON content, then the automatic choice.
    Returns (density, note) describing what was selected and why.
    """
    layout = data.get("layout") or {}
    if requested_density is None:
        requested_density = layout.get("density", "auto")
    if target_pages is None:
        target_pages = layout.get("target_pages")

    if density is None:
        density, note = choose_density(data, target_pages, requested_density)
    else:
        note = f"density '{density.name}' supplied by caller"

    doc, dropped_from_template = open_base_document(template_path)

    # Margins
    for section in doc.sections:
        margin = Inches(density.margin_in)
        section.top_margin = margin
        section.bottom_margin = margin
        section.left_margin = margin
        section.right_margin = margin

    # Default style
    style = doc.styles["Normal"]
    style.font.name = FONT_NAME
    style.font.size = density.pt(BODY_SIZE)
    style.paragraph_format.space_before = Pt(0)
    style.paragraph_format.space_after = Pt(2)

    # Build sections in standard order (per resume-formatting.md)
    build_name_header(doc, data, density)
    build_summary(doc, data, density)
    build_skills(doc, data, density)
    build_experience(doc, data, density)
    build_earlier_career(doc, data, density)
    build_education(doc, data, density)
    build_certifications(doc, data, density)
    build_projects(doc, data, density)
    build_publications(doc, data, density)
    build_awards(doc, data, density)

    doc.save(str(output_path))
    return density, note, dropped_from_template


def main():
    parser = argparse.ArgumentParser(
        description="Generate a .docx resume from JSON content"
    )
    parser.add_argument("content", help="Path to JSON file with resume content")
    parser.add_argument("output", help="Output .docx file path")
    parser.add_argument("--template", help="Optional .docx template file")
    parser.add_argument(
        "--density",
        choices=["auto", *DENSITY_BY_NAME],
        help="Spacing preset. Default 'auto': adapt to this resume's content "
             "(overrides layout.density in the JSON).",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Report what would be produced without writing the .docx",
    )
    parser.add_argument(
        "--target-pages",
        type=int,
        help="Page goal, e.g. 1 or 2. Auto mode picks the loosest spacing that "
             "meets it (overrides layout.target_pages in the JSON).",
    )
    args = parser.parse_args()

    content_path = Path(args.content)
    if not content_path.exists():
        print(f"Error: {content_path} not found", file=sys.stderr)
        sys.exit(1)

    try:
        data = json.loads(content_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {content_path}: {e}", file=sys.stderr)
        sys.exit(1)

    if "name" not in data:
        print("Error: JSON must include 'name' field", file=sys.stderr)
        sys.exit(1)

    output_path = Path(args.output)

    if args.dry_run:
        try:
            layout = data.get("layout") or {}
            density, note = choose_density(
                data,
                args.target_pages or layout.get("target_pages"),
                args.density or layout.get("density", "auto"),
            )
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        print(json.dumps({
            "status": "dry_run",
            "would_write": str(output_path),
            "exists_already": output_path.exists(),
            "sections": [
                k for k in ["summary", "skills", "experience", "earlier_career",
                            "education", "certifications", "projects",
                            "publications", "awards"]
                if data.get(k)
            ],
            "layout": {
                "density": density.name,
                "margin_inches": density.margin_in,
                "estimated_pages": round(estimate_pages(data, density), 2),
                "metrics_source": metrics_source(),
                "reason": note,
            },
            "note": "estimate only; no render performed and nothing written",
        }, indent=2))
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        density, note, dropped = generate_resume(
            data,
            output_path,
            args.template,
            target_pages=args.target_pages,
            requested_density=args.density,
        )
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # With an explicit page goal, confirm against a real render rather than
    # trusting the estimate, and tighten if it missed. Silently skipped when
    # LibreOffice is not installed.
    layout = data.get("layout") or {}
    target_pages = args.target_pages or layout.get("target_pages")
    requested = args.density or layout.get("density", "auto")
    actual_pages, last_fill = verify_layout(output_path)

    # No page goal: the estimator alone cannot reliably spot a trailing page
    # holding a few lines, so when a renderer is available, measure the real
    # fill and tighten while that actually removes a page.
    if not target_pages and requested == "auto" and actual_pages and last_fill is not None:
        index = DENSITIES.index(density)
        while (
            last_fill <= STRAGGLER_PAGE_FRACTION
            and actual_pages > 1
            and index < len(DENSITIES) - 1
        ):
            index += 1
            candidate = DENSITIES[index]
            generate_resume(data, output_path, args.template, density=candidate)
            new_pages, new_fill = verify_layout(output_path)
            if not new_pages or new_pages >= actual_pages:
                # Tightening did not buy a page; keep the roomier layout.
                generate_resume(data, output_path, args.template, density=density)
                break
            density, actual_pages, last_fill = candidate, new_pages, new_fill
            note = (
                f"auto: tightened to '{density.name}' to absorb a trailing page "
                f"that held only a few lines; now {actual_pages} pages"
            )

    if target_pages and requested == "auto" and actual_pages is not None:
        start = DENSITIES.index(density)
        while actual_pages > target_pages and start < len(DENSITIES) - 1:
            start += 1
            density = DENSITIES[start]
            density, note, _ = generate_resume(
                data, output_path, args.template, density=density
            )
            note = (
                f"auto: tightened to '{density.name}' after a render showed "
                f"{actual_pages} pages against a {target_pages}-page goal"
            )
            actual_pages = verify_page_count(output_path)
        if actual_pages and actual_pages > target_pages:
            note += (
                f" -- still {actual_pages} pages at the tightest preset; "
                f"trim content to reach {target_pages}"
            )
        elif actual_pages:
            # The render is authoritative; do not leave a pessimistic estimate
            # standing when the document demonstrably meets the goal.
            note = (
                f"auto: '{density.name}' -- render confirms {actual_pages} "
                f"page(s), meeting the {target_pages}-page goal"
            )

    # Report
    sections_present = [
        k for k in ["summary", "skills", "experience", "earlier_career",
                     "education", "certifications", "projects",
                     "publications", "awards"]
        if data.get(k)
    ]
    result = {
        "status": "generated",
        "output": str(output_path),
        "sections": sections_present,
        "template_content_dropped": dropped,
        "layout": {
            "density": density.name,
            "margin_inches": density.margin_in,
            "estimated_pages": round(estimate_pages(data, density), 2),
            "metrics_source": metrics_source(),
            "actual_pages": actual_pages,
            "last_page_fill": round(last_fill, 2) if last_fill is not None else None,
            "reason": note,
        },
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
