---
paths:
  - "data/profiles/*/output/output-generated-resumes/**"
  - "data/profiles/*/output/output-cover-letters/**"
  - "data/profiles/*/output/output-job-descriptions/**"
  - ".claude/agents/**"
  - ".claude/skills/create-resume/**"
  - ".claude/skills/create-cover-letter/**"
  - ".claude/skills/review-job/**"
---

# Resume Writing Principles

General craft guidance for resume *content*. For document mechanics — fonts,
margins, tab stops, section order, ATS structure — see `resume-formatting.md`.

**Status of this file:** these are heuristics distilled from third-party career
advice, not laws. Where a specific reviewer, target market, or the candidate's
own stated preference conflicts with something here, those win. Record such
overrides in the person's `profile.json` under
`extraction_notes.reviewer_guidance`, not by editing this file.

## Sourcing Discipline (read this first)

Resume material fails in two directions — invented content, and *real content
attributed to the wrong person*. Both have happened in this repo.

- **Verify authorship before recording anything as a person's own statement.**
  A notes file in someone's input folder is not necessarily written by them.
  Collected advice, forum threads, and pasted articles routinely contain
  first-person claims belonging to strangers ("I managed teams of 20",
  "I applied to 10 roles and got 2 offers").
- **Never record job-application outcome statistics** for a person unless they
  state them directly and unprompted. They are the single most tempting figure
  to borrow and the least verifiable.
- When a source file turns out to be third-party material, do not silently drop
  it. Mark it in `profile.json` with a caveat and a directive so a later
  re-parse cannot reintroduce the same error.
- Advice from such a file may still be *used as advice*. The prohibition is on
  attributing its claims, credentials, or numbers to the candidate.

## The Summary

- **Tailor it per application or omit it.** A generic summary is worse than
  none — it consumes the most valuable space on the page to say nothing.
- Three to four lines maximum.
- It must state a **thesis**, not list adjectives. The test: could this
  paragraph describe a thousand other candidates? If yes, rewrite or cut.
- A summary earns its place when the career path does *not* map cleanly onto the
  target role. Its job is then to name the through-line the reader would
  otherwise have to infer — the common thread across scattered-looking roles.
- Include concrete differentiators: scale figures, named employers, the domain.
- It doubles as the answer to "tell me a little about yourself," so it should be
  speakable, not just readable.

A serviceable template:

> With [x]+ years of [type of experience] in [industry or function] across
> [sectors, company types, or specialties], I [core strengths or unique value].
> [Specific example, context, or differentiator]. [What you are aiming for next.]

Weak: *"Results-driven professional with strong communication skills and
experience in fast-paced environments."* — applies to everyone.

Better: *"Marketing analyst with 3 years of experience improving email
conversion rates by 28 percent across B2C campaigns in SaaS."*

## Accomplishments Over Technology

- State what was **delivered**, not what technologies were present. "Designed
  and integrated LLMs (named) with external APIs and libraries (named)" beats
  "incorporated a vast array of services and platforms."
- Long technology dumps read as padding and are the first thing a reviewer
  flags. Move the list to the Skills section and spend the bullet on outcome.
- Make ownership explicit where it is true — bringing a product up from nothing
  is a stronger claim than having worked on one.
- Avoid vague scene-setting ("worked at an innovative startup"). State exactly
  what was built and at what scale.
- Scale is a form of quantification. Device counts, user counts, team size,
  request volume, and data volume all work when revenue does not.
- **Never invent a number.** If a bullet feels weak without one, leave it
  unquantified or ask. See each profile's metric inventory for what is
  defensible.
- **A single action is not an accomplishment.** Filing an issue, opening a
  ticket, attending a conference, or joining a working group cost minutes and
  demonstrate nothing — anyone can do them. Keep the work that produced the
  action and drop the action. "Patched a third-party library to add missing
  namespace support" is evidence; "and filed the upstream feature request"
  is filler riding on it.

## The Depth Test

Anything given prominence — a summary bullet, a highlighted skill, a featured
project — must be something the candidate can answer extensive questions about.
Tools they have used but do not know deeply belong in the plain skills list
lower down, not in the material that invites an interviewer to probe.

A "Summary of Skills" block of 4–8 short bullets works well for senior
candidates: time in particular roles, languages, degrees and certifications
relevant to the target, major achievements, and the tools they have genuine
command of.

## Gates and Non-Gates

Not every line in a posting filters candidates, and treating them as if they do
wastes space and invites unnecessary concessions.

- A **gate** is a requirement that screens you out when unmet — no degree, no
  Python, and the reader stops. These usually sit under "Requirements",
  "Qualifications", or "You have".
- A **non-gate** is a differentiator that helps if present and costs nothing if
  absent. Look for "Exceptional candidates will have", "Nice to have",
  "Bonus", "Preferred", "It would be great if".

How to use the distinction:

- **Meet a gate → name it in the posting's own words.** This is where exact
  keyword matching earns its keep, for ATS parsing and for the human skim.
- **Miss a non-gate → say nothing.** Do not explain, apologise, or pre-empt.
  Nobody is failing the candidate on it, and raising it spends credibility to
  buy nothing. Worse, a concession placed next to a strong credential deflates
  the credential rather than reading as candour.
- **Miss a gate → concede only if it buys something**, and always **bound the
  concession**. State what the candidate *has* handled, not merely what they
  have not; an unbounded admission leaves the reader with no figure to anchor
  on, and they will assume the worst. "Nothing I have built ran at your volume"
  invites the reader to imagine your scale, which is the moment you least want
  them thinking about it.

Naming the limit of one's own claim is a genuine strength and should be
preserved — but aim it at the *work* ("a user would never report that bug"),
not at the candidate's *fitness*. Deflation about work reads as confidence;
deflation about fitness is a verdict the screener will simply accept, since
they assume the candidate would know.

**Parsing caution.** Requirements written as an OR — "experience in Java,
Python, or Kotlin" — are a single gate satisfied by any one item. Do not let a
structured job description split them into separate required skills; that turns
one satisfied requirement into two phantom gaps and distorts every downstream
gap analysis. Check `required_skills` against the posting's raw text whenever
the entries look suspiciously atomic.

## Length

- **One page is not a universal rule.** The actual goal is concise and
  efficient. Roughly: five years of experience or less should fit one page;
  beyond ten years, do not cut important content just to force one page.
- Never cram or strip white space to force a page break. A dense, marginless
  page reads as someone hiding that they have too much.
- Never leave a final page holding only a few lines — it looks unfinished.
  Rebalance the content or adjust spacing so the last page is reasonably full.
- If only the education block spills over, fix it with formatting and white
  space before cutting anything substantive.
- **Verify page count by rendering, not by estimating.** Line-height estimates
  are unreliable — a first draft has come in twenty lines over budget while an
  estimate said seven. Pass `--target-pages` to `tools/generate_resume.py`: it
  renders the document to confirm the true count and tightens spacing if needed,
  rather than trusting arithmetic.
- **Fit the page by cutting content, not by shrinking type.** Spacing presets
  buy back roughly one page across a long resume; past that the honest move is
  to remove the weakest material. Record what was dropped so a longer variant
  can restore it.

## ATS Reality

- Published or third-party "ATS scores" are not meaningful. Ignore them.
- What actually matters is that the document is single column with a
  conventional structure and standard headings. See `resume-formatting.md`.
- Practical test: upload the resume to a site running Workday and check how
  well it parses.

## Templates

Avoid cookie-cutter resume-builder templates. Millions of applicants use the
same handful, so they work against differentiation, and they constrain layout in
ways that hurt when content needs to be rebalanced. Plain, well-set word
processor formatting differentiates better and gives full control.
