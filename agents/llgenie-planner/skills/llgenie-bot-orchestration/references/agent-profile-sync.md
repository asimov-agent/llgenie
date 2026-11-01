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

## Run the gate itself: no `--agents-dir`, clean worktree, count every class

`scripts/check_agent_profiles.py check` **auto-resolves** the live profiles (default `~/.hermes/profiles`) from the
host layout and compares them to the tree. Do not pass `--agents-dir`: it is interpreted *relative to `--root`*, so an
absolute live path aborts with `'.../.curator_backups' is not in the subpath of '<root>' — NOTHING was checked` and
`rc=2`. That `rc=2` is a bad invocation, not repo state — do not report it as the gate verdict.

Run it from a **clean detached worktree off `origin/main`**, never the primary clone and never your own tree:

```bash
rm -rf /tmp/wt-gate && git worktree add -f --detach /tmp/wt-gate origin/main
cd /tmp/wt-gate && python3 scripts/check_agent_profiles.py check; echo rc=$?
```

The primary clone reads `REPO_ROOT=Path(__file__).parents[1]` as its own stale checkout and reports false drift; a
clean worktree makes `REPO_ROOT` the fresh tree while `live_root` still resolves to the real host profiles.

**Never assert `rc=0` / "ZERO findings" from memory or an earlier run** — measure in this pass and quote the exact rc
plus a per-class count, because the finding set changes every time a lane's live file is edited:

```bash
for k in live-longer live-lines-missing absent-from-tree live-edited-not-tree; do
  printf '%s: ' "$k"; python3 scripts/check_agent_profiles.py check --only $k 2>&1 | grep -cE 'FAIL'; done
```

Broader row-scope drift (many lanes' live-only files + grown content) is ONE fleet tracker, not a new issue per
measurement; when the count grows between filings, that is scope growth on the same tracker. A single planner-lane
fold's acceptance gate is `0/0/0` at *its* head and covers every live-longer row for that lane, not just the named few.

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

## A fold green at its PR head can be red at its MERGE head — that is a new drift, not a merge defect

After a fold PR merges, run the gate at the **merge commit**, not the PR head you already watched go green. If rows
reappear, compare each row's live mtime to the fold's tree-commit time:

- Rows whose live mtime is **after** the tree commit were re-grown on top of the fold (the live writer above), so the
  merge itself was valid and the residual drift is a **fresh instance** of the same class — not evidence the merged
  fold was wrong.
- Adjudicate it on a **new** tracker, naming the merge commit, the per-row live mtimes, and the gate rc/class counts.
  A closed `COMPLETED` fold issue is **not** a retry vehicle: a closed issue carries no new work, and reopening it
  re-opens a claim its merge already settled. State plainly that the old issue stays closed and the new issue is the
  correct vehicle — do not reopen it, and do not call the surviving merge a defect.

This is the standing post-merge mandate applied to a fold: the fold's own acceptance ("0 rows for my lane at the PR
head") can fail to survive its merge head without the merge being at fault. Say which it is with the mtime comparison.

## Measure the writer dead before any re-cut — a freeze test, not a hunch

A fold whose target is a live file only holds if the file stopped growing. Requesting a re-cut while the target is
still moving guarantees the fold lands behind live again and the next pass repeats the whole exchange — the chase
never converges. But refusing every re-cut "because it keeps moving" is the opposite failure: the gate can never
close and the lane waits forever. Decide with a measurement, not a mood:

```bash
F=~/.hermes/profiles/<lane>/skills/<skill>/references/<file>.md
S1=$(stat -c%s "$F"); sleep 20; S2=$(stat -c%s "$F")
stat -c '%y %s' "$F"   # mtime + size; compare mtime to `date -u`
echo "S1=$S1 S2=$S2"
```

- **Frozen** = size unchanged across the window AND no mtime change for a couple of minutes. Only then is a re-cut
  valid, and it is **exactly one** re-cut on the **same** vehicle at that frozen size — never a new PR, never a
  re-fold per pass.
- **Unfrozen** = size or mtime still moving. Do **not** request a re-cut (it will be shot at a moving target); state
  the freeze condition explicitly on the PR and tracker so the lane knows what unblocks, and re-measure next pass.
- Re-check the freeze immediately before the lane copies, and tell it to do capture→copy→commit→verify in one shot:
  if live moves again mid-fold, stop-and-report rather than chase. The acceptance is byte-identity at the fold
  moment, and a fold that lands while frozen is the acceptance.
- **Keep in-session working notes in your scratch ledger, not appended into a live gate-authoritative reference.**
  A live profile ref is versioned content under a drift gate; writing pass notes into it re-grows exactly the row the
  fold just cleared, so the note that "stops the drift" is itself drift. Stage notes in scratch, then let the single
  fold PR carry the durable lesson.

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
