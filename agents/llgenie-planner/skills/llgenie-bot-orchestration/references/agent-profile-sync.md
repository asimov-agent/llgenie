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

## Drift needs TWO sets: by-name AND by-content

A name-set diff (`comm` on two sorted filename lists) finds tree-only and live-only files, and stops there. It
**cannot see a file present on both sides with different content** — the commonest drift, where the tree holds an
older, truncated copy and live has grown. Equal file counts prove nothing: tree=66 / live=66 with 11 content-diffs
is 11 unsynced files, and a names-only scan reports "0 live-only" and looks clean.

Always measure both, per file, on the same fetched sha:

```bash
T=$(mktemp); L=$(mktemp)
git ls-tree origin/main --name-only agents/<lane>/skills/<skill>/references/ | sed 's|.*references/||' | sort > "$T"
ls -1 ~/.hermes/profiles/<lane>/skills/<skill>/references/ | sort > "$L"
comm -23 "$L" "$T"   # live-only: absent from tree
comm -13 "$L" "$T"   # tree-only: dead in the tree
while read f; do t=$(git cat-file blob origin/main:agents/<lane>/skills/<skill>/references/"$f" | sha256sum | cut -d' ' -f1)
  l=$(sha256sum ~/.hermes/profiles/<lane>/skills/<skill>/references/"$f" | cut -d' ' -f1)
  [ "$t" = "$l" ] || echo "DIFF $f tree=$t live=$l (tree=$(git cat-file blob origin/main:.../"$f"|wc -c) live=$(wc -c < .../"$f"))";
done < "$T"
```

- Report a DIFF with **both hashes and both byte counts**: `live > tree` on every row is the signature of
tree-truncation (a stale fold), which is a different fix from a genuine divergence.
- A fold that closes the absent-file set does **not** close the drift. Re-scan after it merges: new live-only files
  appear as the lane keeps learning, and the content-diff set a names-only scan never measured is still there.
- Dispatch the fold as one issue listing **every** row (both classes) with its sha256, and accept it only on a
  per-file live==tree sha256 table in the report — a count of files is not evidence of sync.

## "cmp=0 vs live" is a claim; re-diff the PR head against CURRENT live

A fold PR reports "byte-identical, SOUL n b / SKILL n b, cmp=0". Verify it yourself at the PR's real head,
not the head the lane quoted (a lane often reports the sha from before its last push):

```bash
git fetch origin 'refs/pull/<n>/head:pr<n>'
diff <(git show pr<n>:agents/<lane>/skills/<skill>/SKILL.md) \
     ~/.hermes/profiles/<lane>/skills/<skill>/SKILL.md && echo IDENTICAL
```

When this diffs, the fold copied a **pre-accretion snapshot** — the live file gained lessons after the lane
copied it, so the tree ships silently behind live. Acceptance is byte-identity to CURRENT live at fold time.
Send the lane back to re-read live, byte-copy, and force-push the **same** branch (one vehicle), then prove
the diff empty before reporting. SOUL can match while SKILL is stale — check each file, not the pair.

## What to commit

`SOUL.md`, `SKILL.md`, and every `references/` file the live skill actually has — including ones the tree lacks. A tree
that carries four references while the live skill carries five is not synced, however green the four look.

## A live writer re-grows the rows you just cleared

A lane can land a correct sync vehicle whose `CHECK=1` is green at its head, and the live copy is **edited again
minutes later** — so the gate reports live-longer / live-edited-not-tree for a file the lane never touched. Measured
across a fleet: three different lanes' live profiles were mutated within the same few minutes, always right after a
clearing commit, with no lane session open.

Consequences that belong in every reply to such a lane:

- **Do not launder an unknown-author live edit into an armed PR.** Its content is not the lane's, the PR's evidence
  no longer describes its head, and the never-launder rule is what keeps a reviewed diff a reviewed diff. Refusing is
  correct; the lane that says "not mine, not in my commit" is doing the job right.
- **Do not open a fresh follow-up vehicle yet either** — the writer will re-grow the file before the follow-up merges,
  so the chase never converges. Route the observation to the single gate issue that stops the live write, then do one
  clean sync per lane once the writer is dead.
- **A second vehicle on a row that already landed is the #824→#835 mistake.** When a re-dispatch arrives after the
  lane already shipped its PR, say plainly that the earlier dispatch is moot and the existing PR stays the single
  vehicle — never a clone.
- **Attribution is the finding, not the file.** Same-minutes mutations on several lanes means an unowned process, not
  several careless lanes; report the mtimes side by side on the gate issue.

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
