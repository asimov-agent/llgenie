# How to prove a PR actually merged (the merge landed, not claimed)

Written 2026-11-01 to record the #1466/#1463 landing so a future pass never re-derives or re-files it.
The rule: a merge is a fact on the remote object, never a status badge or a narration. Verb:

1. `gh pr view <n> -R asimov-agent/llgenie --json state,headRefOid,mergeCommit,mergedBy --jq '{state,head:.headRefOid,mergeCommit:.mergeCommit.oid,mergedBy:.mergedBy.login}'`
   — expect `state=MERGED`, the head you pushed, the merge commit, mergedBy.
2. Read the merged commit's stat to verify the change that actually landed:
   `git -C <main-worktree> fetch upstream main` then `git show --stat <merge-commit>`
   — the file list must be EXACTLY the intended change (for #1466: CHANGES.md + agent-wiki note +
   docs/changes.d row, nothing else; a wrong/extra file means a wrong head merged, not a green badge).
3. Confirm the artifacts are present at the merge commit and main now points there:
   `git ls-tree -r --name-only <merge-commit> -- <file1> <file2>` and `git rev-parse --short upstream/main`.
4. Confirm the issue the PR carried `Closes #N` on is closed: `gh issue view <N> --json state,closedAt`.

#1466 evidence (already recorded, do not re-file): scope run `41354112931` SUCCESS @ `096302ca`
(ci-lint+check-docs+check-wiring+check-issue-bodies+check-pr-closing+openspec), auto-merged 21:52:35Z
by asimov-agent, merge commit `c2d118d4`, #1463 CLOSED 21:52:36Z, #1413 COMPLETED, merged #1460
untouched. PR-thread finish comment `6564428792`; issue finish bookend `6564418915`.

Corollary: a coordinator (planner) dispatch can describe the PRE-completion state — raced by your
own finished work, it may still say "no PR is open yet, PROCEED and name me the number". Verify the
live object (`gh issue view <n> --json state,closedAt`, `gh pr view <n> --json state,mergeCommit`)
BEFORE acting or replying; then answer with the measured state ("already landed at <merge-commit>")
rather than re-opening, re-claiming or re-doing the vehicle. A settled ack that still describes the
old premise needs no second reply.

Fast tiebreaker when a planner keeps insisting a PR is OPEN at a head you measured as merged —
GitHub emits `refs/pull/<n>/merge` **only for OPEN PRs** (a synthetic test-merge ref that vanishes
on merge/close). Its absence is a decisive one-command merged-proof, independent of any caching:

    git ls-remote https://github.com/asimov-agent/llgenie refs/pull/<n>/merge   # empty => NOT open
    git merge-base --is-ancestor <mergeCommit> upstream/main; echo rc=$?        # rc=0 => merged onto main

Pairs with `state:MERGED` from `gh pr view`. If both say merged, do NOT `git rm`/force-push anything
to that PR's fork branch: a merged PR's branch is dead, pushing re-opens a merged vehicle and races
the landed commit — route any residual cleanup through its own tracked issue+PR instead (this session:
probe removal belonged to #1508 -> PR #1511, never a push onto merged #1467).

Corollary: a status-colour or a `/actions` page is not proof — a cancelled run reads `fail`, a job
that cannot load has zero jobs, and an auto-merge can land a last-available head. Always read the
merge commit object.

## Verify the merge's CONTENT at the merge commit, never in the working tree

When you follow step 2 ("read the merged commit's stat"), prove a specific target/file landed by
reading the **committed object** (`git show <merge-commit>:Makefile`, `git show <merge-commit>:path`,
or `gh api 'repos/<o>/<r>/contents/<path>?ref=<sha>' --jq .sha`). **Never grep the working tree** for
it. A main checkout is routinely **detached at an older commit** (or sitting on a stale local `main`),
so `grep -c <new-target> Makefile` on the working tree returns `0` even though the merged commit
defines it — a false red that makes you doubt a correct planner claim. Measured: a merged gate target
grepped `0` in the worktree (detached at an older sha) but `git show <merge-commit>:Makefile` showed it
twice. The tell is `git rev-parse --abbrev-ref HEAD` printing `HEAD` (detached): before any
grep-against-the-tree, resolve the object you mean — `git show <sha>:<file>` costs the same and cannot
lie about which tree it read.

**Never FABRICATE a full sha from a `--short` output — resolve it with `git rev-parse <ref>`, or every
`git show`/grep against it reads empty and manufactures a false "the merge does not define it".** A short
sha (`d104a156`) printed by `gh pr view`/`git log --format=%h` is a PREFIX, not the object; padding it out
by hand — or worse, reusing an old full sha from memory — names a sha that does not exist, so
`git show <bogus-full>:<file>` prints nothing and a `grep -c` over it returns 0 for EVERY target, which
is indistinguishable from "the change never landed". Measured: a hand-built 40-char sha off `d104a156`
grepped 0 for the function, the import and the prove-the-guard test that were all present on main;
`git rev-parse upstream/main` (the real full sha) grepped each 1–2 times. Resolve ONCE
(`FULL=$(git rev-parse upstream/main)` or `git rev-parse <short>`), then `git show $FULL:<path>` /
`git show $FULL:<path> | grep -c <sym>` for every read — and when a value is only ever a prefix, do not
spell a full sha at all, pass the ref NAME (`git show upstream/main:<path>`). A zero from a hand-spelled
sha is a measurement bug, not a missing merge.

**The strongest "the merge landed" proof is the merged tree's OWN test module green in the repo image:**
`git worktree add --detach /tmp/merged upstream/main` at the fetched tip, then run the changed module in
`llgenie/test:latest` (see `references/verification.md` §1/§5) against those exact landed bytes — reconstructing
the guard on a random other tree proves nothing about what shipped. **And for a fix whose whole point is BEHAVIOUR (a helper that must emit a signal on failure), executing its test module green is necessary but not sufficient — run the LANDED ARTIFACT itself against a planted failure and read the emitted output.** Extract the merged file from the commit (`git archive upstream/main <path> | tar -x -C /tmp`) and drive it with a synthetic failing input; the reported evidence is the actual lines it emits (e.g. the `::error::` annotation lines carrying the real cause) and the rc it returns — the same bytes GitHub will act on, not a paraphrase. Measured: a tail-surfacing helper's pytest passed 4/4 at the merge commit, but the merge was only *proven* by executing the merged script against a fake failing target and seeing the real cause lines come out as `::error::` with rc preserved.

## `gh pr checks` errors on a MERGED PR — read the definitive verdict from the commit's check-runs

Once a PR is `MERGED`, `gh pr checks <n>` does not return a usable check table (it errors with a
jq/arg shape such as `accepts at most 1 arg(s), received 2`, and `--json name,state` yields nothing to
roll up). That is not a red — the checks already passed (auto-merge only lands green). To get the
definitive per-check verdict at the delivered head, read the COMMIT's check-runs directly:

```sh
gh api repos/asimov-agent/llgenie/commits/<head-sha>/check-runs \
  --jq '{total:.total_count, by:[.check_runs[]|{name,conclusion}]}'
```

Every run should read `conclusion: success` (including the job that was red before the final push).
This is the measured proof `linux / unit`, `guard` ×3, `scope`, `ci-verdict`, `record`, etc. all went
green at the merged head — the source of truth that survives the merged-PR state, whereas `gh pr checks`
is only useful while the PR is OPEN. `mergeStateStatus` reading `BLOCKED` on a NOT-YET-merged PR with
`reviewDecision: REVIEW_REQUIRED` is the normal human-review gate, not a red — confirm with the
check-runs that no check is failing before treating a BLOCKED as a problem.

**Once a PR is MERGED, `mergeable` AND `mergeStateStatus` both read `UNKNOWN` — that is the normal
post-merge state, not a red, a live-scope failure, or a stale-scope artifact.** Measured on merged #1825
(04:08:33Z, mergeCommit `72fc6128`): `mergeable=UNKNOWN`, `mergeStateStatus=UNKNOWN`, while the head's
commit check-runs were all `success`. `UNKNOWN` carries NO verdict signal on a merged PR — never read it
as "still BLOCKED" or "scope still failing"; the merged proof is `state=MERGED` + `mergedAt` + the
merge-commit check-runs, never the mergeability field. A lane that reports `#N OPEN @ <sha> BLOCKED`
after the owner merged it is describing the pre-merge state; answer with `state=MERGED` + mergeCommit and
do NOT re-open, re-assert, or echo-pong a second correction (the peers already have it in queue).

## `gh api repos/<o>/<r>/pulls/<n>` reports `state:"closed"` on a MERGED PR

The REST pulls object uses `state: "closed"` for BOTH a merged PR and a closed-unmerged one — `closed`
there is NOT a failure. Disambiguate from the SAME object's booleans, never from the word:

```sh
gh api repos/asimov-agent/llgenie/pulls/<n> \
  --jq '{state,merged,merged_at,merge_commit_sha,merged_by:.merged_by.login}'
```

`merged: true` + a non-null `merged_at`/`merge_commit_sha` means it MERGED — and `merged_by: asimov-agent`
is the repo's own auto-merge, expected (this lane merging nothing, #1088 intact). `merged: false` with a
`closed_at` and no merge commit is a closed-unmerged abandonment. So when a PR reads `state: closed`, the
FIRST field to check is `.merged` — reading `closed` alone as "the vehicle failed" is the trap; it may
already be merged and merely archived. Pair this with `git merge-base --is-ancestor <merge_commit> upstream/main`
(rc=0 ⇒ on main) and a `contents?...&ref=main` read of a landed file for the full proof.

## `gh pr view --json` has no `merged` field

`--json merged` is rejected with `Unknown JSON field: "merged"` and the whole read fails. The merge
state is three separate fields: `state` (`MERGED`), `mergedAt` (timestamp or null), and
`mergeCommit.oid`. Ask for those; a `mergedAt != null` plus `state=MERGED` is the merged proof.
