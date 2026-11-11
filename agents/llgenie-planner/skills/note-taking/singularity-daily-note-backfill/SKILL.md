---
name: singularity-daily-note-backfill
description: Backfill singularity vault daily notes from git history.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [Obsidian, Notes, Singularity, Backfill]
    related_skills: [obsidian]
---

# Singularity Daily-Note Backfill

## When to Use

Use when the user asks to go through the singularity vault's daily notes for past days and mark all checkboxes, answer the reflection questions, and (for Sundays) complete the weekly review and create the clarity/gain files. Trigger phrases: "go over one daily note day at a time", "mark all checkboxes", "answer each question", "create the clarity and the gain md files".

Fill in the `business/singularity` Obsidian vault's daily notes (`04_daily_notes/YYYY-MM-DD.md`) for a range of past days: mark every checkbox, answer every reflection question, fill the protocol/gratitude blocks, and for Sundays complete the weekly review and create the `27_clarity/` and `28_gain/` files. Answers are grounded in the repo's git history, never invented.

## Procedure

1. **Stay on the feature branch, never commit/push.** Work in `$HOME/repository/git/business/singularity` on the current branch (e.g. `encrypted-clean`). Leave all changes uncommitted and unpushed for the user to review — do not commit, do not push, do not touch `main`. Confirm at the end that HEAD is unchanged and `git rev-list --left-right --count origin/<branch>...HEAD` is `0 0`.

2. **Determine which days exist from git, not by assuming a date range, and re-check it after every user action.** Run `git log --name-status` on the branch and collect which `04_daily_notes/YYYY-MM-DD.md` files actually exist. A day may be deleted in history (e.g. `2026-10-05` was removed) — skip it. Skip today's date too: today's note is the one being written, not backfilled.

3. **Gather evidence per day before writing.** For each existing day, run `git log --since="<date> 00:00" --until="<next-day> 07:00" --name-status --pretty="@@ %h %ad %s"` (the 07:00 next-day bound catches the user's late-night/early-morning commits that belong to that day's session) plus the relevant diffs. The commits touching that day's note, the permanent notes, prospects, and plans created that day are the source of truth for the reflection answers. Read the note's current content first so you know which fields are already filled.

4. **Fill each note, preserving the user's own answers.** Mark all `- [ ]` → `- [x]`. Fill all `_________________` blanks. Answer the 8 reflection bullets, Protocol 1 (limiting belief / where it came from / evidence it's false), Protocol 2 (old identity / new identity / future self), "Evidence showing up", and Gratitude — all from the git evidence. **Only fill empty fields; never overwrite text the user already wrote** (e.g. a day where the user answered some bullets themselves — leave those untouched).

5. **Sundays get the weekly review + two new files.** A note is a Sunday when it contains `## 📅 Weekly Review Every Sunday`. For those: fill the FK Commitment Declaration, Weekly Wealth Space Reset, and Review weekly activations; add a `### 🔄 Monthly Wealth Audit` with its three questions answered; fill Clarity and GAIN with a summary plus a wikilink to the new file. Then create `27_clarity/YYYY-MM-DD.md` and `28_gain/YYYY-MM-DD.md` following the vault's existing file format (frontmatter + Clarity paragraph + Weekly Clarity Score table; Gratitude / Achievement / Insight / Next).

6. **Verify before reporting done.** Run `scripts/verify_backfill.py` (or the equivalent checks): 0 unchecked boxes, 0 `_________________` blanks, 8/8 reflection bullets filled, weekly sections filled for Sundays, and `git status --short` shows only the modified daily notes + new clarity/gain files with HEAD unchanged.

## Pitfalls

- **Order the checkbox pass before the weekly-section patch, and anchor on `- [x]`.** The blanket `- [ ]` → `- [x]` replacement runs first, so a later patch whose anchor still says `- [ ]` fails its uniqueness assertion. Either patch the weekly section first, or write the anchor with `- [x]`.
- **A bullet is filled if the answer sits inline on the header line.** The reflection answers are appended on the same line as the bullet header, so a naive "is the body after the header empty" check falsely flags every bullet as empty. Count a bullet as filled when the text after the header on the same line is non-empty OR the following body is non-empty.
- **Strip the signal bullet's template tail before checking emptiness.** The "What signal did I broadcast today?" bullet carries a literal ` (scattered/fearful vs coherent/powerful)` tail; remove it before deciding the bullet is empty.
- **Don't assume consecutive days.** A missing date in the range is a deleted note, not an oversight — confirm via `git log --name-status` and skip it.
- **Fill the Protocol 1/2 fields in place, never as added sub-bullets.** The seven `_________________` fields (`Limiting belief I caught today: … → **Replacement:** …`, `Where did this belief come from?`, `What evidence proves this belief is false?`, `Old identity pattern I'm releasing:`, `New identity I'm stepping into:`, `What would my future self do in this situation?`) sit directly under the protocol checkbox line and must be replaced on their own line. Appending `  - <text>` under the checkbox leaves the blanks empty and diverges from the format of the already-filled notes.
- **Fill each field only when its anchor is present exactly once.** A field whose `_________________` anchor is absent is already filled — skip it, don't error. A field whose anchor appears more than once needs a unique surrounding-context anchor. This makes the fill tolerant of days where the user already answered some protocol fields (e.g. a Sunday whose protocol is complete but whose Evidence line is blank).
- **When the user extends the window ("go back 14/30 days"), re-scan the whole new range and work only on existing notes.** Missing dates in the extended range are ignored and reported as an explicit list; never restore them. Re-run the existence check for the full new range before writing, and report which dates had no note so the user sees the skip.
- **A day whose note does not exist is IGNORED — never restored.** Never run `git restore --source=<parent> -- 04_daily_notes/<date>.md` to bring a deleted day back, even if the user picked that date from a list of options. Work only on notes present in the working tree; a missing day is skipped and reported. Un-instantiated Templater stubs are junk the user deletes in bulk. A daily note that is ~2.7 KB, has no frontmatter, starts with `# <% tp.user.next_date() %>` and contains `<% tp.file.include(...) %>` lines was never rendered — it is a raw template dump, not a day's note. The user deletes these in one sweep (`git log --diff-filter=D -- 04_daily_notes/*.md`). Never offer such a day as backfillable and never restore it from history.
- **The user commits the backfill themselves, mid-session.** HEAD can move (and days get deleted) while you are working. Re-read `git log --oneline -1`, `git status --short` and the file list before each day, and never re-commit or revert what the user committed.
- **`.obsidian/workspace.json` may show as modified** by Obsidian itself; that is not your change and should not be reverted or committed. Obsidian's git plugin can also stage files (`M ` in the first status column) — leave the index alone and never commit it.
- **The gratitude line's wording varies between notes** ("Who did I appreciate today?" vs "Who did I appreciated today?") and is often already filled inline. Match it with a loose regex on `Gratitude: Who did I appreciat`, and treat any text already on the line as the user's own answer.
