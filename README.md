# Resume AI - Multi-Agent Resume Optimization System

A Claude Code-powered system that parses resumes, builds a structured profile,
and generates tailored resumes and cover letters.

Resumes go through a consensus review by five specialized agents (coordinated by
a sixth, the orchestrator). Cover letters use a lighter three-agent path, and can
be written in your own voice from writing samples you supply.

## Quick Start

All interaction happens through Claude Code slash commands. No separate installation or build step required.

### Prerequisites

- [Claude Code](https://claude.ai/code) CLI installed
- Python 3.10+
- **Optional:** [LibreOffice](https://www.libreoffice.org/), used to confirm the
  real page count of a generated document. Without it the tools fall back to a
  built-in estimator, which runs about 10% optimistic — everything still works,
  page fitting is just less exact.

### Setup

```bash
# Clone the repository
git clone <repo-url> && cd resume_ai

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Optional: to run the test suite
pip install -r requirements-dev.txt && pytest
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

   **Put only actual resumes here.** Everything in this folder is parsed as
   *fact* — a record of what you did. Notes, ideas, open questions, and feedback
   from a coach or the internet go in `input/input-notes/` instead, where they
   are treated as guidance and can never become a claim on your resume. Mixing
   the two has caused real damage: a saved forum thread was once parsed as
   personal notes, and a stranger's job-search statistic ended up recorded as
   the profile owner's own.

3. **Build the profile** — run `/parse-resumes`. Claude reads and comprehends
   every file in `input/input-resumes/` and synthesizes a single `profile.json`
   (the source of truth for all later steps).

4. **Generate tailored resumes** — run `/create-resume` for each job posting.

5. **Optionally restyle the output** — the generators produce properly formatted
   documents with no setup. If you want your own fonts or colours, copy
   `templates/default.docx`, edit it in Word, and pass it with `--template`.
   See [Templates](#templates--using-your-own).

6. **Optionally add a cover letter** — run `/create-cover-letter`. If you want it
   to sound like you rather than like a template, drop a writing sample into
   `data/profiles/{slug}/input/input-voice-samples/` first. A past cover letter
   works, but anything substantial you actually wrote is better — a detailed
   email, a technical explanation, a personal statement. Prose written *without a
   template in front of you* carries far more of your voice. Skip it entirely and
   you get a clear, neutral default voice.

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

### `/scan-codebase` - Add What Your Code Proves

Augments an existing profile from your own source repositories. A resume records what you remembered to write down; your code is the primary record of what you actually built.

**Usage:** Run `/scan-codebase` and point it at your projects folder. Scanning everything at once is the normal case — Claude runs the inventory itself, but the underlying command is:

```bash
# every project in a folder — point --all at the PARENT directory
python3 tools/scan_codebase.py ~/PycharmProjects --all \
    --author "Jane Doe" --author jdoe --out scan.json

# one project on its own — no --all, pass the project directory
python3 tools/scan_codebase.py ~/PycharmProjects/widget-service --author jdoe
```

`--all` treats every subdirectory as a separate project, **whether or not it has git initialized** — a project without a `.git` is still a project, it just has no authorship record. It descends exactly one level, so a folder that itself contains projects needs its own `--all`. Vendored and build directories (`node_modules`, `.venv`, `dist`, …) are always skipped.

`--author` is repeatable, and you should pass every identity you commit under — a full name on one machine, a GitHub handle on another, a nickname on a third. The scan reports every committer it finds so you can confirm which are yours.

**How it works:**
1. **Mechanical inventory**: `tools/scan_codebase.py` counts lines by language, finds test files, parses declared dependencies, and asks git who wrote how much — counts only, no judgments
2. **Identity confirmation**: you are shown every committer identity found across every project and asked which are yours, before anything is attributed
3. **AI comprehension**: Claude reads the actual source and works out what each project is and what it demonstrates

**What it produces:**
- New `projects` and `skills` entries in `profile.json`, each with evidence naming the repo and what in it supports the claim
- Proficiency upgrades where code evidence outranks a bare mention in an old resume
- A record of which repos were scanned and which remain, so an interrupted scan can resume

**Rules:**
- **Authorship is verified from git first, and identities are confirmed with you.** A directory on your disk is not evidence you wrote it, and a handle is not evidence it's yours. Minority-authored repos describe your contribution, not the project; unestablished authorship is brought back to you rather than assumed.
- **A missing `.git` never disqualifies a project.** It removes the ability to check authorship and nothing else. Those projects are listed separately and you're asked about them.
- **Teaching material, demos, and scratch work are skipped** even when they're large and entirely yours — a folder of live-coding examples is many disconnected snippets, not a system.
- **Existing claims are never deleted for lack of code.** Absence of evidence is not evidence of absence — you may have used a technology at a job whose code isn't on your laptop. Such conflicts get flagged, not resolved.
- **Findings are written at resume altitude.** Implementation detail stays in the evidence field where it belongs. See [Altitude](#altitude) below.
- Client names, credentials, and customer data found in source never enter the profile.

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

### `/create-cover-letter` - Generate a Tailored Cover Letter

Writes a one-page cover letter for a specific posting, optionally in your own voice.

**Usage:** Run `/create-cover-letter`, then provide a job posting (or reuse one
already parsed by `/create-resume`).

**What it does:**
1. Resolves the voice — if `input/input-voice-samples/` has files it matches your
   writing; if it is empty it **asks** whether you would like to add samples or
   take the default voice. It never decides for you silently.
2. Drafts the letter with the `cover-letter-writer` agent, which returns every
   factual claim alongside the `profile.json` path it came from
3. Reviews once with two agents in parallel:
   - **Fact Checker** — verifies every claim; **can block**
   - **Employer Emulator** — reads as the hiring manager for that role and
     reports what fails to land; advisory only
4. Allows at most one revision round, then generates the `.docx` into
   `output/output-cover-letters/`
5. Links the letter to the application record if one exists

**Why only three agents:** a cover letter is short, and every claim traces to a
profile that has already been audited, so full consensus is overhead. Two
reviewers cover the failure modes that matter — fabrication, and failing to
persuade. More would be worse, not better: consensus sands prose toward a safe
middle, and sounding like a specific person is the only real advantage a cover
letter has over the resume.

**On voice samples:** they supply *voice only, never facts*. Every claim is still
checked against `profile.json`, so a stale or embellished line in an old letter
cannot ride into a new one. Samples must be your own writing.

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
        input-voice-samples/             # OPTIONAL: your own writing, used to match
                                          #   voice in cover letters. Empty is fine
        input-notes/                     # Notes, ideas, open questions, feedback from
                                          #   coaches. Guidance only, never parsed as fact
      applications/                      # JSON: application tracking records
      output/
        output-job-descriptions/         # JSON: parsed/structured job postings
        output-generated-resumes/        # Output: tailored DOCX resumes
        output-cover-letters/            # Output: tailored DOCX cover letters
tools/                         # Shared scripts (see below)
tests/                         # pytest suite; fixtures are fictional by policy
templates/                     # DOCX style templates. default.docx ships with the
                               #   repo; drop your own here and pass --template
schemas/                       # JSON Schema files for data validation (shared)
.claude/
  agents/                      # Agent definitions (orchestrator, resume-expert,
                               #   employer-emulator, recruiter, bias-auditor,
                               #   fact-checker, cover-letter-writer)
  rules/                       # Standards that attach automatically by file path
                               #   (data-integrity, resume-writing,
                               #   resume-formatting, application-tracking,
                               #   user-interaction)
  skills/                      # Skill definitions (profile-create, profile-switch,
                               #   profile-delete, parse-resumes, create-resume,
                               #   create-cover-letter, review-job,
                               #   track-application)
```

## Tools

Deterministic work runs through pre-built scripts rather than generated code.

| Script | Purpose |
|---|---|
| `docx_to_md.py` | Convert a DOCX to markdown; reports any text it could not extract |
| `extract_resumes.py` | Batch-extract every resume for a profile |
| `scan_codebase.py` | Inventory a codebase: lines by language, tests, dependencies, git authorship. Counts only — never judgments |
| `generate_resume.py` | Build a .docx resume from JSON; spacing adapts to a page goal |
| `generate_cover_letter.py` | Build a .docx cover letter from JSON |
| `layout.py` | Shared text metrics, template loading, page verification (module, not a CLI) |
| `validate.py` | Validate profile/application/job-description JSON against the schemas |
| `application_update.py` | Change an application's status or log activity, with transition validation |
| `application_status.py` | Report search state; `--analytics` for outcome rates |
| `diff_content.py` | Compare two generated documents by their content sidecars |
| `common.py` | Shared paths and active-profile helpers (module, not a CLI) |
| `profile_create.py` / `profile_switch.py` / `profile_delete.py` | Profile management |

### Page fitting

`generate_resume.py` chooses spacing to suit the document instead of applying one
fixed look. Three presets — `normal`, `compact`, `dense` — vary margins and
section spacing only. Font sizes never change, because shrinking type to force a
fit is exactly what makes a resume look crammed.

```bash
python3 tools/generate_resume.py content.json out.docx --target-pages 1
python3 tools/generate_resume.py content.json out.docx --density compact
```

State a page goal rather than naming a preset where you can; the tool then picks
the loosest spacing that meets it. With no goal it starts roomy and tightens only
to reclaim a trailing page holding a few stray lines. Where LibreOffice is
installed it confirms the real page count by rendering rather than trusting the
estimate.

### Templates — using your own

You do not need a template. Both generators produce a complete, properly styled
document on their own, and `--template` defaults to none.

**If you want your own look**, put a `.docx` in `templates/` and pass it:

```bash
python3 tools/generate_resume.py content.json out.docx --template templates/mine.docx
python3 tools/generate_cover_letter.py letter.json out.docx --template templates/mine.docx
```

The folder is not enforced — any path works — but `templates/` is where these
belong, and `.gitignore` has an exception so `.docx` files there are versioned
rather than treated as generated output.

The easiest way to make one is to copy `templates/default.docx`, open it in
Word, and change fonts, colours, or bullet glyphs. Two rules:

- **A template supplies styles, not content.** python-docx opens a `.docx`
  whole, so any body text in it would be prepended to every document you
  generate. Anything found is stripped and reported rather than silently
  included — but start from an empty document and you avoid the question.
- **It must define `Normal` and `List Bullet`.** A `.docx` saved out of Word
  that never used a bulleted list will not define `List Bullet`, and the
  generators reference it by name. You will get a clear error naming the
  missing style rather than a crash.

A path that does not exist is an error, not a silent fallback — a typo would
otherwise produce an unstyled document with no warning. Page spacing always
comes from the density presets, which override the template's margins.

### Application updates

Status changes go through `application_update.py` rather than hand-editing JSON:

```bash
python3 tools/application_update.py <record> --show
python3 tools/application_update.py <record> --status phone_interview --notes "45 min with the hiring manager"
python3 tools/application_update.py <record> --log "Recruiter emailed to schedule"
```

It validates the move against a transition graph (so a record cannot skip from
`draft` to `accepted`, or leave a terminal state, without `--force`), appends to
`status_history` instead of rewriting it, timestamps every entry, journals the
change, validates against the schema before and after, and writes atomically.
`ghosted` is deliberately recoverable — employers do resurface.

### DOCX extraction

`docx_to_md.py` extracts greedily — body text in document order, tables
including nested ones and those inside headers and footers, text boxes, and
headers and footers themselves. It then compares every text node in the file
against what came out and **reports anything that did not make it**:

```bash
python3 tools/docx_to_md.py resume.docx --json     # includes the skip report
```

No extractor anticipates every construct Word emits, and this output is what
your profile is built from. A resume quietly losing an employer is worse than a
warning, so a non-empty skip list is worth acting on.

### Comparing versions

```bash
python3 tools/diff_content.py old.content.json new.content.json
```

Reports what actually changed between two generated documents — summary, skills
by category, bullets added, removed, or reworded — rather than the wall of
reflowed lines `git diff` produces on JSON. Small edits are paired as rewordings
instead of counting as one removal plus one addition.

### Dry runs

```bash
python3 tools/generate_resume.py content.json out.docx --target-pages 1 --dry-run
```

Reports the sections, the density it would choose, and the estimated page count
without writing a file.

### Which profile, and schema versions

Tools resolve the profile in this order: `--slug`, then the `RESUME_AI_PROFILE`
environment variable, then `data/.active-profile`, then a sole existing profile.
The environment variable lets one shell pin a profile without touching the
shared file:

```bash
RESUME_AI_PROFILE=jane-doe python3 tools/application_status.py
```

All stored JSON carries a `schema_version`. Validation warns on a missing or
major-mismatched version rather than failing, so an old document can still be
read and fixed.

### Validation

```bash
python3 tools/validate.py data/profiles/jane-doe/profile.json
python3 tools/validate.py --all              # every profile, every covered file
python3 tools/validate.py --all --strict     # plus the rules schemas cannot express
```

Infers the schema from the file's location, reports the exact JSON path at fault,
and exits non-zero so it can gate a workflow.

`--strict` adds the requirements `data-integrity.md` states but JSON Schema
cannot check: every entry carries a bare `source_file`, dates are ISO 8601, no
skill claims a proficiency without evidence, `is_current` roles have no end date,
and an application's `status` matches the last entry in its `status_history`.

### Search status

```bash
python3 tools/application_status.py                  # active profile
python3 tools/application_status.py --stale-days 21
```

Reports what is still live, which applications have had no movement past the
threshold, which follow-ups are overdue, and which generated documents were built
from an older `profile.json` than the current one. Terminal statuses are never
reported as quiet.

## File Naming Conventions

| Type | Pattern | Example |
|---|---|---|
| Profile | `profile.json` (in `data/profiles/{slug}/`) | `data/profiles/jane-doe/profile.json` |
| Application | `{YYYY-MM-DD}_{company}_{role}.json` | `applications/2026-04-12_google_senior-swe.json` |
| Job description | `{company}_{role}_{YYYY-MM-DD}.json` | `output/output-job-descriptions/google_senior-swe_2026-04-12.json` |
| Generated resume | `{First}_{Last}_{company-slug}_{role-slug}_{YYYY-MM-DD}.docx` | `output/output-generated-resumes/Jane_Doe_acme_senior-platform-engineer_2026-05-26.docx` |
| Generated cover letter | same stem plus `_cover-letter.docx` | `output/output-cover-letters/Jane_Doe_acme_senior-platform-engineer_2026-05-26_cover-letter.docx` |
| Content sidecar | `{same-stem}.content.json` | `Jane_Doe_acme_senior-platform-engineer_2026-05-26.content.json` |

Every generated `.docx` is saved next to the JSON it was built from. A `.docx`
cannot be read back into structured content, so without the sidecar even a
one-line change means regenerating the document from scratch.

## Data Integrity

- All JSON files are validated against schemas in `schemas/` before writing,
  using `python3 tools/validate.py`
- Every skill and experience entry traces back to an input resume via `source_file` (filename only)
- Application status history is append-only
- Job descriptions are snapshot at parse time (URLs expire)
- Content is **never fabricated** - all generated content must be traceable to parsed source data
- Input files are **not automatically the person's own words**. Notes folders
  often hold third-party advice and pasted articles whose first-person claims
  belong to strangers; authorship is verified before anything is recorded as the
  person's own statement

## Altitude

Accuracy is necessary but not sufficient. A claim can be perfectly true and
still waste the line it sits on by being pitched at the wrong level of
abstraction.

**The test: could a screener with no context tell at a glance that this is
impressive?** They have seconds and nothing but the page.

The failure mode here is writing *too low*, and it is structural rather than
careless — profile material is built by reading source material closely, so it
inherits the altitude of whatever it was read from. `/scan-codebase` is the
strongest source of it. Reading code surfaces details that prove authorship: an
unusual algorithm, a precise line count, a clever workaround. They are
compelling exactly because nobody could invent them, which makes them excellent
**provenance** and poor **content**.

| Too low | At altitude |
|---|---|
| "stores a sha256 hash of a `secrets.token_urlsafe(32)` token" | "single-use signup invitations with expiry and revocation" |
| "compares the UTC offset at session time against the current one" | "timezone-correct scheduling" |
| "Lambda behind API Gateway, DynamoDB for state, cross-account IAM" | "deploys AI agents into isolated accounts with per-tenant provisioning" |
| "775 of 2,578 lines are tests" | (cut — the reader has no baseline to judge it against) |

Numbers earn their place when the reader has a baseline. "3,000+ devices",
"100+ students", and "a team of 8" are instantly legible; a line-count ratio is
not, and hands the reader a question instead of a fact.

Detail that fails the test is not discarded — it stays in `profile.json` under
`evidence` or `outcomes`, where it justifies the claim above it and is ready for
the interview question it actually answers. The rule is enforced in three
places: `/scan-codebase` applies it when writing entries, `/create-resume` runs
an explicit altitude pass before generating, and the `resume-expert` agent votes
REVISE on violations during consensus. The full rule lives in
`.claude/rules/resume-writing.md`.

## Installation as a package

The tools run directly with `python3 tools/<script>.py` and need no install —
that is the form every skill uses. They can also be installed, which puts them
on PATH:

```bash
pip install -e ".[dev]"
resume-validate --all --strict
resume-application-status --analytics
```

## Tests and lint

```bash
pip install -e ".[dev]"    # or: pip install -r requirements-dev.txt
pytest
ruff check tools/ tests/
```

`ruff.toml` is deliberately conservative: it catches defects — undefined names,
unused imports, mutable defaults, unchained raises — without imposing a
formatter. Dependencies are pinned with compatible-release ranges in
`requirements.txt` and `pyproject.toml`, since python-docx decides the default
styles every generated document inherits.

Covers the pure functions worth pinning: text metrics, page estimation and
density selection, slug generation, active-profile semantics, and schema
validation. CI runs them on Python 3.10 and 3.13, and additionally exercises the
generators on a runner with no LibreOffice installed, so the fallback path stays
honest.

All test fixtures are fictional. Per the confidentiality rule, no real personal
data appears anywhere outside `data/profiles/`, which is gitignored.
