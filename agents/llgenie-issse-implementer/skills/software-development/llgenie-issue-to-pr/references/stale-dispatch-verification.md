# Stale-dispatch guard: verify before you act

A dispatch that names a PR, a run id, or a failing test is a **claim, not a measurement**.
The planner/board can read a detached view (merged PRs listed as OPEN, superseded runs
listed as live). Measure these fields, then act — or decline with the evidence.

## 1. A CI red is current only if its run is newer than the merge

```
gh api repos/O/R/actions/runs/<run-id> --jq '{created_at,head_sha,conclusion}'
gh pr view <n> --repo O/R --json state,mergedAt,headRefOid
```

If `run.created_at < pr.mergedAt`, the run executed on a **superseded intermediate
head**, before the branch advanced and merged green. Doing nothing is correct. A
`linux/unit` failure on such a run is already fixed at the merged head.

**A cited head sha that exists but sits on NO origin ref is an orphaned intermediate
head.** `git cat-file -e <sha>` only proves it exists; test liveness with
`git for-each-ref --contains <sha> refs/remotes/origin` — **empty output means the
branch advanced past it and merged, so any red run at that sha is history.** A dispatch
telling you to "re-push at head <sha>" where that sha is orphaned is impossible and a
#824 violation on a merged, read-only vehicle. Refuse with the merge sha and the
origin/main is-ancestor proof.

## 2. A 404 branch after merge means the branch is gone

```
gh api repos/O/R/branches/<branch> --jq .name   # 404 = deleted after merge
```

There is no branch to "fix same-branch" or re-push to. Say so; never invent one.

## 3. Run the claimed-failing test yourself on a fresh origin/main

```
git worktree add --detach $TMPDIR/v origin/main
(cd $TMPDIR/v && python -m pytest tests/<file>::<test> -q -p no:cacheprovider)
git worktree remove --force $TMPDIR/v
```

Green there disproves the claim outright (the wiring is genuinely in the manifest; the
tree is genuinely wired). Never weaken the assertion to make it pass.

## 4. Prove the merged head shipped green

```
gh api 'repos/O/R/actions/runs?head_sha=<merged-head>' --jq '.workflow_runs[]|{name,conclusion}'
```

CI + ci-scope + holds all `success` at the merged head is the proof the deliverable
landed green. Cite it in the correction.

## Before declaring a dispatched file or target ABSENT, resolve it in git

A dispatch naming `scripts/<x>.py` or a `make <target>` can look missing when the search
tool, not the tree, is at fault. A name-glob (`*<x>*.py`) or a line-anchored grep
(`^<target>:`) misses a genuinely tracked file or a target declared on a SHARED line with
siblings, and the workflow then reads as "the dispatch is stale" when it is not. Resolve
against git before concluding anything:

```
git cat-file -e HEAD:scripts/<x>.py && echo present   # authoritative existence at HEAD
git ls-files -- 'scripts/*.py' | grep -F '<x>.py'
git grep -n '<symbol-or-target>' HEAD -- Makefile .github/workflows
```

Only after `git cat-file`/`git ls-files`/`git grep` also come up empty is a dispatched path
truly absent (then check `git log --all --oneline -- <path>` for a file that existed in
history but was removed). A wrong-path conclusion from a failed glob wastes a full cycle of
re-dispatch.

## Correcting the planner

Send one message to `@llgenie-planner` carrying the API fields you measured: run
`created_at` vs `mergedAt`, branch 404/200, test rc, merged-head run conclusions.
Never re-dispatch a fix for merged work and never fabricate a change to satisfy a
stale claim.

**One live-API pin, then STOP re-measuring.** Once
`gh api repos/O/R/pulls/<n>` shows `merged=true` and the issue shows `state=closed`,
`reason=completed`, every later planner/ack replay gets the SAME answer. Reply once —
"already verified: PR <n> merged at <merge-sha>, issue closed <time>, no re-measure" —
and hold. Do not spend a new tool call proving it a 3rd..9th time; that is churn, not
rigour, and the peer is replaying its own queued prior pass, not disputing you.

**When the same stale claim replays a 4th+ time, move the proof onto the issue thread.**
A DM is a point in a queue the peer may replay out of order; an `gh issue comment` is
immutable and dated. Post there once — the measured timestamp, `state/state_reason/closed_at`,
`pulls/<n>` `merged_at`+`merge_commit_sha`, the branch ref sha (fork and origin), the
current open-PR list, and the stale shas the peer quoted — then one short DM pointing at
that comment id and stop. This ends the loop without a 10th re-measure and leaves the
next reader a citable anchor.

**After a merge, `git/ref/heads/<branch>` can lag the PR object.** It may still return
the branch's OLD first/pre-rebuild commit while `pulls/<n>.head.sha` is the rebuilt head
that actually got merged. Read `head.sha` and `merge_commit_sha` from the PR; never
"diagnose a red" at a branch-ref sha that is not the PR's `head.sha` — that red belongs
to a superseded intermediate.

**A dispatch to CLAIM an issue the API returns as merged/COMPLETED is a duplicate-vehicle
request (#824).** Decline on-record with the merge sha + closed-at and do NOT cut a
worktree off a stale `origin/main <sha>` to re-claim landed work; a second vehicle for
a closed issue is the defect, not the fix.

## A dispatch's failure MECHANISM is a hypothesis — reproduce it before you author a fix

A dispatch rarely says only "this test is red"; it explains WHY ("the index has no wheels so the
resolver still picks the placeholder", "the build backend is poetry"). That mechanism is as much a
claim as the run id. Authoring a fix against a misdiagnosed mechanism produces a diff that changes
nothing real — and worse, a "deepen" that mutates a correct implementation. Verify the mechanism
before the first edit.

1. **Read the CITED run's own log for the exact error string the dispatch names.** Grep the failed
   log for the claimed line (`poetry`, `rocm==0.1.0`, `No module named …`). If NO run in the
   candidate set (`gh run list --branch <b>`) ever logged that error, the premise has no evidence —
   it may be a different failure wearing the same label. A common trap: the cited "engine-build red"
   is actually `Cache export is not supported for the docker driver` (a pipeline docker-driver
   defect), miles from the packaging failure the dispatch attributes to it.
2. **Reproduce the mechanism with a live minimal probe using the TREE'S EXACT flags**, not a
   hand-typed guess at them. Resolver/packaging claims are falsifiable in seconds:
   `uv pip compile --python-version <v> --python-platform linux --index-strategy unsafe-best-match
   --extra-index-url <url> -o out.txt <req>` and read what it actually resolved. If the resolved
   set contradicts the dispatch (e.g. it picks the real `rocm==7.14.1` sdist, not the `0.1.0`
   placeholder), say so with the probe output BEFORE writing code.
3. **"The index has zero .whl files" is NOT "the index lacks the package."** A PEP-503 simple
   index that lists only `pkg-<ver>.tar.gz` tarballs still serves `pkg` — as an sdist for that
   exact package name. Under `--index-strategy unsafe-best-match` uv picks the HIGHEST version
   across all configured indexes, so an index offering `7.14.1` beats a PyPI placeholder at `0.1.0`;
   the sdist's build backend is whatever it declares (check `build-backend` — a setuptools sdist
   needs no poetry even if the placeholder in PyPI uses one). Confirm the mechanism at this level
   before concluding the current flags "cannot defeat" the placeholder.
4. **Do not force-push the deepen over a live push=true verdict run at the same head.** A
   `workflow_dispatch` with `push=true` compiling the target cell (rocm/cuda/cpu) is the ground
   truth; `cancel-in-progress` makes an authorised push destructive. Hold the push, report the
   measured contradiction on the issue + a DM to the planner, and author the deepen only against
   the ACTUAL log once the run concludes — or report green if its cell passes.

## Lane boundary (route, don't implement)

- `.github/workflows/*` or a gate-source change (`PR_BODY:` event-snapshot, gate
  scripts feeding `ci.yml`/`scope.yml`) → `@llgenie-ci-pipelines-maintainer`.
- Doc-only change → documentation lane. Security finding → `@llgenie-security`.
- Route with the issue number and the owning lane; do not cut a worktree.

## Pitfall found in practice

SKILL.md sits at the 100,000-character limit; a new SKILL.md section is rejected.
Extend `references/` instead, and rely on `skill_view`'s `linked_files` listing for
discovery — do not attempt a pointer patch, it overflows too.
