---
name: review-job
description: Analyze a job posting and evaluate fit against a person's profile without creating a resume
---

# Review Job Skill

Analyze a job posting and assess how well a person's profile matches, without
generating a resume. Useful for deciding whether to apply.

## Steps

0. **Resolve active profile**:
   Run `python3 tools/profile_switch.py` to get the active profile slug.
   If none set, tell user to run `/profile-switch` or `/profile-create`.
   All paths below are relative to `data/profiles/{slug}/`.

1. **Get the job posting** — check these sources in order:
   1. Files directly inside `data/profiles/{slug}/input/input-job-postings/`
      (PDF, DOCX, or TXT) — do NOT look inside its `processed/` subfolder;
      those postings have already had a resume generated for them via
      `/create-resume`. For DOCX, convert with
      `python3 tools/docx_to_md.py <file>`. For PDF or TXT, read directly
      with the Read tool. If multiple files exist, ask the user which one
      (or process the most recent).
   2. URL provided by the user
   3. Text pasted by the user

   `/review-job` never moves the source file — only `/create-resume` archives
   a posting into `processed/`, since only it produces a resume/application.

2. **Get the person's profile**: Load from `data/profiles/{slug}/profile.json`
   - The profile must already exist (built via `/parse-resumes`). If `profile.json`
     is missing, tell the user to run `/parse-resumes` first. Do NOT read source
     resumes directly.

3. **Parse job requirements** into:
   - Must-have skills/qualifications
   - Nice-to-have skills/qualifications
   - Years of experience required
   - Education requirements
   - Industry/domain requirements
   - Location/remote requirements

4. **Match against profile**:
   - For each must-have: MATCH / PARTIAL / GAP
   - For each nice-to-have: MATCH / PARTIAL / GAP
   - Experience level comparison
   - Education match

5. **Generate fit report**:
   ```
   Overall Match: X% (must-haves met / total must-haves)

   STRONG MATCHES:
   - [skill/requirement]: [evidence from profile]

   PARTIAL MATCHES:
   - [skill/requirement]: [what candidate has vs what's needed]

   GAPS:
   - [skill/requirement]: [not found in profile]

   RECOMMENDATION: [Apply / Apply with caveats / Do not apply]
   REASONING: [why]
   ```

6. **Save analysis** to `data/profiles/{slug}/output/output-job-descriptions/` for reference

## Critical Rules
- Be honest about gaps. Do not overstate partial matches.
- The recommendation must weigh must-haves heavily over nice-to-haves
- A candidate missing 2+ must-haves should generally get "Do not apply"
  unless the role is clearly flexible on requirements
