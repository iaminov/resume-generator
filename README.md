# Resume AI - Multi-Agent Resume Optimization System

A Claude Code-powered system that parses resumes, builds skills databases, and generates tailored resumes using five specialized AI agents that collaborate through a consensus-based review process (with a 6th orchestrator agent).

## Quick Start

All interaction happens through Claude Code slash commands. No separate installation or build step required.

### Prerequisites

- [Claude Code](https://claude.ai/code) CLI installed
- Python 3.10+

### Setup

```bash
# Clone the repository
git clone <repo-url> && cd resume_ai

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

(Alternatively, use `python` instead of `python3` if the `python3` command is not available.)

### First-Time Workflow

Once the project is open in Claude Code, follow these steps in order:

1. **Create a profile** — run `/profile-create` and provide the person's full
   name. This creates `data/profiles/{slug}/` and sets it active.

2. **Add your existing resumes** — copy every resume you already have (any
   number, any version) into the new profile's `input/input-resumes/` directory:

   ```
   data/profiles/{slug}/input/input-resumes/
   ```

   Both **PDF** and **Word (.docx)** files are supported. There is no required
   filename — drop them in as-is. This is the raw material the system learns
   from, so include everything: old resumes, role-specific variants, even cover
   letters. The richer this collection, the better the resulting profile.

3. **Build the profile** — run `/parse-resumes`. Claude reads and comprehends
   every file in `input/input-resumes/` and synthesizes a single `profile.json`
   (the source of truth for all later steps).

4. **Generate tailored resumes** — run `/create-resume` for each job posting.

## Commands

### `/profile-create` - Create a New Profile

Sets up a new person's profile directory with the full folder structure and makes it the active profile.

**Usage:** Run `/profile-create` and provide the person's full name.

**What it does:**
- Creates `data/profiles/{slug}/` with subdirectories: `input/input-resumes/`, `input/input-job-postings/`, `applications/`, `output/output-job-descriptions/`, `output/output-generated-resumes/`
- Sets the new profile as active in `data/.active-profile`
- Tells you where to place resume files

---

### `/profile-switch` - Switch Active Profile

Switches which person's data all other commands operate on.

**Usage:** Run `/profile-switch` to see available profiles and pick one, or `/profile-switch {slug}` to switch directly.

---

### `/profile-delete` - Delete a Profile

Permanently deletes a person's profile directory and all associated data.

**Usage:** Run `/profile-delete` and confirm. Requires explicit confirmation to proceed.

---

### `/parse-resumes` - Build Comprehensive Profile

Uses a two-phase AI pipeline to build a comprehensive `profile.json` from all resumes in the active profile's `input/input-resumes/` directory.

**Usage:** Run `/parse-resumes` in Claude Code. It automatically processes every PDF/DOCX in the active profile's `input/input-resumes/` directory.

**How it works:**
1. **Mechanical extraction**: PDFs are read natively by Claude; DOCX files are converted to markdown via `tools/docx_to_md.py`
2. **AI comprehension**: Claude reads all extracted text in full, understands context, infers skills from experience descriptions, deduplicates by meaning (not string matching), and synthesizes a unified profile

**What it produces:**
- A single `profile.json` containing: contact info, professional summaries, skills (with evidence and proficiency), experience (with deduplicated bullets), education, certifications, projects, awards
- Every entry traces back to its source file
- Validated against `schemas/profile.schema.json`

**Rules:** Claude IS the parser — no custom scripts for content analysis. Never invents or assumes data not present in the source. Ambiguous fields are flagged for user review.

---

### `/create-resume` - Generate a Tailored Resume

Creates an optimized, job-specific resume through the full 5-agent consensus workflow.

**Usage:** Run `/create-resume`, then provide a job posting (URL or pasted text).

**What it does:**
1. Parses the job description
2. **Checks for a duplicate** — searches `applications/` for an existing record with the same company + role. If one exists, it shows you the existing status, resume file, and creation date (and flags if your profile has been updated since), then asks whether to proceed. It never regenerates a resume silently.
3. Saves the job description to the active profile's `output/output-job-descriptions/`
4. Runs a gap analysis (strong matches, partial matches, gaps) and presents it before proceeding
5. Launches the orchestrator agent to manage the consensus process:
   - Resume Expert creates the initial draft
   - All 5 agents review in parallel (max 5 rounds)
   - Each round reports vote status to the user
6. Generates the final `.docx` resume in the active profile's `output/output-generated-resumes/`
7. Creates an application tracking record in the active profile's `applications/`
8. **Archives the source posting** — if the job came from a file in `input/input-job-postings/`, that file is moved into `input/input-job-postings/processed/` so it no longer shows up as a pickable input. **To force the same posting to be reprocessed** (e.g., you updated your profile and want a fresh resume for it), just move the file back out of `processed/` into `input-job-postings/` — no command needed.
9. Presents the result with consensus summary for user approval

**Rules:** The consensus process is never skipped. Gap analysis is shown before generation so the user can decide not to apply. Duplicate applications require explicit user confirmation before a second resume is generated.

---

### `/review-job` - Analyze Job Fit

Evaluates how well the active profile matches a job posting without generating a resume. Useful for deciding whether to apply.

**Usage:** Run `/review-job`, then provide a job posting.

**What it does:**
- Parses job requirements into must-haves and nice-to-haves
- Matches each requirement against the profile: MATCH / PARTIAL / GAP
- Generates a fit report with overall match percentage
- Provides a recommendation: Apply / Apply with caveats / Do not apply
- Saves the analysis to the active profile's `output/output-job-descriptions/` for reference

**Rules:** Honest about gaps. Missing 2+ must-haves generally yields a "Do not apply" recommendation.

---

### `/track-application` - Manage Applications

Full application lifecycle tracking — status, contacts, interviews, compensation, follow-ups, and outcome.

**Usage:** Run `/track-application` with one of these sub-commands:

| Sub-command | Example | Description |
|---|---|---|
| **Update status** | `update Google Senior SWE to screening` | Change application status with timestamp |
| **Add contact** | `add contact Sarah Lee for Google` | Track recruiter, hiring manager, interviewers |
| **Log interview** | `had technical interview at Google` | Record interview details, topics, sentiment |
| **Add note** | `note for Google: team is 12 people, mostly backend` | Free-form journal entry |
| **Update comp** | `offer from Google: 220k base + 200k equity` | Track posted range, discussed, or offer |
| **Add follow-up** | `follow up with Google by April 20` | Schedule a reminder with due date |
| **Complete follow-up** | `done: thank-you email for Google` | Mark a follow-up as completed |
| **Close application** | `rejected from Google` or `close Google as withdrawn` | Record outcome with reason and lessons learned |
| **View application** | `show Google Senior SWE` | Full record: contacts, interviews, comp, activity log |
| **List all** | `list applications` | Summary table with overdue follow-ups highlighted |
| **Stats** | `application stats` | Response rate, interview rate, offer rate, and trends |

**Valid statuses:** `draft` > `ready` > `applied` > `screening` > `phone_interview` > `technical_interview` > `onsite_interview` > `offer` > `accepted` / `rejected` / `withdrawn` / `ghosted`

**Rules:** All status changes are user-initiated. Status history and activity log are append-only. Compensation is never shown in summary tables.

## Agent System

Six specialized agents collaborate via an orchestrator pattern during resume creation:

### Orchestrator
Coordinates the end-to-end workflow. Manages intake, job analysis, the consensus review loop, output generation, and application tracking. Runs all 5 review agents in parallel each round and synthesizes their feedback.

### Resume Expert
Senior resume writing specialist (20+ years). Focuses on:
- ATS keyword optimization and formatting
- Achievement-oriented bullets using the CAR formula (Challenge, Action, Result)
- Tailoring content to specific job descriptions
- Quantifying accomplishments with metrics

Votes APPROVE only when keyword match, achievement quality, relevance, ATS compliance, length, and flow all pass.

### Employer Emulator
Thinks like a hiring manager screening 200 resumes to find 10 interviews. Performs:
- **6-second scan**: immediate fit signals, keyword visibility, red flags
- **Detailed evaluation**: must-have coverage, achievement credibility, career progression, culture signals

Votes APPROVE only if the resume would advance to the interview pile with no major gaps or red flags.

### Recruiter
Independent technical recruiter (15+ years, contingency-based). Evaluates:
- Competitive positioning against the talent pool
- Title alignment and seniority match
- Narrative arc and career story clarity
- Market reality check (realistic target, industry alignment)

Votes APPROVE only if they would confidently submit the candidate to their client, staking reputation and commission.

### Bias Auditor
Audits resumes for content that could trigger unconscious bias in hiring. Covers:
- **Ageism**: graduation dates, early career roles, "20+ years" phrasing, outdated tech
- **Gender**: gendered language, stereotypical action verbs, framing imbalances
- **Ethnicity/origin**: foreign credential context, unnecessary visa/citizenship info
- **Disability**: employment gap framing, accommodation signals
- **Socioeconomic**: institution prestige bias, address signals
- **Career patterns**: job hopping perception, overqualification, career change framing

Recommends protective edits: removing graduation dates, consolidating older roles, reframing language. All edits must be truthful — the goal is to protect, not deceive.

Votes APPROVE only if the resume minimizes removable bias exposure while remaining truthful and complete. Cannot recommend changing job titles, metrics, or other facts — only omission and reframing.

### Fact Checker
Verifies every claim in the resume against `profile.json`. Catches:
- **Title changes**: job titles must match the profile exactly
- **Metric inflation**: numbers must trace to source data
- **Scope creep**: "contributed to" cannot become "led" without evidence
- **Skill fabrication**: only skills present in the profile can appear
- **Achievement misattribution**: bullets must map to the correct role

Has **veto power** on accuracy — if the fact checker flags a factual error, it must be corrected regardless of what other agents prefer. Enforces the bright line between protective omission (acceptable) and fabrication (never acceptable).

Votes APPROVE only if every factual claim in the resume is supported by the profile.

### Consensus Protocol

- Each agent votes **APPROVE** or **REVISE** per round
- REVISE votes must include: section affected, current text, proposed change, reasoning
- All 5 must approve to finalize (max 5 rounds)
- If round 5 ends without consensus, the best version is presented with dissenting notes

## Directory Structure

```
data/
  .active-profile              # Active person slug
  profiles/
    {slug}/
      profile.json                       # Comprehensive extracted profile
      input/
        input-resumes/                   # Input: PDF/DOCX resume files
        input-job-postings/              # Input: job posting PDF/DOCX/TXT files
          processed/                     # Postings already turned into a resume by
                                          #   /create-resume; move a file back out
                                          #   of here to force it to be reprocessed
      applications/                      # JSON: application tracking records
      output/
        output-job-descriptions/         # JSON: parsed/structured job postings
        output-generated-resumes/        # Output: tailored DOCX resumes
tools/                         # Shared utility scripts (docx_to_md.py)
templates/                     # DOCX resume templates (shared)
schemas/                       # JSON Schema files for data validation (shared)
.claude/
  agents/                      # Agent definitions (orchestrator, resume-expert,
                               #   employer-emulator, recruiter, bias-auditor,
                               #   fact-checker)
  skills/                      # Skill definitions (profile-create, profile-switch,
                               #   profile-delete, parse-resumes, create-resume,
                               #   review-job, track-application)
```

## File Naming Conventions

| Type | Pattern | Example |
|---|---|---|
| Profile | `profile.json` (in `data/profiles/{slug}/`) | `data/profiles/jane-doe/profile.json` |
| Application | `{YYYY-MM-DD}_{company}_{role}.json` | `applications/2026-04-12_google_senior-swe.json` |
| Job description | `{company}_{role}_{YYYY-MM-DD}.json` | `output/output-job-descriptions/google_senior-swe_2026-04-12.json` |
| Generated resume | `{First}_{Last}_{company-slug}_{role-slug}_{YYYY-MM-DD}.docx` | `output/output-generated-resumes/Jane_Doe_acme_senior-platform-engineer_2026-05-26.docx` |

## Data Integrity

- All JSON files are validated against schemas in `schemas/` before writing
- Every skill and experience entry traces back to an input resume via `source_file` (filename only)
- Application status history is append-only
- Job descriptions are snapshot at parse time (URLs expire)
- Content is **never fabricated** - all generated resume content must be traceable to parsed source data
