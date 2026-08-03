# Resume AI - Multi-Agent Resume Optimization System

## Project Overview
Multi-agent system that parses resumes, builds skills databases, and generates
tailored resumes using five specialized agents (Resume Expert, Employer Emulator,
Recruiter, Bias Auditor, Fact Checker) that collaborate through a consensus-based
review process (with a 6th orchestrator agent). It also generates tailored cover
letters through a lighter two-agent workflow.

## Architecture
- **Data format**: JSON files for all structured data (profiles, applications, job descriptions)
- **Resume input**: PDF and Word (.docx) formats in active profile's `input/input-resumes/` directory
- **Resume output**: Word (.docx) format in active profile's `output/output-generated-resumes/` directory
- **Cover letter output**: Word (.docx) in active profile's `output/output-cover-letters/` directory
- **Agent consensus**: 5 agents review each resume, max 5 revision rounds
- **Cover letter review**: 3 agents — writer drafts, fact-checker and employer-emulator review once in parallel
- **Multi-person**: Each person gets their own directory under `data/profiles/` containing all their data

## Directory Structure
```
data/
  .active-profile              # Active person slug (e.g., "jane-doe")
  profiles/
    {slug}/
      profile.json                       # Comprehensive extracted profile (single source of truth)
      input/
        input-resumes/                   # Input: person's PDF/DOCX resume files
        input-job-postings/              # Input: job posting PDF/DOCX/TXT files to apply for
          processed/                     # Postings already turned into a resume;
                                          #   move a file back out to reprocess it
        input-voice-samples/             # OPTIONAL: the person's own writing, used to
                                          #   match voice in cover letters. Empty is fine —
                                          #   the letter falls back to a generic voice
        input-notes/                     # Notes, ideas, open questions, third-party
                                          #   feedback. Guidance only, NEVER parsed as fact
      applications/                      # JSON: application tracking records
      output/
        output-job-descriptions/         # JSON: parsed/structured job postings
        output-generated-resumes/        # Output: tailored DOCX resumes
        output-cover-letters/            # Output: tailored DOCX cover letters
tools/                         # Shared utility scripts (see Tools section below)
templates/                     # DOCX resume templates (shared)
schemas/                       # JSON Schema files for data validation (shared)
```

## Agent System
Seven agents. Resume generation uses six of them via the orchestrator pattern:
1. **orchestrator** - Coordinates workflow, manages consensus rounds
2. **resume-expert** - Resume writing specialist, formatting, ATS optimization
3. **employer-emulator** - Thinks like a hiring manager, evaluates fit
4. **recruiter** - Independent recruiter perspective, market positioning
5. **bias-auditor** - Audits for age, gender, ethnicity, disability, and other bias exposure
6. **fact-checker** - Verifies every claim against profile.json; has veto power on accuracy

Cover letter generation uses three:
7. **cover-letter-writer** - Drafts the letter, optionally matching the person's voice

`fact-checker` and `employer-emulator` then review it once in parallel, with at
most one revision round. Only the fact-checker can block; the emulator advises.
Two reviewers cover the failure modes that matter for a letter — fabrication,
and failing to persuade — and no more are added on purpose: consensus sands
prose toward the safe middle, and sounding like a specific person is the only
advantage a cover letter has over the resume.

See `.claude/agents/` for full agent definitions.

## Key Rules
- **NEVER fabricate skills or experience** - only use data from parsed resumes
- **NEVER hallucinate dates, titles, or company names** - accuracy is critical
- **NEVER write custom scripts to analyze resume content** - Claude IS the parser.
  Use `tools/docx_to_md.py` for DOCX text extraction, Read for PDFs, then
  comprehend the content directly. Do not write Python/scripts for pattern
  matching, skill extraction, or profile building.
- All generated content must be traceable to input resume data
- Validate all JSON against schemas in `schemas/` before writing
- **NEVER silently regenerate a resume for a company+role that already has an
  application record** - `/create-resume` checks `applications/` first and
  asks the user before proceeding. Once a resume is generated, the source
  file in `input-job-postings/` is moved into its `processed/` subfolder;
  moving it back out re-enables it for reprocessing.
- Application records are the central tracking unit — they capture not just the
  resume but the full lifecycle: contacts, interviews, compensation, follow-ups,
  activity log, and outcome. See `schemas/application.schema.json` for the full
  schema.

## Workflow

### Profile management
- `/profile-create` — Create a new person's profile directory and set as active
- `/profile-switch` — Switch active profile to a different person
- `/profile-delete` — Delete a person's profile and all associated data

### Phase 1: Build the profile (run once, update as needed)
`/parse-resumes` uses a two-phase pipeline:
1. **Mechanical extraction**: PDFs are read natively; DOCX files are converted
   to markdown via `tools/docx_to_md.py`
2. **AI comprehension**: Claude reads all extracted text, understands context,
   deduplicates by meaning (not string matching), and builds `profile.json`

Claude IS the parser — no custom scripts for content analysis. The profile is
the **single source of truth** and must exist before any other skill can run.

### Phase 2: Generate tailored resumes (run per job)
`/create-resume` takes a job posting + the active profile and produces a
tailored resume through the 5-agent consensus process. It selects the most
relevant subset of the profile's skills and experience for that specific role.
The final resume is generated via `tools/generate_resume.py` — never write
python-docx code inline or create new scripts for DOCX generation.

### Phase 3: Generate a cover letter (optional, per job)
`/create-cover-letter` takes a job posting + the active profile and produces a
tailored letter. The Cover Letter Writer drafts it and the Fact Checker reviews
it once. Voice is **optional**: drop the person's own writing into
`input/input-voice-samples/` to have the letter match how they actually write
(a past cover letter is best, but any substantial prose they wrote will do), or
skip it and take a clear generic professional voice. The skill always offers
both rather than defaulting silently. Samples supply *voice only* — `profile.json`
remains the sole source of facts. Generated via `tools/generate_cover_letter.py`.

### Other commands
- `/review-job` — Analyze a job posting and evaluate fit against a profile
- `/track-application` — Full application lifecycle: status, contacts, interviews, comp, follow-ups, outcome

## Rules
Detailed rules live in `.claude/rules/` and attach automatically by file path:

| File | Covers |
|---|---|
| `data-integrity.md` | Active profile resolution, JSON validation, naming, confidentiality |
| `resume-writing.md` | Content craft: summary thesis, accomplishments over tech dumps, length, sourcing discipline |
| `resume-formatting.md` | Document mechanics: fonts, margins, tab stops, section order, ATS structure |
| `application-tracking.md` | Application record requirements |
| `user-interaction.md` | When to ask the user and when to just execute |

## Notes vs Resumes (CRITICAL)
`input/input-resumes/` is parsed as **fact** — its contents become the person's
own claims in `profile.json`. `input/input-notes/` is parsed as **guidance** —
notes, ideas, open questions, and feedback from coaches or the internet. Nothing
from `input-notes/` may become a skill, experience entry, project, or metric. If
a file's category is unclear it belongs in `input-notes/`; treating guidance as
fact is the damaging direction. See `.claude/rules/data-integrity.md`.

## Source Attribution (CRITICAL)
Input files are not automatically the person's own words. Notes folders often
contain third-party advice, forum threads, and pasted articles whose first-person
claims belong to strangers. **Verify authorship before recording anything in
`profile.json` as the person's own statement, credential, or statistic.** Never
record job-application outcome statistics unless the person states them directly.
See `.claude/rules/resume-writing.md`.

## Data Integrity
- Every profile JSON must validate against `schemas/profile.schema.json`
- Every application JSON must validate against `schemas/application.schema.json`
- Every job description JSON must validate against `schemas/job-description.schema.json`
- Generated resumes must be saved alongside metadata linking to source profile and target job

## Tools (pre-built scripts)

All deterministic operations use pre-built, tested scripts in `tools/`. Skills
must call these scripts — never generate new scripts or write inline code for
these operations.

| Script | Purpose | Usage |
|---|---|---|
| `tools/docx_to_md.py` | Convert single DOCX to markdown | `python3 tools/docx_to_md.py file.docx` |
| `tools/extract_resumes.py` | Batch-extract all resumes for a profile | `python3 tools/extract_resumes.py [--slug name]` |
| `tools/generate_cover_letter.py` | Generate .docx cover letter from JSON content; warns if over one page or 400 words | `python3 tools/generate_cover_letter.py content.json output.docx` |
| `tools/generate_resume.py` | Generate .docx resume from JSON content; spacing adapts to fit a page goal | `python3 tools/generate_resume.py content.json output.docx [--target-pages 1] [--density auto\|normal\|compact\|dense]` |
| `tools/profile_create.py` | Create profile directory structure | `python3 tools/profile_create.py "Full Name" [--slug slug]` |
| `tools/profile_switch.py` | List profiles or switch active | `python3 tools/profile_switch.py [slug]` |
| `tools/profile_delete.py` | Delete a profile (dry-run or confirmed) | `python3 tools/profile_delete.py slug [--confirm]` |
| `tools/validate.py` | Validate JSON against the schemas; `--strict` also checks the data-integrity rules schemas cannot express | `python3 tools/validate.py <file> [--strict]` or `--all` |
| `tools/application_update.py` | Change an application's status or log activity, with transition validation | `python3 tools/application_update.py <record> --status applied` |
| `tools/application_status.py` | Report search state; `--analytics` for outcome rates | `python3 tools/application_status.py [--stale-days N] [--analytics] [--json]` |
| `tools/diff_content.py` | Compare two generated documents by their content sidecars | `python3 tools/diff_content.py old.content.json new.content.json` |

Two modules in `tools/` are shared code rather than CLIs:

- **`common.py`** — the four project paths and the active-profile helpers
  (`get_active_slug`, `set_active_slug`, `profile_dir`). The layout is defined
  once and the active-profile convention from `.claude/rules/data-integrity.md`
  is enforced identically everywhere. New tools should import from it rather
  than recomputing `PROJECT_ROOT`.
- **`layout.py`** — text metrics (`wrapped_lines`, `text_width_pt`) and page
  verification (`verify_layout`, `verify_page_count`). Both generators use it,
  so neither has to import the other.

## Profile Resolution and Versioning

Every tool resolves which profile to use in this order: an explicit `--slug`,
then the `RESUME_AI_PROFILE` environment variable, then `data/.active-profile`,
then a sole existing profile. The environment variable lets one session pin a
profile without disturbing the shared file, so two sessions can work on
different people concurrently.

All profile, application, and job-description JSON carries `schema_version`
(currently `1.0`, defined in `tools/common.py`). `validate.py` warns on a
missing version or a differing major version rather than failing — refusing to
validate would block the very edit that fixes it.

## Dry Runs

Both generators accept `--dry-run`, reporting what they would produce (sections,
chosen density, estimated pages) without writing anything. Use it to check a
page target before committing to a file.

## Tests

```bash
pip install -r requirements-dev.txt && pytest
```

Covers text metrics, page estimation and density selection, slug generation,
active-profile semantics, and schema validation. CI runs them on Python 3.10 and
3.13 and also exercises the generators on a runner without LibreOffice, keeping
the no-renderer fallback honest.

**All fixtures are fictional.** The confidentiality rule applies to tests too —
they are committed, so no real personal data may appear in them.

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

To customise the look, edit `templates/default.docx` in Word (fonts, colours,
bullet glyphs) and pass it with `--template`. Per-run spacing still comes from
the density presets, which override the template's margins.

## Dependencies
Python packages are listed in `requirements.txt`. Install via:
```bash
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
```
(Alternatively, "python" if the "python3" command is not available.)