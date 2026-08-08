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

A fourth preset, `ultra` (0.30" margins, every font scaled to 95%), sits outside
that ladder. **Automatic selection never reaches it** — it applies only when
named with `--density ultra` or `"density": "ultra"` in the content JSON.

It exists because the one-page target and the no-shrinking rule genuinely
conflict for a candidate with more real material than a page holds, and the
candidate's own stated preference wins that conflict (see `resume-writing.md`).
Two constraints on using it:

- **Cut weak content first.** Reach for `ultra` only once the remaining
  material is all worth keeping, never to avoid editing.
- **It is the candidate's call, not the tool's.** Do not select it to rescue a
  draft that was simply written long.

Font sizes scale uniformly and are rounded to the half-point Word stores, so the
name / heading / role-title / body hierarchy survives the scaling rather than
collapsing into one size.

Selection, in precedence order:

1. `--density` / `--target-pages` on the command line
2. a `"layout": {"density": ..., "target_pages": ...}` object in the content JSON
3. automatic — start at `normal` and tighten only to reclaim a trailing page
   that would hold just a few lines

**Prefer setting `target_pages` over naming a preset.** State the goal and let
the tool find the loosest spacing that meets it; hardcoding `dense` on a short
resume just wastes white space.

When LibreOffice is installed the tool renders the document to settle both
checks against reality rather than arithmetic:

- with a page goal, it confirms the real count and tightens if the estimate missed
- with no goal, it measures how full the last page is and tightens while that
  actually removes a page, so a trailing page holding two lines gets absorbed

Without LibreOffice it falls back to the built-in estimator, which runs about
10% optimistic — treat its output as a guide, not a guarantee. The estimator
alone is not reliable enough to catch a straggler: it once put a document at
4.97 pages when the real render was six, the last holding two lines.

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

## Templates

`templates/default.docx` is the base document both generators can start from
(`--template`). A template supplies **styles, not content**:

- Any body content in it is stripped before generating, and reported in the
  tool's output. python-docx opens a .docx whole, so leftover text would
  otherwise be prepended to every document produced from it.
- It must define `Normal` and `List Bullet`. A .docx saved out of Word that
  never used a bulleted list will not define `List Bullet`, and the generators
  reference it by name.
- A missing template path is an error, not a silent fallback — a typo would
  otherwise produce an unstyled document with no warning.

Templates are **optional** — both generators produce a complete, correctly
styled document without one, and `--template` defaults to none.

A user supplying their own puts a `.docx` in `templates/` and passes
`--template templates/theirs.docx`. Any path works, but `templates/` is the
convention and `.gitignore` has an exception so `.docx` files there are
versioned rather than treated as generated output. The easiest starting point
is a copy of `templates/default.docx`.

Per-run spacing still comes from the density presets, which override the
template's margins.
