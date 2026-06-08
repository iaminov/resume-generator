---
name: create-resume
description: Generate a tailored resume for a specific job posting using the multi-agent consensus process
---

# Create Resume Skill

Generate a tailored, optimized resume through the 5-agent consensus workflow.

## Steps

0. **Resolve active profile**:
   Run `python3 tools/profile_switch.py` to get the active profile slug.
   If none set, tell user to run `/profile-switch` or `/profile-create`.
   All paths below are relative to `data/profiles/{slug}/`.

1. **Gather inputs**:
   - **Job posting** — check these sources in order:
     1. Files in `data/profiles/{slug}/job-postings/` (PDF or DOCX). For DOCX,
        convert with `python3 tools/docx_to_md.py <file>`. For PDF, read
        directly with the Read tool. If multiple files exist, ask the user
        which one (or process the most recent).
     2. URL provided by the user
     3. Text pasted by the user
   - **Profile**: Load from `data/profiles/{slug}/profile.json`
   - **The profile is the single source of truth** — all resume content must come
     from it. If `profile.json` doesn't exist, tell the user to run `/parse-resumes`
     first. Do NOT read source resumes directly; always go through the profile.

2. **Parse job description**:
   - Extract: title, company, required skills, preferred skills, responsibilities,
     qualifications, salary range (if listed), location, remote policy
   - Save to `data/profiles/{slug}/job-descriptions/{company}_{role}_{date}.json`
   - Validate against `schemas/job-description.schema.json`

3. **Gap analysis**:
   - Compare profile skills/experience against job requirements
   - Identify: strong matches, partial matches, gaps
   - Present gap analysis to user before proceeding
   - If critical gaps exist, warn the user and ask whether to proceed

4. **Launch orchestrator agent**:
   - The orchestrator manages the full consensus workflow
   - Resume Expert creates initial draft
   - All 5 agents review in parallel (max 5 rounds):
     Resume Expert, Employer Emulator, Recruiter, Bias Auditor, Fact Checker
   - Each round reports status to user

5. **Generate .docx**:
   - Write the final resume content as a JSON file matching the input format
     documented in `tools/generate_resume.py` (name, contact, summary, skills,
     experience, education, certifications, projects, publications, awards)
   - Save the content JSON to a temp file, then run:
     ```
     python3 tools/generate_resume.py content.json data/profiles/{slug}/generated-resumes/{First}_{Last}_{company-slug}_{role-slug}_{YYYY-MM-DD}.docx
     ```
   - Do NOT write python-docx code inline or create new scripts — always use the
     pre-built `tools/generate_resume.py`
   - The script applies all formatting from `.claude/rules/resume-formatting.md`
     automatically

6. **Create application record**:
   - Save to `data/profiles/{slug}/applications/{date}_{company}_{role}.json`
   - Initial status: `draft` (changes to `ready` after user approval)
   - Include all consensus metadata
   - File references within the record are relative to the person's profile
     directory (e.g., `job-descriptions/...`, `generated-resumes/...`, `profile.json`)

7. **Present to user**:
   - Show final resume content
   - Show consensus summary (which agents approved, any dissenting notes)
   - Ask user to approve or request manual changes
   - Update status to `ready` on approval

## Critical Rules
- Do not skip the consensus process for any reason
- Present gap analysis before generating - the user may decide not to apply
- Save the job description at parse time (URLs expire)
