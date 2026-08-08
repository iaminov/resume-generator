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

## Agent System
Seven agents, defined in `.claude/agents/`. Six drive resume generation via the
orchestrator pattern; `cover-letter-writer` drafts the cover letter.

`fact-checker` and `employer-emulator` then review it once in parallel, with at
most one revision round. Only the fact-checker can block; the emulator advises.
Two reviewers cover the failure modes that matter for a letter — fabrication,
and failing to persuade — and no more are added on purpose: consensus sands
prose toward the safe middle, and sounding like a specific person is the only
advantage a cover letter has over the resume.

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

Each command's full workflow lives in `.claude/skills/<name>/SKILL.md` and loads
when the command runs: `/profile-create`, `/profile-switch`, `/profile-delete`,
`/parse-resumes`, `/scan-codebase`, `/create-resume`, `/create-cover-letter`,
`/review-job`, `/track-application`.

Two constraints the skills depend on but cannot enforce:

- **`/parse-resumes` runs first.** `profile.json` is the single source of truth
  and must exist before any other command can run. `/scan-codebase` augments an
  existing profile; it never creates one.
- **Documents are generated only by the pre-built scripts** —
  `tools/generate_resume.py` and `tools/generate_cover_letter.py`. Never write
  python-docx code inline or create new scripts for DOCX generation.

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

## Altitude (CRITICAL)

Accuracy is necessary but not sufficient — a true claim pitched at the wrong
level of abstraction still wastes the line. **The test is whether a screener
with no context could tell at a glance that a claim is impressive.**

The failure this repo produces is writing *too low*, because profile material is
built by reading source material closely and inherits the altitude of whatever
it was read from. `/scan-codebase` is the biggest source of it: reading code
surfaces details that prove authorship — an unusual algorithm, a precise line
count, a clever workaround — and they are compelling precisely because they
could not be invented. That makes them excellent **provenance** and poor
**content**.

- Keep them in `profile.json` under `evidence` or `outcomes`, where they justify
  a claim.
- Put the capability on the page: "timezone-correct scheduling", not "compares
  the UTC offset at session time against the current one".
- Numbers need a baseline the reader can judge against. "3,000+ devices" works;
  "775 of 2,578 lines are tests" hands the reader a question instead of a fact.

See the Altitude section of `.claude/rules/resume-writing.md` for the full rule.
`/create-resume` runs an explicit altitude pass before generating, and
`resume-expert` votes REVISE on violations during consensus.

## Data Integrity
- Every profile JSON must validate against `schemas/profile.schema.json`
- Every application JSON must validate against `schemas/application.schema.json`
- Every job description JSON must validate against `schemas/job-description.schema.json`
- Generated resumes must be saved alongside metadata linking to source profile and target job

## Tools (pre-built scripts)

All deterministic operations use pre-built, tested scripts in `tools/`. Skills
must call these scripts — never generate new scripts or write inline code for
these operations.

`ls tools/` lists them; every script takes `--help` for its own arguments. Both
generators also accept `--dry-run`, which reports the sections, chosen density,
and estimated page count without writing a file — use it to check a page target
before committing to one.

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

## Dependencies
Runtime packages are pinned in `requirements.txt` and mirrored in
`pyproject.toml`; test and lint tooling lives in `requirements-dev.txt` and the
`dev` extra. Versions use compatible-release ranges (`~=`) rather than `>=`,
because python-docx decides the default styles every generated document
inherits and an unbounded range can change output without anything here
changing.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # runtime only
pip install -e ".[dev]"                  # plus pytest and ruff, and puts the
                                         #   console entry points on PATH
```
(Alternatively, "python" if the "python3" command is not available.)

Installing is optional. `python3 tools/<script>.py` works without it, and that
is the form every skill and rule uses.

## Lint
```bash
ruff check tools/ tests/
```
Configured in `ruff.toml` to catch defects — undefined names, unused imports,
mutable defaults, unchained raises — without imposing a formatter. CI runs it
alongside the tests, so a dead import left by a refactor fails the build.

## Git remotes

This repo is typically used as a fork, so pushes and pulls can target different
remotes. **`git branch -vv` and `git status` show only the fetch remote**, which
in that setup names the repo you are *not* pushing to. Never infer the push
target from them:

```bash
git rev-parse --abbrev-ref '@{push}'      # where a bare `git push` actually goes
git push --dry-run                        # confirms it without sending anything
```