---
name: create-cover-letter
description: Generate a tailored cover letter for a specific job posting, optionally matching the person's own writing voice, reviewed once by a fact-checker and a hiring-manager emulator
---

# Create Cover Letter Skill

Generate a tailored cover letter through a three-agent workflow: the Cover Letter
Writer drafts it, then the Fact Checker and Employer Emulator review it once in
parallel, with at most one revision round.

This is deliberately lighter than `/create-resume`. A cover letter is short and
every claim traces to a profile that has already been audited, so a five-agent
consensus is overhead. Two reviewers cover the failure modes that matter:
fabrication, and failing to persuade.

## Steps

0. **Resolve active profile**:
   Run `python3 tools/profile_switch.py` to get the active profile slug.
   If none set, tell the user to run `/profile-switch` or `/profile-create`.
   All paths below are relative to `data/profiles/{slug}/`.

1. **Gather inputs**:
   - **Job posting** — check these sources in order:
     1. Files directly inside `input/input-job-postings/` (PDF, DOCX, TXT) —
        do NOT look inside `processed/`. If several exist, ask which one.
     2. An existing parsed job description in `output/output-job-descriptions/`
        (useful when a resume was already generated for this job)
     3. A URL or text supplied by the user
   - For DOCX use `python3 tools/docx_to_md.py <file>`; read PDF and TXT directly.
   - **Profile**: load `data/profiles/{slug}/profile.json`. It is the single
     source of truth for every fact. If it does not exist, tell the user to run
     `/parse-resumes` first. Do NOT read source resumes directly.

2. **Resolve the voice** (ASK THE USER — this is a required pause):

   Check `data/profiles/{slug}/input/input-voice-samples/` for files.

   - **If the folder has samples**: extract them (DOCX via
     `tools/docx_to_md.py`, PDF and TXT read directly) and use voice-matched
     mode. Tell the user which samples you are matching.
   - **If the folder is empty or missing**: tell the user both options and let
     them choose. Say it plainly, something like:

     > No writing samples found. Two options:
     > **(a)** Drop one or more samples into
     > `data/profiles/{slug}/input/input-voice-samples/` and I'll match your
     > voice — a past cover letter works best, but any substantial writing you
     > produced will do (emails, a personal statement, a blog post, a detailed
     > message). More is better; one good sample is enough.
     > **(b)** I write in a clear, professional default voice.

     Do not guess. Wait for the answer. If they choose (a), wait for the files,
     then re-check the folder.

   **Sample quality caveats** — apply and mention if relevant:
   - Samples must be the person's OWN writing. Ask if unsure. This repo has
     already been bitten by third-party text recorded as the candidate's own;
     see `.claude/rules/resume-writing.md`.
   - Samples supply *voice only*, never facts. Any claim in a sample must still
     be corroborated by `profile.json`.
   - Very short samples (under ~150 words) give a weak signal. Say so rather
     than over-fitting to a couple of sentences.

3. **Check for an existing letter**:
   - Look in `output/output-cover-letters/` for a letter matching this company
     and role.
   - If one exists, show the user its filename and date, and ask whether to
     regenerate before continuing. Never silently overwrite.

4. **Save the job description** (if not already saved from a previous run):
   - Save to `output/output-job-descriptions/{company}_{role}_{date}.json`
   - Validate: `python3 tools/validate.py data/profiles/{slug}/output/output-job-descriptions/<file>.json`
     It exits non-zero on failure and reports the exact JSON path at fault.
     Fix the data and re-run; never save a file that does not validate.

5. **Draft — launch the `cover-letter-writer` agent**:
   Give it: the profile, the parsed job posting, the voice mode (and sample
   text if any), and any framing rules recorded in the profile's
   `extraction_notes` (client anonymity, titles, claims that may not be made).
   It returns the letter as JSON plus a list of every factual claim with its
   `profile.json` source.

6. **Review — launch two agents IN PARALLEL, once each**:

   The two reviewers cover orthogonal failure modes: one guards truth, the
   other guards impact. That is the whole space for a document this short.
   Do not add `recruiter` or `bias-auditor` — market positioning is irrelevant
   to a letter, and a letter drawn from an already-audited profile gives the
   bias auditor almost nothing to find.

   **`fact-checker`** — give it the letter, the writer's claim list, and
   `profile.json`. It verifies every factual claim and flags anything
   unsupported, exaggerated, or fabricated. **Veto power on accuracy.**

   **`employer-emulator`** — give it the letter and the job posting, and tell
   it to read as the hiring manager for THIS role: would this letter earn a
   call, and what falls flat? Constrain it explicitly in the prompt:
   - It reports **what fails to land and why**. It does NOT rewrite or supply
     replacement prose. The writer keeps authority over wording.
   - **Voice is not a defect.** Adding reviewers to prose tends to sand a
     letter toward the safe middle, and sounding like a specific person is the
     only real asset a cover letter has. Flag substance that does not land, not
     phrasing that differs from a conventional register.
   - It must separate **modest phrasing** (keep — understatement reads as
     confident and credible) from **a buried achievement** (fix — where plain
     wording hides the scale or difficulty of real work). Only the second is a
     finding.
   - No veto. Its findings are advice; `fact-checker` alone can block.

   Then: if neither reports blocking problems, continue to step 7. Otherwise
   hand both sets of findings back to `cover-letter-writer` for ONE revision
   and accept the result. Do not loop — if problems remain after one revision,
   surface them to the user rather than iterating.

7. **Generate the .docx**:
   - Write the final content as JSON matching the input format documented in
     `tools/generate_cover_letter.py`
   - Save to a temp file, then run:
     ```
     python3 tools/generate_cover_letter.py content.json data/profiles/{slug}/output/output-cover-letters/{First}_{Last}_{company-slug}_{role-slug}_{YYYY-MM-DD}_cover-letter.docx
     ```
   - Do NOT write python-docx code inline or create another script
   - **Keep the content JSON.** Save it beside the .docx as
     `{same-stem}.content.json` — a .docx cannot be edited back into structured
     data, and the sidecar is what makes a later revision cheap.
   - The script reports page count and word count and warns if the letter runs
     past one page or over 400 words. **Act on those warnings** — cut, do not
     ignore them.
   - A letter well under 400 words can still spill by one or two lines, usually
     just the signature. Before cutting prose the fact-checker has already
     cleared, remove redundancy in the letterhead — a recipient `title` line
     duplicating the salutation is the usual culprit. Trim body text only if
     that is not enough, and never re-add a claim while shortening.

8. **Link it to the application record**:
   - If an application record exists for this company + role in
     `applications/`, set its `cover_letter_file` to the new letter's path
     (relative to the profile directory) and append an activity log entry.
   - If no record exists, do not create one — cover letters can be written
     before applying. Mention to the user that `/create-resume` or
     `/track-application` will create the record.

9. **Present to the user**:
   - Show the letter text
   - Report the voice mode used and, if matched, which samples
   - Report the fact-checker's verdict and any residual concerns
   - Report the employer-emulator's read: would it earn a call, and what it
     flagged. Say explicitly which of its suggestions were declined and why —
     a note kept for voice reasons is a decision the user should see, not a
     silent omission
   - Show word count and page count
   - Ask for approval or changes

## Critical Rules
- Exactly three agents: `cover-letter-writer` drafts; `fact-checker` and
  `employer-emulator` review once, in parallel; at most one revision round.
  Do not add further reviewers — consensus sands prose toward the safe middle,
  and voice is the only advantage a letter has over the resume
- Never fabricate a fact, a metric, or a stated affinity for the company
- Voice samples supply voice only — `profile.json` remains the source of facts
- Never write a letter longer than one page
- Never overwrite an existing letter for the same company + role without asking
- Always tell the user the voice-sample option exists rather than silently
  defaulting to the generic voice
