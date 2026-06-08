---
paths:
  - "data/**"
  - ".claude/skills/**"
---

# User Interaction Rules

## Do Not Ask Unnecessary Questions

When executing any resume management skill (`/parse-resumes`, `/create-resume`,
`/review-job`, `/track-application`, `/profile-create`, `/profile-switch`):

- **NEVER ask before reading files** — just read them
- **NEVER ask before writing/generating data** — profiles, job descriptions,
  application records, generated resumes. Just create them.
- **NEVER ask before creating directories** — just create them
- **NEVER ask before running Python scripts** for extraction or validation — just run them

## Always Ask Before Destroying Data

- **ALWAYS ask before deleting** files, directories, or profile data
- **ALWAYS ask before overwriting** an existing profile.json (offer merge vs rebuild)
- **ALWAYS confirm** destructive operations in `/profile-delete`

## Principle

The user invoked the skill — that is the authorization. Execute the full workflow
without interruption. Only pause for user input when the skill's steps explicitly
call for it (e.g., gap analysis review in `/create-resume`, merge vs rebuild in
`/parse-resumes`).
