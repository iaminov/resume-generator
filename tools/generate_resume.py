#!/usr/bin/env python3
"""Generate a .docx resume from a JSON content file.

This script is a GENERIC formatter. It takes structured JSON describing
the tailored resume content (already selected and written by Claude) and
produces a formatted Word document. It does NOT contain any person-specific
content — all content comes from the JSON input.

Usage:
    python3 tools/generate_resume.py content.json output.docx
    python3 tools/generate_resume.py content.json output.docx --template templates/default.docx

JSON input format:
{
  "name": "Full Name",
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
import sys
from pathlib import Path

from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement


# Formatting constants (from resume-formatting.md)
FONT_NAME = "Calibri"
NAME_SIZE = Pt(14)
SECTION_HEADING_SIZE = Pt(11)
BODY_SIZE = Pt(10)
CONTACT_SIZE = Pt(10)
ROLE_TITLE_SIZE = Pt(10.5)
MARGIN = Inches(0.6)
COLOR_HEADING = RGBColor(0x1A, 0x1A, 0x1A)
COLOR_BODY = RGBColor(0x00, 0x00, 0x00)
COLOR_META = RGBColor(0x55, 0x55, 0x55)
COLOR_LINK = RGBColor(0x26, 0x5B, 0x8C)
BORDER_COLOR = "999999"


def set_font(run, size=BODY_SIZE, bold=False, color=COLOR_BODY):
    """Apply font formatting to a run."""
    run.font.name = FONT_NAME
    run.font.size = size
    run.font.bold = bold
    run.font.color.rgb = color


def add_section_heading(doc, text):
    """Add a section heading with a bottom border line."""
    para = doc.add_paragraph()
    para.paragraph_format.space_before = Pt(10)
    para.paragraph_format.space_after = Pt(4)

    run = para.add_run(text.upper())
    set_font(run, size=SECTION_HEADING_SIZE, bold=True, color=COLOR_HEADING)

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


def add_bullet(doc, text):
    """Add a bullet point paragraph."""
    para = doc.add_paragraph(style="List Bullet")
    para.paragraph_format.space_before = Pt(1)
    para.paragraph_format.space_after = Pt(1)
    para.clear()
    run = para.add_run(text)
    set_font(run)
    return para


def build_name_header(doc, data):
    """Add candidate name and contact info."""
    # Name
    para = doc.add_paragraph()
    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    para.paragraph_format.space_after = Pt(2)
    run = para.add_run(data["name"].upper())
    set_font(run, size=NAME_SIZE, bold=True)

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
        set_font(run, size=CONTACT_SIZE)

    if links:
        para = doc.add_paragraph()
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        para.paragraph_format.space_before = Pt(0)
        para.paragraph_format.space_after = Pt(4)
        run = para.add_run(" | ".join(links))
        set_font(run, size=CONTACT_SIZE, color=COLOR_LINK)


def build_summary(doc, data):
    """Add professional summary."""
    text = (data.get("summary") or "").strip()
    if not text:
        return
    add_section_heading(doc, "Professional Summary")
    para = doc.add_paragraph()
    para.paragraph_format.space_before = Pt(2)
    para.paragraph_format.space_after = Pt(4)
    run = para.add_run(text)
    set_font(run)


def build_skills(doc, data):
    """Add skills grouped by category."""
    skills = data.get("skills", [])
    if not skills:
        return
    add_section_heading(doc, "Technical Skills")
    for group in skills:
        category = group.get("category", "")
        items = group.get("items", [])
        if not items:
            continue
        para = doc.add_paragraph()
        para.paragraph_format.space_before = Pt(2)
        para.paragraph_format.space_after = Pt(1)
        cat_run = para.add_run(f"{category}: ")
        set_font(cat_run, bold=True)
        # items can be a list or a pre-formatted string
        items_text = ", ".join(items) if isinstance(items, list) else str(items)
        items_run = para.add_run(items_text)
        set_font(items_run)


def build_experience(doc, data):
    """Add professional experience."""
    experience = data.get("experience", [])
    if not experience:
        return
    add_section_heading(doc, "Professional Experience")
    for role in experience:
        # Line 1: TITLE ......................................... dates
        para = doc.add_paragraph()
        para.paragraph_format.space_before = Pt(8)
        para.paragraph_format.space_after = Pt(2)
        add_right_tab(doc, para)

        title_run = para.add_run(role.get("title", "").upper())
        set_font(title_run, size=ROLE_TITLE_SIZE, bold=True)

        if role.get("dates"):
            date_run = para.add_run("\t" + role["dates"])
            set_font(date_run, color=COLOR_META)

        # Line 2: Company — Location
        meta_parts = [role.get("company", "")]
        if role.get("location"):
            meta_parts.append(role["location"])
        meta_parts = [p for p in meta_parts if p]
        if meta_parts:
            para.add_run("\n")
            meta_run = para.add_run(" — ".join(meta_parts))
            set_font(meta_run, color=COLOR_META)

        for bullet in role.get("bullets", []):
            add_bullet(doc, bullet)


def build_earlier_career(doc, data):
    """Add earlier career as a compact one-liner: Title at Company, Title at Company."""
    roles = data.get("earlier_career", [])
    if not roles:
        return
    # Support legacy string format as fallback
    if isinstance(roles, str):
        roles = roles.strip()
        if not roles:
            return
        add_section_heading(doc, "Earlier Career")
        para = doc.add_paragraph()
        para.paragraph_format.space_before = Pt(2)
        para.paragraph_format.space_after = Pt(4)
        run = para.add_run(roles)
        set_font(run)
        return
    add_section_heading(doc, "Earlier Career")
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
        para.paragraph_format.space_before = Pt(2)
        para.paragraph_format.space_after = Pt(4)
        run = para.add_run(" | ".join(entries))
        set_font(run)


def build_education(doc, data):
    """Add education."""
    education = data.get("education", [])
    if not education:
        return
    add_section_heading(doc, "Education")
    for edu in education:
        para = doc.add_paragraph()
        para.paragraph_format.space_before = Pt(2)
        para.paragraph_format.space_after = Pt(2)
        add_right_tab(doc, para)
        degree = edu.get("degree", "")
        if degree:
            run = para.add_run(degree)
            set_font(run, bold=True)
        institution = edu.get("institution", "")
        if institution:
            run = para.add_run(f" \u2014 {institution}")
            set_font(run)
        dates = edu.get("dates", "")
        if dates:
            run = para.add_run("\t" + dates)
            set_font(run, color=COLOR_META)
        for detail in edu.get("details", []):
            d_para = doc.add_paragraph()
            d_para.paragraph_format.space_before = Pt(0)
            d_para.paragraph_format.space_after = Pt(0)
            run = d_para.add_run(f"  {detail}")
            set_font(run, color=COLOR_META)


def build_certifications(doc, data):
    """Add certifications."""
    certs = data.get("certifications", [])
    if not certs:
        return
    add_section_heading(doc, "Certifications")
    for cert in certs:
        para = doc.add_paragraph()
        para.paragraph_format.space_before = Pt(1)
        para.paragraph_format.space_after = Pt(1)
        add_right_tab(doc, para)
        run = para.add_run(cert.get("name", ""))
        set_font(run, bold=True)
        issuer = cert.get("issuer", "")
        if issuer:
            run = para.add_run(f" — {issuer}")
            set_font(run, color=COLOR_META)
        date = cert.get("date", "")
        if date:
            run = para.add_run("\t" + date)
            set_font(run, color=COLOR_META)


def build_projects(doc, data):
    """Add projects."""
    projects = data.get("projects", [])
    if not projects:
        return
    add_section_heading(doc, "Projects")
    for proj in projects:
        para = doc.add_paragraph()
        para.paragraph_format.space_before = Pt(2)
        para.paragraph_format.space_after = Pt(2)
        run = para.add_run(proj.get("name", ""))
        set_font(run, bold=True)
        desc = proj.get("description", "")
        if desc:
            run = para.add_run(f" \u2014 {desc}")
            set_font(run)
        tech = proj.get("technologies", "")
        if tech:
            run = para.add_run(f" ({tech})")
            set_font(run, color=COLOR_META)


def build_publications(doc, data):
    """Add publications."""
    pubs = data.get("publications", [])
    if not pubs:
        return
    add_section_heading(doc, "Publications")
    for pub in pubs:
        para = doc.add_paragraph()
        para.paragraph_format.space_before = Pt(1)
        para.paragraph_format.space_after = Pt(1)
        run = para.add_run(pub.get("title", ""))
        set_font(run, bold=True)
        venue = pub.get("venue", "")
        if venue:
            run = para.add_run(f" \u2014 {venue}")
            set_font(run, color=COLOR_META)


def build_awards(doc, data):
    """Add awards."""
    awards = data.get("awards", [])
    if not awards:
        return
    add_section_heading(doc, "Awards")
    for award in awards:
        para = doc.add_paragraph()
        para.paragraph_format.space_before = Pt(1)
        para.paragraph_format.space_after = Pt(1)
        run = para.add_run(award.get("name", ""))
        set_font(run, bold=True)
        details = award.get("details", "")
        if details:
            run = para.add_run(f" \u2014 {details}")
            set_font(run, color=COLOR_META)


def generate_resume(data, output_path, template_path=None):
    """Generate the complete .docx resume from JSON data."""
    if template_path and Path(template_path).exists():
        doc = Document(template_path)
    else:
        doc = Document()

    # Margins
    for section in doc.sections:
        section.top_margin = MARGIN
        section.bottom_margin = MARGIN
        section.left_margin = MARGIN
        section.right_margin = MARGIN

    # Default style
    style = doc.styles["Normal"]
    style.font.name = FONT_NAME
    style.font.size = BODY_SIZE
    style.paragraph_format.space_before = Pt(0)
    style.paragraph_format.space_after = Pt(2)

    # Build sections in standard order (per resume-formatting.md)
    build_name_header(doc, data)
    build_summary(doc, data)
    build_skills(doc, data)
    build_experience(doc, data)
    build_earlier_career(doc, data)
    build_education(doc, data)
    build_certifications(doc, data)
    build_projects(doc, data)
    build_publications(doc, data)
    build_awards(doc, data)

    doc.save(str(output_path))


def main():
    parser = argparse.ArgumentParser(
        description="Generate a .docx resume from JSON content"
    )
    parser.add_argument("content", help="Path to JSON file with resume content")
    parser.add_argument("output", help="Output .docx file path")
    parser.add_argument("--template", help="Optional .docx template file")
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
    output_path.parent.mkdir(parents=True, exist_ok=True)

    generate_resume(data, output_path, args.template)

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
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
