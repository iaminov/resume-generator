---
paths:
  - "data/profiles/*/generated-resumes/**"
  - "templates/**"
---

# Resume Formatting Standards

## Document Format
- Output format: .docx (Microsoft Word)
- Use python-docx for generation
- Apply consistent fonts: Calibri or Arial, 10-11pt body, 14pt name
- Margins: 0.5-0.75 inches all sides
- Single column layout (no tables, text boxes, or columns - ATS hostile)

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
