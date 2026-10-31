# Versioning an agent's own instructions

A lane's `SOUL.md` and skills are versioned repository content, not private state. This governs syncing them and
judging whether another lane's versioned claim is true.

## The tree copy is the reviewed one; the live profile is the running one

Edits that change how a credential-holding agent behaves belong in the repo under `agents/<profile>/` via an issue and
a PR, so the instruction can be diffed and traced to an incident. A live-only edit is invisible to every other lane
and to the owner, which means the next lane relearns the same lesson.

- **The repo path may not exist yet.** Check before telling a lane to open its versioning PR:
  `gh api repos/<o>/<r>/contents/agents?ref=<main-sha>` — a 404 means the tree has not landed, and *no* lane can
  comply. That is a precondition to merge, not a lane failing to follow the rule.
- Recording a lesson live while a repo PR is pending is staging, not the destination — say which PR will carry it,
  and hold the lane to it.

## Sync direction: live can be LONGER than the tree

The sync tool copies tree → live. When the live profile carries material the tree lacks, a write-mode sync **deletes**
it, and no gate notices — the failure is silent by construction.

```bash
make sync-agent-profile PROFILE=<lane> CHECK=1     # OK: N file(s) match byte for byte, exit 0
```

- **Always `CHECK=1` first**, and never run write mode for a profile whose live copy is richer.
- Reconcile by committing the **live** content into `agents/<profile>/` and proving `CHECK=1` green afterwards — the
direction is evidenced in the PR body with sizes on each side.
- **A byte count is a measurement at one time.** Syncing from a size quoted earlier in a conversation reverts the
  lessons written since. Read the live size in the same command that decides, and state the sha you measured at.
- The gate that makes this measurable is a `check-agent-profiles`-style check: it reports each file whose live copy
  is longer than the tree's, with the byte counts and the first missing heading — the difference between "this is
  versioned" as a claim and as a check.

## What to commit

`SOUL.md`, `SKILL.md`, and every `references/` file the live skill actually has — including ones the tree lacks. A tree
that carries four references while the live skill carries five is not synced, however green the four look.

## When the skill file is too large to patch

`skill_manage` refuses a save when a skill's `SKILL.md` exceeds roughly **100,000 characters**, aborts the whole batch
and **rolls back every touched skill**. The refusal is silent from the lane's side: it reports "I recorded it", which
is true of the attempt and false of the artifact. If the profile also has a duplicate copy of the skill, the patch
retargets there instead — which is the mechanism behind a lane that appears to "keep forgetting" a rule it keeps
writing down. A file that has crossed the line is un-patchable, not stubborn.

Measure before blaming the lane or rewording the lesson:

```bash
wc -c ~/.hermes/profiles/<lane>/skills/<skill>/SKILL.md
# size each section, largest first — the split target is the top one
awk '/^## /{if(n)print n" "c" "h; h=$0; c=0; n=NR} {c+=length($0)+1} END{print n" "c" "h}' SKILL.md \
  | sort -k2 -rn | head
```

Then split **by section**, never by concatenation:

1. Move the largest self-contained section **verbatim** into `references/<topic>.md`, with a one-line header saying it
   was moved and why.
2. Keep the heading in `SKILL.md` and leave a pointer under it (`See references/<topic>.md.`) so a reader still finds
   the rule where it is used.
3. **Prove nothing was lost by comparison, not by eye** — every non-blank line of the old section must appear in the
   new file; print `content lines: N, missing: 0`.
4. Re-run the lint immediately: replacing a section leaves the *next* heading with no blank line before it, and a
   markdown linefeed gate rejects exactly that. Expect to insert blank lines and re-lint.
5. `CHECK=1 make sync-agent-profile PROFILE=<lane>` and mirror the tree copy, then **prove the cap is clear with a real
   `skill_manage` save** — the save is the evidence, and a lesson *about* the cap recorded through the cap is the only
   one that shows the cap moved.

Do not raise the cap and do not split by concatenating whole files: a line-wise union strips blank lines and fences, so
shell comments inside fenced blocks are then read as markdown headings and the lint gate rejects the file. A gate that
fails at the true cap and warns below it is the durable fix, so the next file that grows by accretion is visible before
it becomes un-patchable.

## A verification run of another lane's scripts needs an extraction, not a worktree

To check that a lane's shipped scripts and their tests actually work, extract the head — do not create a worktree (it
is debris nobody may prune) and do not run the profile's copy (that is not the shipped artifact):

```bash
git archive <pr-head-sha> | tar -x -C /tmp/<dir>
cd /tmp/<dir> && python -m pytest tests/<the lane's test file> -q
a=agents/<lane>/skills/<skill>/scripts/<script>.py; ls -l "$a" | cut -c1-10; python "$a"
```

Run the **tree** copy and report what it did — including a refusal. A tool that fails fast on a missing premise
(`refs/remotes/origin/main missing`) is behaving correctly and is a better finding than one that prints a plausible
report from an unprepared tree. Remove the scratch directory afterwards; it was never a worktree.
