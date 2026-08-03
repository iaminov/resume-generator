---
name: track-application
description: Update application status, view application history, or get a summary of all active applications
---

# Track Application Skill

Manage and update application tracking records for the active profile.

## Resolve Active Profile (applies to all commands below)

Before any command, run `python3 tools/profile_switch.py` to get the active
profile slug. If none set, tell user to run `/profile-switch` or `/profile-create`.

All commands operate on `data/profiles/{slug}/applications/`. To view another
person's applications, first run `/profile-switch`.

## Finding Applications

When searching for a specific application (by company name, role, or any keyword):
1. **Always read the JSON files** — do NOT rely on filename grep alone. Filenames
   are slugified and may not match the user's search term (e.g., the file might
   be `private-equity-firm_...json` but the `company` field inside is `"Acme Capital"`).
2. Read all application JSON files in the directory, check the `company`, `role`,
   and other fields inside each file.
3. Use case-insensitive matching.
4. If no match is found, say so — but only after checking the actual JSON content
   of every application file, not just the filenames.

## Commands

### Search status
User says: "how's my job search", "what's outstanding", "anything gone quiet"

Run `python3 tools/application_status.py`. It reports active applications,
anything with no movement past the threshold, overdue follow-ups, and generated
documents built from an older `profile.json` than the current one. Use
`--stale-days N` to tighten or loosen the quiet threshold, `--json` for
machine-readable output.

Do not compute this by reading every record and doing date arithmetic by hand —
terminal statuses must never be reported as quiet, and that rule lives in the tool.

### Update status
User says: "update [company] [role] to [status]"
1. Find the application in `data/profiles/{slug}/applications/`
2. Ask for optional notes
3. Run `python3 tools/application_update.py <record> --status <new> [--notes "..."]`
4. Report the result, including the `valid_next` statuses it returns

**Do not hand-edit the JSON for a status change.** The tool validates the
transition against a defined graph, appends to `status_history` rather than
rewriting it, timestamps the entry, journals the change to `activity_log`,
validates against the schema before and after, and writes atomically.

- To see where a record can go: `--show`
- If the tool refuses a transition, it is because the move skips a stage or
  leaves a terminal state. Surface that to the user. Only pass `--force` when
  they confirm it really happened — it records a warning in the output.

### Add contact
User says: "add contact [name] for [company]" or "met [name] at [company]"
1. Find the application
2. Add to `contacts` array: name, role (recruiter/hiring_manager/interviewer/peer/other),
   title, email, linkedin — whatever the user provides
3. Auto-append an `activity_log` entry
4. Save and confirm

### Log interview
User says: "log interview for [company]" or "had [type] interview at [company]"
1. Find the application
2. Add to `interviews` array: date, type, interviewers, duration, topics, notes, sentiment
3. If interviewers are named, ensure they exist in `contacts` (add if not)
4. Auto-append an `activity_log` entry
5. Auto-update status if needed (e.g., `applied` → `phone_interview`)
6. Ask if any follow-ups to schedule (e.g., "send thank-you email by tomorrow")
7. Save and confirm

### Add note / log activity

Use `python3 tools/application_update.py <record> --log "what happened"` rather
than editing `activity_log` by hand; it timestamps the entry and revalidates.

User says: "note for [company]: ..." or "log: recruiter emailed about next steps"
1. Find the application
2. Append to `activity_log` with timestamp and the user's text
3. Save and confirm

### Update compensation
User says: "comp for [company]: ..." or "offer from [company]: ..."
1. Find the application
2. Update `compensation` — `posted_range`, `discussed_range`, `offer`, or `candidate_target`
   depending on what the user provides
3. Auto-append an `activity_log` entry
4. If user provides offer details, ask if status should move to `offer`
5. Save and confirm

### Add follow-up
User says: "follow up with [company] by [date]" or "remind me to [action] by [date]"
1. Find the application
2. Add to `follow_ups` array: action, due_date, completed=false
3. Auto-append an `activity_log` entry
4. Save and confirm

### Complete follow-up
User says: "done: [follow-up action] for [company]"
1. Find the matching follow-up
2. Set `completed: true`, `completed_date` to today
3. Auto-append an `activity_log` entry
4. Save and confirm

### Close application
User says: "close [company] as [result]" or "rejected from [company]"
1. Find the application
2. Set `outcome`: result, reason, feedback, would_reapply, lessons_learned — ask
   for whatever details the user wants to record
3. Update status to the terminal status
4. Auto-append an `activity_log` entry
5. Save and confirm

### View application
User says: "show [company] [role]" or "show application for [company]"
1. Find and display the full application record
2. Include: role, company, status, applied date, contacts, interviews,
   compensation (if any), upcoming follow-ups, activity log (recent entries),
   agent consensus summary

### List all applications
User says: "list applications" or "show all applications"
1. Read all files in `data/profiles/{slug}/applications/`
2. Display summary table:
   ```
   Date       | Company    | Role              | Status     | Next Follow-up | Days
   -----------|------------|-------------------|------------|----------------|------
   2026-03-15 | Google     | Senior SWE        | screening  | Thank-you (4/13) | 28
   2026-03-20 | Meta       | Staff Engineer     | applied    | Follow up (4/14) | 23
   ```
3. Highlight overdue follow-ups and applications needing attention
   (applied 7+ days ago with no status change)

### Application stats
User says: "application stats" or "show stats"
1. Calculate and display:
   - Total applications by status
   - Response rate (any response / total applied)
   - Interview rate (any interview / total applied)
   - Offer rate (offers / total applied)
   - Average days to first response
   - Applications per week/month
   - Overdue follow-ups count

## Activity Log Rules
The `activity_log` is the running journal for each application. Every mutation
to the application record should auto-append a log entry with a timestamp.
Users can also add free-form notes directly. The log is append-only.

## Critical Rules
- Never auto-update statuses unless it's a clear consequence of a logged event
  (e.g., logging an interview when status is `applied`)
- Warn if a status transition seems unusual (e.g., `applied` → `offer`)
- Always append to `status_history` and `activity_log`, never overwrite
- When the user mentions a person's name in context of a company, check if
  they're already in `contacts` before adding a duplicate
- Compensation data is sensitive — never include it in summary tables,
  only in individual application views
