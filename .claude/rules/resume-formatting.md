---
paths:
  - "data/profiles/*/output/output-generated-resumes/**"
  - "templates/**"
---

# Resume Formatting Standards

## Document Format
- Output format: .docx (Microsoft Word)
- Use python-docx for generation
- Apply consistent fonts: Calibri or Arial, 10-11pt body, 18pt name
- Margins: 0.5-0.75 inches all sides
- Single column layout (no tables, text boxes, or columns - ATS hostile)

## Adaptive Density

`tools/generate_resume.py` picks spacing to suit the resume in hand rather than
applying one fixed look. Three presets vary **margins and section spacing only**
— font sizes never change, because shrinking type to force a fit is what makes a
resume look crammed:

| Preset | Margins | Use |
|---|---|---|
| `normal` | 0.75" | Default. Roomy; right for reference documents and short resumes |
| `compact` | 0.60" | Middle ground |
| `dense` | 0.50" | Content-heavy resumes held to a strict page goal |

Selection, in precedence order:

1. `--density` / `--target-pages` on the command line
2. a `"layout": {"density": ..., "target_pages": ...}` object in the content JSON
3. automatic — start at `normal` and tighten only to reclaim a trailing page
   that would hold just a few lines

**Prefer setting `target_pages` over naming a preset.** State the goal and let
the tool find the loosest spacing that meets it; hardcoding `dense` on a short
resume just wastes white space.

With a page goal set, the tool renders the document through LibreOffice (when
installed) to confirm the real page count and tightens further if the estimate
missed. Without LibreOffice it falls back to the built-in estimator, which runs
about 10% optimistic — treat its output as a guide, not a guarantee.

## Date Alignment
- Dates are right-aligned to the right margin using a **right tab stop**, so
  they form a clean vertical column the reader can scan for chronology
- Applies to Professional Experience, Education, and Certifications
- Layout per role: `TITLE` ⇥ `dates` on line one, `Company — Location` on line two
- **Never use a table to achieve this.** Tables are ATS-hostile: some parsers
  reorder or drop cells. A right tab stop keeps the document genuinely single
  column while producing the same visual result
- The tab stop is placed at page width minus both margins, computed from the
  document section rather than hardcoded, so it stays correct if margins or
  page size change
- `tools/generate_resume.py` applies this automatically — no per-resume work

## Section Order (Standard)
1. Name and contact information (header)
2. Professional Summary (3-4 lines max)
3. Skills / Technical Skills
4. Professional Experience (reverse chronological, last 10-15 years)
5. Earlier Career (if applicable — compact one-liner, no dates)
6. Education
7. Certifications (if relevant)
8. Optional: Projects, Publications, Awards

## Earlier Career Section
When older roles are consolidated (for ageism protection or brevity):
- Format as a single line: `Title at Company | Title at Company | ...`
- No dates, no descriptions, no bullets — just title and company name
- Titles must be exact (from profile.json) — no rewording or inflation
- Must include all older roles needed to avoid creating timeline gaps
  between the earliest detailed role and the start of the candidate's career

## Timeline Continuity (CRITICAL)
The resume must show continuous employment from the earliest included role to
the present. NEVER omit a role if it creates a gap in the timeline.
- Less relevant roles get fewer bullets, not deletion
- Consulting, freelance, and startup roles are real employment — include them
- If in doubt, include at minimal detail (title, company, dates, 1 bullet)
- "Earlier Career" covers the oldest roles but the transition from detailed
  experience to Earlier Career must also be gap-free

## Content Rules
- Professional summary: tailored to target role, not generic
- Skills: grouped by category, match job posting terminology exactly
- Skills section is for HARD skills ONLY — technologies, tools, platforms,
  languages, frameworks, methodologies, and domain/technical competencies.
  NEVER list soft/interpersonal skills there (e.g., Leadership, Mentorship,
  Communication, Cross-functional Collaboration, Vendor Management, Stakeholder
  Management, Teamwork). As a list they are redundant, noisy, and read as
  filler. Convey soft skills by DEMONSTRATING them inside experience bullets
  (e.g., "Led a global team of 15+ engineers across three regions..."), never
  by naming them in the Skills section.
- Experience bullets: start with strong action verb, follow CAR formula
  (Challenge, Action, Result), quantify where data supports it
- Maximum 2 pages for <15 years experience, 3 pages for 15+
- No photos, no personal information beyond contact details
- No "References available upon request"

## ATS Optimization
- Use standard section headings (not creative alternatives)
- No headers/footers (many ATS cannot read them)
- No images, charts, or graphics
- Spell out acronyms at least once
- Include exact keyword matches from job posting where truthful
- Use both spelled-out and abbreviated forms of terms
  (e.g., "Search Engine Optimization (SEO)")
