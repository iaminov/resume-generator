# Resume AI - Multi-Agent Resume Optimization System

## Project Overview
Multi-agent system that parses resumes, builds skills databases, and generates
tailored resumes using five specialized agents (Resume Expert, Employer Emulator,
Recruiter, Bias Auditor, Fact Checker) that collaborate through a consensus-based
review process (with a 6th orchestrator agent).

## Architecture
- **Data format**: JSON files for all structured data (profiles, applications, job descriptions)
- **Resume input**: PDF and Word (.docx) formats in active profile's `input/input-resumes/` directory
- **Resume output**: Word (.docx) format in active profile's `output/output-generated-resumes/` directory
- **Agent consensus**: 5 agents review each resume, max 5 revision rounds
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
      applications/                      # JSON: application tracking records
      output/
        output-job-descriptions/         # JSON: parsed/structured job postings
        output-generated-resumes/        # Output: tailored DOCX resumes
tools/                         # Shared utility scripts (see Tools section below)
templates/                     # DOCX resume templates (shared)
schemas/                       # JSON Schema files for data validation (shared)
```

## Agent System
Six agents collaborate via orchestrator pattern:
1. **orchestrator** - Coordinates workflow, manages consensus rounds
2. **resume-expert** - Resume writing specialist, formatting, ATS optimization
3. **employer-emulator** - Thinks like a hiring manager, evaluates fit
4. **recruiter** - Independent recruiter perspective, market positioning
5. **bias-auditor** - Audits for age, gender, ethnicity, disability, and other bias exposure
6. **fact-checker** - Verifies every claim against profile.json; has veto power on accuracy

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

### Other commands
- `/review-job` — Analyze a job posting and evaluate fit against a profile
- `/track-application` — Full application lifecycle: status, contacts, interviews, comp, follow-ups, outcome

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
| `tools/generate_resume.py` | Generate .docx resume from JSON content | `python3 tools/generate_resume.py content.json output.docx` |
| `tools/profile_create.py` | Create profile directory structure | `python3 tools/profile_create.py "Full Name" [--slug slug]` |
| `tools/profile_switch.py` | List profiles or switch active | `python3 tools/profile_switch.py [slug]` |
| `tools/profile_delete.py` | Delete a profile (dry-run or confirmed) | `python3 tools/profile_delete.py slug [--confirm]` |

## Dependencies
Python packages are listed in `requirements.txt`. Install via:
```bash
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
```
(Alternatively, "python" if the "python3" command is not available.)