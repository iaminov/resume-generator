---
name: profile-delete
description: Delete a person's profile directory and all associated data after user confirmation
---

# Profile Delete Skill

## Steps

1. If no slug provided, list profiles first:
   ```
   python3 tools/profile_switch.py
   ```
   Ask the user which profile to delete.

2. Run a dry run to show what will be deleted:
   ```
   python3 tools/profile_delete.py {slug}
   ```
   Parse the JSON output and show the user a clear inventory:
   - Whether it's the active profile
   - Number of source resumes, applications, job descriptions, generated resumes

3. **Ask the user to confirm deletion.** This is destructive and irreversible.
   Do NOT proceed without explicit confirmation.

4. Only after user confirms, run the actual delete:
   ```
   python3 tools/profile_delete.py {slug} --confirm
   ```

5. Report the result. If `active_cleared` is true, tell the user to run
   `/profile-switch` to select a different profile.

## Critical Rules

- **ALWAYS show the dry run first and get user confirmation before passing --confirm**
- NEVER run `--confirm` without the user explicitly agreeing to delete
- Do NOT delete files or directories manually — the script handles everything
