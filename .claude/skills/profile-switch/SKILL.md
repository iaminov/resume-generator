---
name: profile-switch
description: Switch the active profile to a different person by updating data/.active-profile
---

# Profile Switch Skill

## Steps

1. List available profiles:
   ```
   python3 tools/profile_switch.py
   ```
   Parse the JSON output and show the user a readable list with active status,
   name, resume count, and whether `profile.json` has been built.

2. If the user provided a slug as an argument, or picks one from the list, switch:
   ```
   python3 tools/profile_switch.py {slug}
   ```

3. Parse the JSON output and confirm the switch. If `has_profile` is false,
   remind the user to add resumes and run `/parse-resumes`.

4. If no profiles exist (status: "empty"), tell the user to run `/profile-create`.

## Critical Rules

- Do NOT write to `data/.active-profile` manually — the script handles it
- Do NOT create profiles — only switch between existing ones
