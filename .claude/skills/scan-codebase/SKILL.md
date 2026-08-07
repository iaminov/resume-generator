---
name: scan-codebase
description: Read a person's codebases and add what they actually built to profile.json, with git-verified authorship and evidence for every claim
---

# Scan Codebase Skill

Build profile entries from source code the person has written. A resume assembled
only from previous resumes inherits every omission in them; the code is the
primary record of what was actually built, and it is the only source that can
**disprove** a claim as well as support one.

The output is new or updated `skills` and `projects` entries in `profile.json`,
each carrying evidence a later reader can check.

## Architecture: Two-Phase Pipeline

**Phase A — Mechanical inventory** (one script call, no AI):
`python3 tools/scan_codebase.py <path>` counts lines by language, finds test
files, parses declared dependencies, and asks git who wrote how much. It makes
no judgments and produces no prose.

**Phase B — AI comprehension** (Claude reads the code):
Read the actual source and work out what the project *is*, what it demonstrates,
and which of it belongs on a resume. Phase A tells you a repo is 2,578 Python
lines with a `manage.py`; only reading it tells you it is a booking platform.

Phase B is the whole point. Do NOT write scripts for it — no pattern matching
for skill names, no keyword counting, no scoring. **You are the parser.**

## Steps

### 0. Resolve the active profile

Run `python3 tools/profile_switch.py` for the active slug. If none is set, tell
the user to run `/profile-switch` or `/profile-create` and stop.

`profile.json` must already exist — this skill augments a profile, it does not
create one. If it is missing, tell the user to run `/parse-resumes` first.

### 1. Establish what to scan

Ask the user for the directory if they did not name one. **Scanning a whole
projects folder at once is the normal case** — people keep all their work in one
place, and doing them one at a time wastes the comparison between them.

Point `--all` at the *parent* directory. It scans every subdirectory as a
separate project:

```
python3 tools/scan_codebase.py ~/PycharmProjects --all \
    --author "Jane Doe" --author jdoe --out scan.json
```

For a single project, drop `--all` and pass the project directory itself:

```
python3 tools/scan_codebase.py ~/PycharmProjects/widget-service --author jdoe
```

Notes on `--all`:

- **It does not require git.** Every subdirectory is scanned whether or not it
  has a `.git`, because a project without one is still a project.
- **It descends exactly one level.** If a subdirectory has a lot of code but its
  own subfolders look like separate projects, it is a folder *of* projects —
  scan it again with its own `--all`.
- Vendored and build directories (`node_modules`, `.venv`, `dist`, …) are
  skipped everywhere.

**Pass every identity the person commits under.** `--author` is repeatable. Seed
it from their name and their `contact.github` handle in `profile.json`, then
correct it after step 2 — you cannot know the full list until the scan tells you
who committed.

Write the output to the scratchpad with `--out` when scanning many projects; the
full report is large and does not belong in the project tree. `--out` creates
its parent directories.

### 2. Confirm identities with the user (ALWAYS — do not skip)

The scan output has an `all_authors` roster: every committer seen anywhere,
with commit counts and the repos each appears in. **Show the user the whole
roster and ask which identities are theirs, before attributing anything.**

```
Detected 6 committer identities across 23 projects. Which of these are you?

  alex             110 commits   avengers_api, tutoring, IB-TWS-trading-bot - new
  Alex Aminov       84 commits   Lah, resume-generator, joannaTrading, ...
  iaminov           77 commits   google-drive-sync, income-tracker, ...
  rasputin          45 commits   avengers_api, master_llm_api_repo
  Vadim Vozmitsel   31 commits   vadim-vozmitsel-world
  AJ Alston          5 commits   Lah
```

Never guess this. People commit under bare first names, hosting handles, and
nicknames that look nothing like their name, and the cost is asymmetric in both
directions:

- **Unclaimed identity** → real work reads as somebody else's and is dropped.
  A repo the person wrote entirely can report zero matched commits.
- **Over-claimed identity** → a colleague's work gets attributed to them, which
  is the failure this whole gate exists to prevent.

Re-run the scan with every confirmed identity (`--author` is repeatable) so the
shares are correct, or recompute them from `all_authors`.

### 2b. Apply the authorship gate per repo

With identities confirmed, `author_share` is meaningful. Read `git.authorship`:

- **`verified`, majority share** — safe to treat as their work.
- **`verified`, minority share** — they contributed; describe the contribution,
  never the project. Someone with 4 of 200 commits did not "build" it.
- **`unmatched`** — nobody they claimed committed here. Stop and ask.
- **`unestablished-no-git`** — **the project is still real.** Plenty of genuine
  work never gets `git init`, and a missing `.git` says nothing about who built
  it or whether it belongs in the profile. Ask the user directly rather than
  skipping it. These appear in the top-level `without_git_history` list.

Record what you established in the entry's evidence. "32 of 37 commits" is the
kind of fact that settles a question two months from now. For projects with no
git history, record that authorship was confirmed verbally and when.

### 3. Read the code

For each repo worth including, read enough to describe it honestly:

- The README, if there is one — but treat it as a claim, not a finding.
  READMEs describe intentions and are frequently aspirational.
- The entry points and largest files from `largest_files`.
- The tests, which show what the author believed was worth guaranteeing.
- Enough of the domain logic to state what the system does for whoever uses it.

Read for **capability**, not inventory. The question is "what can this system
do, and what did it take to build" — not "which libraries appear in it".

### 4. Write entries at resume altitude (CRITICAL)

This is the step this skill exists to get right, and the one it most easily gets
wrong. Reading code puts you at implementation altitude, and descriptions
written from that vantage stay there. They read as trivia to everyone else.

**The test: could a screener with no context tell at a glance that this is
impressive?**

- Good: "timezone-correct scheduling across both parties' zones",
  "cross-account tenant isolation", "survives partial failure across four
  external services".
- Too low: "stores a sha256 hash of a `secrets.token_urlsafe(32)` token",
  "compares the UTC offset at session time against the current one",
  "19 references to Bedrock", "six methods across three resources".

**Beware the unfakeable detail.** Reading code surfaces specifics that prove
authorship — an unusual algorithm, a precise line count, a clever workaround.
They are compelling *because* they could not be invented, and that makes them
excellent provenance and poor content. Put them in the entry's `evidence` or
`outcomes` field, where they justify the claim, and keep the claim itself at the
level a reader can act on.

**Numbers need a baseline.** "3,000+ devices" and "a team of 8" are instantly
legible. "775 of 2,578 lines are tests" is not — the reader cannot tell whether
that is good. Keep such figures as evidence; do not write them as claims.

See the Altitude section of `.claude/rules/resume-writing.md` for the full rule.

### 5. Decide what does not go in

Not every repo earns an entry, and a profile padded with tutorials is worse than
a short one.

- Scratch work, tutorials, and course exercises: skip.
- Templates and scaffolds with a few edits: skip.
- **Teaching and demo material: skip, however large.** A folder of live-coding
  demos written during lessons can run to tens of thousands of lines and be
  100% theirs, and it is still not a project — it is many disconnected examples.
  Size and authorship both look exactly like a real system here, so this one has
  to be caught by reading. Ask if unsure; a directory named for a subject rather
  than a product is the usual tell.
- Small utilities: fold into a sentence on a larger entry rather than listing
  each one.
- Projects genuinely built but conventional in shape: include, and say so in the
  evidence, so later tailoring knows not to lead with them.

Where a project was built with substantial AI assistance, it is still the
person's work and goes in the profile. Note it in the evidence so the strength
of the claim is calibrated — but this is an internal note, and never surfaces on
a resume or in a cover letter.

### 6. Merge into profile.json

Never overwrite the profile wholesale. For each finding:

- **New project** → append to `projects` with `description`, `technologies`,
  `outcomes`, and a `source_file` of the repo path.
- **New skill** → append to `skills` with `name`, `category`, `proficiency`, and
  `evidence` naming the repo and what in it demonstrates the skill.
- **Existing skill, stronger evidence** → update `evidence` and reconsider
  `proficiency`. Code evidence outranks a bare mention in an old resume.
- **Existing skill contradicted** → do not delete it silently. Absent evidence
  is not disproof; a technology may have been used at a job whose code you
  cannot see. Flag it in `extraction_notes.flagged_for_review` instead.

Record the audit state under `extraction_notes` — which repos were scanned, on
what date, and which remain. Scans get interrupted, and a profile that cannot
say what it has already covered forces the work to be redone.

**Never record a codebase audit as complete unless every repo in scope was
actually read.** A partial audit described as finished causes the next session
to skip repos that were never opened.

### 7. Validate and report

```
python3 tools/validate.py data/profiles/{slug}/profile.json --strict
```

Fix the data and re-run until it passes. Then report:

```
Scanned:   N projects under {path}
Identities confirmed: [the ones the user claimed]
Added:     N projects, N skills
Updated:   N existing skills with code evidence
Skipped:   N (with the reason for each)
Flagged:   [anything needing the user's judgment]
No git history: [projects where authorship rests on the user's word]
Remaining: [projects in scope but not yet read]
```

Call out explicitly any project where authorship could not be established, and
any identity in `all_authors` the user did not claim — the second list is who
else's work is sitting in that directory.

## Critical Rules

- **You are the parser.** `scan_codebase.py` counts; you comprehend. Never write
  scripts to infer skills, match keywords, or score repos.
- **Confirm committer identities with the user before attributing anything.**
  Show them the full `all_authors` roster and ask which are theirs. Never infer
  it from the resemblance between a handle and a name.
- **Verify authorship before recording anything.** A directory on someone's disk
  is not evidence they wrote it. See `.claude/rules/resume-writing.md`.
- **No git history is not a reason to skip a project.** It removes the ability to
  check authorship, nothing more. Ask the user and carry on.
- **Write at resume altitude.** Implementation detail belongs in `evidence`,
  never in a claim. This is the defect this skill is most prone to.
- **Never invent a metric.** Every number must come from the scan output or the
  code itself.
- **Never delete an existing profile claim on the basis of absent code.** Flag it
  for review; absence of evidence is not evidence of absence.
- **Confidentiality still applies.** Client names, credentials, and customer data
  encountered in source code never enter `profile.json`. If a repo reveals a
  client relationship the person has not already disclosed, ask before recording
  it. Secrets found in code are worth mentioning to the user as a security note,
  and must never be copied anywhere.
