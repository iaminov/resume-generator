---
paths:
  - "data/profiles/**"
  - "schemas/**"
---

# Data Integrity Rules

## Active Profile

All skills that operate on person data must resolve the active profile first:

1. Read `data/.active-profile` to get the active person slug
2. If set → use `data/profiles/{slug}/` as the person's root directory
3. If not set and exactly one profile exists → use it automatically
4. If not set and multiple exist → tell user to run `/profile-switch`
5. If no profiles exist → tell user to run `/profile-create`

## JSON Validation

- Every JSON file written to `data/profiles/` MUST validate against its
  corresponding schema in `schemas/` before being saved
- Use `jsonschema` to validate. If validation fails, fix the data, do not
  skip validation
- Never write partial or malformed JSON files

## Profile Data

- Skills and experience MUST come from parsed source resumes only
- Every entry in a profile must include `source_file` -- the filename of the
  original resume within the person's `source-resumes/` directory (e.g.,
  `resume_v1.pdf`, not a full path)
- Proficiency levels must be inferred from evidence, not assumed
- Dates must be in ISO 8601 format (YYYY-MM-DD or YYYY-MM)
- Do not merge profiles across different people without explicit user confirmation

## Application Data

- Application records are append-only for status history (never delete past statuses)
- Status changes must include a timestamp
- The job description snapshot must be saved at time of application (URLs go stale)
- Resume version used must reference the generated file within the person's
  `generated-resumes/` directory
- All file references in application records are relative to the person's
  profile directory (e.g., `job-descriptions/google_senior-swe_2026-04-12.json`)

## Per-Person Directory Structure

Each person's data lives under `data/profiles/{slug}/`:

```
data/profiles/{slug}/
  profile.json               # Comprehensive extracted profile
  source-resumes/            # Input PDF/DOCX resume files
  job-postings/              # Input job posting PDF/DOCX files
  applications/              # Application tracking records
  job-descriptions/          # Parsed/structured job postings (JSON)
  generated-resumes/         # Tailored resume output
```

## File Naming Conventions

- Profile: `profile.json` (inside `data/profiles/{slug}/`)
- Applications: `{YYYY-MM-DD}_{company-slug}_{role-slug}.json`
- Job descriptions: `{company-slug}_{role-slug}_{YYYY-MM-DD}.json`
- Generated resumes: `{First}_{Last}_{company-slug}_{role-slug}_{YYYY-MM-DD}.docx`
  (e.g., `Jane_Doe_acme_senior-platform-engineer_2026-05-26.docx`)

### Company Slug Rules

The `{company-slug}` in filenames MUST be the actual company name slugified,
not a description or category. Use the `company` field from the job posting.

- "Goldman Sachs" → `goldman-sachs`
- "JPMorgan Chase" → `jpmorgan-chase`
- NEVER use descriptions like `private-equity-firm`, `big-tech-company`, `startup`
- If the company name is unknown at file creation time, use the best known
  name and rename later when clarified

## Confidentiality

- NEVER use real user names, company names, or other personal data in code,
  documentation, examples, comments, or commit messages
- All examples in docs, docstrings, skills, and rules must use generic
  placeholders: "Jane Doe", "Acme Corp", "jane-doe", "acme", etc.
- User data lives only in `data/profiles/` (which is gitignored) — nowhere else
