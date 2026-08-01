---
name: profile-create
description: Create a new person profile directory with the full folder structure, and set it as the active profile
---

# Profile Create Skill

## Steps

1. Get the person's full name from the user (or from the skill argument if provided)

2. Run the script:
   ```
   python3 tools/profile_create.py "Full Name"
   ```
   Optionally pass `--slug custom-slug` if the user wants a specific slug.

3. Parse the JSON output and report the result to the user:
   - Show the created directory path
   - Confirm it was set as active
   - Remind them to:
     - Add resume files to `source-resumes/` and run `/parse-resumes`
     - Drop job posting files (PDF/DOCX/TXT) into `job-postings/` for `/create-resume`

4. If the script exits with an error (profile already exists), relay the error
   and suggest `/profile-switch` instead.

## Critical Rules

- Do NOT create directories or write files manually — the script handles everything
- Do NOT modify the script output — just relay it to the user in a readable format
