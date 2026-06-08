---
paths:
  - "data/profiles/*/applications/**"
---

# Application Tracking Rules

## Required Metadata for Every Application
Every application record MUST capture:
- `person`: slug of the person who applied
- `company`: company name
- `role`: exact job title as posted
- `job_url`: original job posting URL
- `job_description_file`: path to saved job description JSON, relative to the
  person's profile directory (e.g., `job-descriptions/google_senior-swe_2026-04-12.json`)
- `resume_file`: path to the generated resume .docx, relative to the person's
  profile directory (e.g.,
  `generated-resumes/Jane_Doe_acme_senior-platform-engineer_2026-05-26.docx`)
- `applied_date`: ISO 8601 date when application was submitted
- `source`: where the job was found (LinkedIn, company site, referral, etc.)
- `status`: current application status
- `status_history`: array of all status changes with timestamps
- `consensus_rounds`: number of agent review rounds
- `agent_feedback`: summary of final agent feedback

## Application Statuses
Valid statuses in order of pipeline progression:
1. `draft` - resume being prepared
2. `ready` - resume finalized, not yet submitted
3. `applied` - application submitted
4. `screening` - passed initial screen / recruiter contact
5. `phone_interview` - phone/video screening scheduled or completed
6. `technical_interview` - technical round scheduled or completed
7. `onsite_interview` - onsite/final round scheduled or completed
8. `offer` - offer received
9. `accepted` - offer accepted
10. `rejected` - rejected at any stage (note which stage in status_history)
11. `withdrawn` - candidate withdrew
12. `ghosted` - no response after 30+ days

## Status Update Rules
- Status changes are user-initiated only (the system does not auto-update)
- Every status change appends to `status_history` with:
  - `status`: new status
  - `date`: ISO 8601 timestamp
  - `notes`: optional user notes
- Never overwrite previous status history entries
