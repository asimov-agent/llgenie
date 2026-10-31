- **Rule 3 (owner 2026-10-29): before starting ANY new issue/PR work, every lane must fetch and rebase its worktree onto the latest fetched `asimov-agent/llgenie` `main`, then report to the planner ("llgenie inbox triage" — me), so the planner can relay the assignment across the fleet (and no two bots pick one issue).** *cite #994*

- **The PR-rebase lane (`llgenie-pr-merge-conflict`) must always communicate with the other llgenie bots before rebasing an ongoing PR.** Concretely, BEFORE touching a branch with a live claim, an open PR, or a `bot-claim:` comment: message the owning lane with the id, the head sha you measured, and what you are about to do; then post the conclusion on the PR, because a decision that exists only in a DM does not exist for the next reader. A rebase another lane has to resolve by hand is the failure. *cite #994*
- **All lanes must keep their ongoing PR rebased onto the latest fetched `asimov-agent/llgenie` `main`.** Fetch fresh (`git fetch upstream main`; `asimov-agent/llgenie` is the canonical remote, a fork named `origin` is not upstream) and rebase at the sha fetched in that same moment — never a sha quoted in a message, which is stale by the time you read it. Do not rebase through a live run at the head (cancel-in-progress makes an authorised rebase destructive). *cite #994*

# Sweep mechanics — the loops that do the work

Distilled from a 30-PR sweep after a parked `main` moved. These are the shapes that worked; the
rules live in SKILL.md §8, this file is the concrete commands.

Substitute `<clone>` for the owner's checkout and keep your own worktrees beside it under
`../llgenie-wt/pr<N>-rebase`.

## 1. Measure staleness (publish this before moving anything)

```bash
cd <clone>
git fetch origin main --quiet
git fetch origin '+refs/heads/*:refs/remotes/origin/*' --quiet
git fetch fork   '+refs/heads/*:refs/remotes/fork/*'   --quiet   # only if cross-repo heads exist

# per open PR: is the new main an ancestor of the PR's tip?
#   gh pr view <n> --json headRefName,isCrossRepository  -> pick the remote
#   git merge-base --is-ancestor origin/main refs/remotes/<remote>/<branch>  -> 0 means current
```

Publish three buckets: **stale**, **already current**, **held** (`do-not-merge`, drafts). "Nothing is
stale, measured at `<sha>`" is a complete and valid result — do not pad it with no-op rebases.

## 2. Prepare a batch (reuse worktrees, never reset)

```bash
for N in "$@"; do
  read -r BR BASE CROSS <<<"$(gh pr view "$N" --repo <repo> \
      --json headRefName,baseRefName,isCrossRepository \
      --jq '"\(.headRefName) \(.baseRefName) \(.isCrossRepository)"')"
  [ "$BASE" = main ] || { echo "#$N skip: base=$BASE"; continue; }
  R=$([ "$CROSS" = true ] && echo fork || echo origin)
  git fetch "$R" "$BR:refs/remotes/$R/$BR" --quiet
  WANT=$(git rev-parse "refs/remotes/$R/$BR")
  WT=../llgenie-wt/pr${N}-rebase
  if [ -d "$WT" ]; then
    cd "$WT"
    # ff-only, never reset: a non-ff move is a finding to inspect (see §8 of SKILL.md)
    git merge --ff-only "$WANT" --quiet || { echo "#$N worktree-not-ff — inspect, do not reset"; cd - >/dev/null; continue; }
  else
    git worktree add -b "pr${N}-rebase" "$WT" "refs/remotes/$R/$BR" >/dev/null
    cd "$WT"
  fi
  git merge-base --is-ancestor origin/main HEAD && { echo "#$N already current"; cd - >/dev/null; continue; }
  GIT_EDITOR=true git rebase origin/main >/tmp/rb-$N.log 2>&1 \
    && echo "#$N CLEAN  @$(git rev-parse --short HEAD)" \
    || { echo "#$N CONFLICTS:"; grep -E '^CONFLICT' /tmp/rb-$N.log; git status --short | grep -E '^(UU|AA|DU|UD)' ; }
  cd - >/dev/null
done
```

## 2b. Before any lease push on a branch that diverged: is the push safe?

A rejected `--force-with-lease` is the *good* outcome. The dangerous outcome is a lease that **succeeds**
on a branch whose remote carried work your local branch does not, because the push silently deletes it.
Two cheap questions decide it:

```bash
# 1. Does the remote carry commits with no local equivalent?  '+' = NOT local, '-' = already local
git -C "$WT" cherry HEAD "$REMOTE/$BR"
# 2. Is the local tip just a superseded replay of the remote one?
git -C "$WT" rev-parse "$(git -C "$WT" rev-parse HEAD)^{tree}"
git -C "$WT" rev-parse "$(git rev-parse $REMOTE/$BR)^{tree}"
```

| cherry | trees | verdict |
|---|---|---|
| all `-` | either | **safe to push** — the remote's commits are already present by patch-id |
| any `+` | identical | **safe to push** — the local branch is a superseded replay of the same content |
| any `+` | different | **do NOT push** — the remote holds work with no local equivalent; a lease push deletes it. Report the `+` shas and leave the branch to its lane |

A rebase completed and parked (branch moved onto the new base, nothing pushed) is a legitimate terminal
state for a diverged branch, and a far better one than a clean-looking push that destroys work.

## 3. Gate, then push once — per PR

```bash
PARENT=<clone>                      # mount BOTH paths or git-dependent tests fail
ROOT=$(git rev-parse --show-toplevel)
TESTS=$(git diff --name-only origin/main...HEAD | grep -E '^tests/test_.*\.py$' | tr '\n' ' ')

make check-docs || { echo SKIP-gate-red; continue; }
[ -z "$TESTS" ] || docker run --rm -u root -v "$ROOT":/repo:rw -v "$PARENT":"$PARENT":rw -w /repo \
    llgenie/test python -m pytest $TESTS -p no:cacheprovider -q | tail -3

LEASE=$(git rev-parse "$R/$BR")
git push --force-with-lease="refs/heads/$BR:$LEASE" "$R" "HEAD:refs/heads/$BR"
```

`--force-with-lease` naming the ref you actually fetched is the whole collision protection: another
actor's push makes it fail loudly instead of being overwritten.

## 4. Resolving the habitual conflicts as unions

| file | what both sides did | resolution |
|---|---|---|
| `CHANGES.md` | each added a top row to the index table | keep **both** rows; main's where main has it, the branch's directly under it |
| `Makefile` `.PHONY` | each added keys | union of the key lists, order of main first |
| `.github/workflows/*.yml` `outputs:` / `run:` | both added an output, or one switched to variable style | keep both outputs; adopt main's style and add the branch's assignment in that style, then one `echo` after `fi` |
| a test file's explanatory comment | both rewrote the same sentence | keep both explanations, one block; never drop one side's reasoning |
| a test file's assertion about a deleted stage | main rewrote it, branch strengthened it | keep the **stronger** assertion plus both comments |

Validate the resolution mechanically before `rebase --continue`: no `^<<<<<<<`/`^>>>>>>>` markers, YAML
files parse, Python files compile. Conflict-marker greps must match line anchors — a bare `<<`
substring test false-positives on every heredoc in the tree.

When `CHANGES.md` conflicts in many PRs at once, do not hand-merge the hunk — take main's file
wholesale and re-insert the branch's rows, then let the gate referee:

```python
main_file = git(wt, "show", "origin/main:CHANGES.md")          # authoritative table
main_rows = {ln for ln in main_file.splitlines() if ROW.match(ln)}
branch_rows = [ln for ln in conflicted.splitlines()             # rows only the branch added
               if ROW.match(ln) and ln not in main_rows]
lines = main_file.splitlines()
sep = index of the '|---|---|---|---|' header line                 # insert under the separator
write('\n'.join(lines[:sep + 1] + branch_rows + lines[sep + 1:]))
```

`make check-docs` then proves it: it fails on a note with no row *and* a row whose note does not exist,
so a dropped or invented row cannot pass. Hand-merging the hunk is how a row disappears while the rest
of the suite stays green.

**Never trust git's rerere auto-resolution of `CHANGES.md`.** The repo shares one `.git/rr-cache`
across ~150 worktrees, so a conflicted hunk can be "resolved" from an unrelated earlier attempt: the
rebase prints `Staged 'CHANGES.md' using previous resolution.` and stages a row that is in neither
`origin/main` nor the branch — the branch's own row is gone and an invented one sits in its place.
Verify every resolution mechanically before `git add`, comparing sorted row sets:

```bash
T=$(mktemp -d)
row() { grep '^| ' "$1" | grep -v '^| Date |' | grep -v '^|---' | sort; }
row CHANGES.md > $T/work; git show origin/main:CHANGES.md | row /dev/stdin > $T/main
comm -23 $T/main $T/work   # MUST be empty: no main row dropped
comm -13 $T/main $T/work   # MUST be exactly the branch's row(s)
```

On a hit, rebuild from `git show origin/main:CHANGES.md` and insert the branch's row
(`git show <commit>:CHANGES.md | grep '^| <date> | <row text>'`) under the `|---|` separator. Also
diff the final commit against `origin/main` filtered to changed rows
(`git diff origin/main..HEAD -- CHANGES.md | grep -E '^[+-]\|'`): it must show only additions.

**A blocked `git reset --hard` in an unattended/Kanban run.** The tool refuses it, and the worktree
the dispatcher hands you is on the PR's branch but sitting at `origin/main` (it inherited the branch
ref, not the PR head), so `git merge --ff-only` cannot move it back. Once `git log
origin/<branch>..HEAD` shows nothing but main's own commits (no local-only work), use
`git checkout --force --detach <pr-head>`, rebase there, then `git checkout -B <branch>` to reattach.

## 5. Read a failing job's LOG before blaming a branch

A check's conclusion tells you *that* a job failed; only the log tells you *what* failed and whether the
branch caused it. Fetch the job id from the check run's `details_url`, then read the log — the API
refuses plain reads of some logs, so pass `--allow-escape-sequences` and strip the ANSI:

```bash
H=$(gh pr view <n> --json headRefOid --jq .headRefOid)
URL=$(gh api "repos/<repo>/commits/$H/check-runs?per_page=100" \
        --jq '.check_runs[]|select(.conclusion=="failure")|.details_url' | head -1)
JID=$(sed -n 's#.*/job/\([0-9]*\).*#\1#p' <<<"$URL")
gh api "repos/<repo>/actions/jobs/$JID/logs" --allow-escape-sequences \
  | sed 's/\x1b\[[0-9;]*m//g' | grep -E 'FAILED|assert|Error' | head -12
```

The assertion text names the test file and line, which is what lets you match it against a pristine
`origin/main` worktree and conclude "inherited, not this branch" instead of guessing from job names.

## 6. After the sweep

Re-measure staleness against the same sha and report: current / still-stale with a per-PR reason /
held. The per-PR reasons are the deliverable — "4 left, one gate-red, one blocked by another PR, two
diverged worktrees" is a report; "mostly done" is not.

## Fleet orchestration (issue #1010) — this skill's lane side

1. **report-back:** rebase/resolve to done (last push, gates green, head fixed) -> post head sha + PR number + what stands to @llgenie-planner.
2. **new-PR -> reviewer:** the planner sends new reviewable PRs to @llgenie-pr-reviever; this lane never reviews its own PR.
3. **version-here:** this behaviour is versioned by issue + PR under agents/llgenie-pr-merge-conflict/, then sync-agent-profile PROFILE=llgenie-pr-merge-conflict CHECK=1 comes back byte-identical.
4. **one lane, one PR:** before a sweep touches a PR, check bot-claim: and agent/issue-<n>-* branch; a claimed PR is another lane's (issue #994 rule 1).


## After ANY strategy-flag rebase, diff the tree against main and read what you did not intend

`-X theirs` (and `-X ours`) is a statement about **conflicts**, not about correctness. It resolves
every conflicting hunk in the chosen direction — and the damage it does is precisely in hunks that
*never showed up as conflicts*, so nothing flags them.

Measured on a 128-commit stack root: `-X theirs` silently reverted main's `ci_images.py latest
agent` back to an older `ref agent` in the `fix-loop-image` recipe. The only symptom was a unit test
asserting a command string (`tests/test_fix_loop.py:284`), which cost a 35-minute matrix on the PR
six others were stacked behind. The regression was real and later repaired by its own commit; the
*detection* came from a human diffing two trees by hand, which does not scale.

The check costs one command per file you did not mean to touch:

```bash
git diff origin/main -- Makefile        # expect: NO hunks, or only the ones you added
grep -c 'the exact string main has'    Makefile
```

Rules that follow:
- **Resolve a shared recipe/Makefile/CI file per hunk against main**, not by a strategy flag.
- **After any `-X` rebase, diff every non-generated file against main** and confirm the absent hunks
  are the ones you meant to be absent. Generated files (`CHANGES.md`, census) are regenerated, so
  they are excluded from this check by construction.
- **A test asserting a command string is a regression detector for a bad resolution**, not noise —
  when one fails after a rebase, read the string it expected before editing the test.

## Sibling PRs that touch the same doc for DIFFERENT subjects are a union, not a class

When two PRs merge in sequence and both edit `README.md`, `docs/ENGINES.md` and the same test file,
it is tempting to call the collision "one class, take main's side". That is wrong whenever the two
PRs describe **different subjects** — measured: #1050 built **sglang** from source and #1049 built
**vllm**'s three cells from source, and both legitimately edited the same three files. Taking either
side deletes a real engine's documentation, and every gate stays green because the result is
well-formed prose about one engine instead of two.

Sort the conflicted files into two shapes before resolving anything:

| shape | files | resolution |
|---|---|---|
| **aggregate** | `CHANGES.md`, a rendered index | take main's file, then regenerate from fragments (`make changes-index`); the branch's own row lives in its `docs/changes.d/<note>.md` fragment, which is the correct vehicle. Hand-merging the aggregate re-creates the collision for the next PR. |
| **sibling content** | `README.md`, `docs/ENGINES.md`, a shared test | **merge both intents**, per hunk. Read both sides. |

Never use a blanket `-X ours`/`-X theirs` on the sibling-content files. Prove the union by grepping
for both subjects after the rebase:
```bash
git show HEAD:README.md | grep -ci vllm    # both must be non-zero
git show HEAD:README.md | grep -ci sglang
git diff origin/main -- README.md docs/ENGINES.md tests/test_engine_skills.py
```
Confirm that every hunk you kept is one you meant to keep — a green test suite does not prove a
docs union, because a doc that lost one engine's paragraph still parses and still passes.

**A replayed commit that applies cleanly can still regress the base — gate the whole replay, not just the conflicts.** Stacked-replay failures are not only `UU` conflicts and empty cherry-picks: a replayed commit re-deriving a file whose canonical newer form is already on the base tip applies without conflict yet silently undoes the newer content (measured on a SOUL fleet-block copy: the older generation deleted the base's newer rule-16 bullet, reddening the very gate the branch is about). After a stacked replay, run the branches' own gate; a red in the branch's own territory is the signal to check whether one replayed commit is an older generation — drop it (keep the base's file) rather than hand-reconcile, because its intent is already satisfied by the base.

*detection* needed a hand diff of two trees, which does not scale — so `post-rebase-verify.sh` now
by `scripts/test-revert-detector.sh`, which the pytest suite runs.
runs that diff as **check 11** (every tracked text file that lost a line the base still has), proven
