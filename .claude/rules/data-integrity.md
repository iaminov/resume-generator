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
- Validate with `python3 tools/validate.py <file>`. It infers the schema from
  the file's location, reports the exact JSON path at fault, and exits non-zero
  so it can gate a workflow. `--all` checks every profile in one pass.
- If validation fails, fix the data. Do not skip validation, and do not
  hand-roll a one-off check — a forgotten check is how an invalid profile gets
  written in the first place
- Never write partial or malformed JSON files

## Profile Data

- Skills and experience MUST come from parsed source resumes only
- Every entry in a profile must include `source_file` -- the filename of the
  original resume within the person's `input/input-resumes/` directory (e.g.,
  `resume_v1.pdf`, not a full path)
- Proficiency levels must be inferred from evidence, not assumed
- Dates must be in ISO 8601 format (YYYY-MM-DD or YYYY-MM)
- Do not merge profiles across different people without explicit user confirmation

## Application Data

- Application records are append-only for status history (never delete past statuses)
- Status changes must include a timestamp
- The job description snapshot must be saved at time of application (URLs go stale)
- Resume version used must reference the generated file within the person's
  `output/output-generated-resumes/` directory
- All file references in application records are relative to the person's
  profile directory (e.g., `output/output-job-descriptions/google_senior-swe_2026-04-12.json`)
- Before creating a new application, check `applications/` for an existing
  record with the same company + role. If one exists, surface it to the user
  (status, resume file, created date, whether `profile.json` is newer) and
  ask before generating another resume for the same job — never silently
  create a duplicate

## Per-Person Directory Structure

Each person's data lives under `data/profiles/{slug}/`:

```
data/profiles/{slug}/
  profile.json                        # Comprehensive extracted profile
  input/
    input-resumes/                    # Input PDF/DOCX resume files
    input-job-postings/               # Input job posting PDF/DOCX/TXT files
      processed/                      # Postings already turned into a resume
                                       #   (moved here by /create-resume; move
                                       #   a file back out to reprocess it)
    input-voice-samples/              # OPTIONAL writing samples for cover-letter
                                       #   voice matching (see below)
  applications/                       # Application tracking records
  output/
    output-job-descriptions/          # Parsed/structured job postings (JSON)
    output-generated-resumes/         # Tailored resume output
    output-cover-letters/             # Tailored cover letter output
```

## Voice Samples

`input/input-voice-samples/` is optional and may be empty — `/create-cover-letter`
falls back to a generic professional voice and must always tell the user both
options exist rather than defaulting silently.

When samples are present:

- They must be the person's **own** writing. Verify authorship before using
  them, per the Source Attribution rules — a pasted article or forwarded email
  is not their voice.
- They supply **voice only, never facts**. Any claim appearing in a sample must
  still be corroborated by `profile.json` before it can enter a generated
  document. A past cover letter may well contain claims that were never true.
- Do not copy sentences from a sample into generated output. Match the manner,
  not the wording.

## File Naming Conventions

- Profile: `profile.json` (inside `data/profiles/{slug}/`)
- Applications: `{YYYY-MM-DD}_{company-slug}_{role-slug}.json`
- Job descriptions: `{company-slug}_{role-slug}_{YYYY-MM-DD}.json`
- Generated resumes: `{First}_{Last}_{company-slug}_{role-slug}_{YYYY-MM-DD}.docx`
  (e.g., `Jane_Doe_acme_senior-platform-engineer_2026-05-26.docx`)
- Generated cover letters: same stem plus `_cover-letter.docx`
  (e.g., `Jane_Doe_acme_senior-platform-engineer_2026-05-26_cover-letter.docx`)

## Content Sidecars

Every generated .docx MUST be saved alongside the JSON it was built from, named
`{same-stem}.content.json`:

```
Jane_Doe_acme_senior-platform-engineer_2026-05-26.docx
Jane_Doe_acme_senior-platform-engineer_2026-05-26.content.json
```

A .docx cannot be read back into structured content, so without the sidecar even
a one-line change means regenerating the whole document from the profile and
re-running the agent workflow. With it, a revision is an edit plus one command.

The sidecar is also where per-document layout preferences live — the `layout`
block (`density`, `target_pages`) that `tools/generate_resume.py` reads. Losing
it loses the page target the document was tuned to.

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
