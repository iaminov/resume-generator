---
name: parse-resumes
description: Read all resumes for the active profile, comprehend them as an AI, and build a comprehensive profile.json
---

# Parse Resumes Skill

Build a comprehensive, deduplicated profile by reading and **understanding** every
resume in the active profile's `source-resumes/` directory. The output `profile.json`
becomes the single source of truth for all downstream skills.

## Architecture: Two-Phase Pipeline

**Phase A — Mechanical text extraction** (one script call, no AI needed):
Run `python3 tools/extract_resumes.py` — it converts all DOCX files to `.md`
files alongside the originals. PDFs are read natively by Claude via Read tool.

**Phase B — AI comprehension** (Claude reads everything, builds the profile):
Read every extracted `.md` file and every PDF. Understand context, infer skills,
assess relevancy, deduplicate by **meaning**. Synthesize into a structured profile.

Phase B is the hard part and the whole point. Do NOT write scripts for it.
You ARE the parser.

## Steps

### 0. Resolve active profile

Run `python3 tools/profile_switch.py` to get the active profile slug.
If none set, tell user to run `/profile-switch` or `/profile-create`.

### 1. Extract all resumes (Phase A — one command)

Run:
```
python3 tools/extract_resumes.py
```

This single command:
- Finds all DOCX and PDF files in the active profile's `source-resumes/`
- Converts every DOCX to a `.md` file in the same directory
- Returns a JSON manifest listing all files, their types, and any errors

Parse the JSON output. Report the file count to the user. If no files found, stop.

Do NOT write bash loops, temp directories, or custom extraction scripts.
This one command handles all extraction.

### 2. Read all extracted content (Phase B begins)

For each file listed in the manifest:
- **DOCX** (now `.md`): Read the `.md` file with the Read tool
- **PDF**: Read the PDF directly with the Read tool (native multimodal support)

Read every file. Do not skip any.

### 3. Comprehend all resumes (Phase B — AI understanding)

Now you have the full text of every resume. Read them all carefully and build
your understanding of this person. This is where your value is — not in regex
or pattern matching, but in comprehension:

**Understand the person holistically:**
- What is their career arc? Where are they heading?
- What are their core competencies vs. peripheral skills?
- What seniority level do they operate at?
- What industries/domains do they know?

**Extract structured data with understanding:**
- **Contact info**: Synthesize the most complete version across all resumes
- **Professional summary**: Capture all unique summaries as raw material
- **Skills**: Identify skills from explicit lists AND from context within
  experience bullets. Categorize them. Assess proficiency from evidence
  (someone who "architected" a system is more proficient than someone who
  "assisted with" one)
- **Experience**: Extract every role with full detail. When the same role
  appears in multiple resumes with different bullets, understand which
  bullets describe the same accomplishment in different words vs. genuinely
  different achievements. Keep the strongest version of each unique
  accomplishment.
- **Education, Certifications, Projects, Awards, Publications**: Extract all

**Deduplicate by meaning, not strings:**
- "Led migration to microservices" and "Architected service decomposition
  from monolith" may be the same accomplishment — use judgment
- "Python" listed in skills and "Built data pipeline in Python" in experience
  are the same skill — unify with the richer evidence
- A role at "Google LLC" and "Google" is the same company

**Flag what's uncertain:**
- Ambiguous dates or gaps
- Skills that are mentioned but with unclear proficiency
- Roles where the scope or impact is unclear

### 4. Check for existing profile

If `data/profiles/{slug}/profile.json` already exists:
- Compare what you found against the existing profile
- Show what's new or different
- Ask: merge new data into existing profile, or rebuild from scratch?

### 5. Build and validate the profile JSON

Structure everything into a JSON object that validates against
`schemas/profile.schema.json`. Key requirements:
- Every entry must include `source_file` (filename only, e.g. `resume_v1.pdf`)
- Skills need: name, category, proficiency (with evidence), source_file
- Experience needs: company, title, dates, bullets, skills_used, source_file
- Use ISO 8601 dates (YYYY-MM or YYYY-MM-DD)

Validate against the schema using jsonschema. Fix any issues before saving.

### 6. Save

Write to `data/profiles/{slug}/profile.json`.

### 7. Report

Present a comprehensive summary:
```
Profile: {Full Name} ({slug})
Source files: N resumes parsed

Skills: N total across M categories
  [list top skills by category]

Experience: N roles across M companies
  [list roles with date ranges]

Education: N entries
Certifications: N

Deduplication notes:
  [what was merged, what was the stronger version chosen]

Flagged for review:
  [any ambiguities, uncertain data, or discrepancies]
```

## Critical Rules

- **Use the provided tools** — run `extract_resumes.py` once for extraction.
  Do NOT write bash loops, temp directories, or custom scripts.
- **You are the parser** — do NOT write Python scripts to analyze resume content,
  match patterns, or build the profile. Read the text and use your comprehension.
- **NEVER invent or assume data** not present in the source resumes
- **Read ALL resumes** — the whole point is comprehensive extraction
- Preserve exact dates, titles, and company names as written
- Track `source_file` (filename only) in every extracted record
- Deduplicate by **meaning and context**, not string comparison
- The output must contain the **union** of all unique information across resumes
