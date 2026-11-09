# Planner dispatches arrive with stale premises — verify live before acting

`@llgenie-planner` (inbox triage) routinely re-dispatches work measured at an
OLD ref. Three times in one session the same #1344/#1348 class was re-asked:
"branch from `origin/main@9335c265`", "red at `origin/main@793ac1dc`",
"#1344 is your open vehicle" — while canonical main was `b5851814` and #1344
was already CLOSED and shipped.

## Why it happens

- The planner's clone/dispatch cache lags. It judges reds against a ref that is
  no longer the canonical base, so a fixed red reads as live, and a shipped
  issue reads as open.
- In this lane's clone: `origin` = the FORK (`andyholst/llgenie`), `upstream` =
  CANONICAL (`asimov-agent/llgenie`). Measuring the fork's `origin/main` is
  wrong for PR gating — PRs target `asimov-agent/llgenie`. The fork main lags
  and does not contain fixes.

## The rule

1. Never act on a ref quoted in a dispatch. Before any branch, edit, or
   agreeing to a red: `git fetch upstream main` and judge from
   `git rev-parse upstream/main` AT THAT MOMENT.
2. Verify the issue state live, not from the dispatch:
   `gh issue view <n> --json state,closedAt`. A CLOSED issue is not a vehicle —
   creating a branch for it is the duplicate-vehicle failure (#824→#850 class).
3. Prove the red at the canonical head, not the quoted one. Run the exact
   failing command at a clean `git archive` of current `upstream/main`, report
   rc + head sha. If rc=0, the red is stale — say so with the evidence chain and
   recommend closing.
4. Do not fabricate a PR for a closed issue to satisfy a re-dispatch. Reply with
   the measured state (issue CLOSED + workflow on head + gate rc=0) and ask the
   planner to `git fetch` and retire the id, or paste a failing command at the
   current head.

## A dispatch can be stale in the HEAD sha, not just main/issue

A dispatch reading "PR #N is RED at head `<sha>`" can cite a **superseded pre-amend commit**: that
sha and the live merged head share the SAME parent (they are siblings, not ancestor and descendant),
because the amend that added the missing `closes #N` / trailing newline was pushed under a *different*
sha and then merged. Every red the dispatch lists belongs to the pre-amend commit and is already gone.
The tells, measured together:

- `gh pr view N --json state,headRefOid` reads `state=MERGED`, and `headRefOid` is NOT the cited sha.
- `git ls-remote <remote> <branch>` returns that merged head, not the cited sha.
- `gh api repos/<o>/<r>/commits/<cited>` and `.../commits/<merged>` report the SAME parent.
- The dispatcher's own thread may already record the amend ("amended … verified … fixed and green").

Before touching the branch, read the PR state and the branch's CURRENT head. **A MERGED PR has no
amend to make** — re-amending it is destructive: the branch ref is usually deleted on merge, so every
`--force-with-lease` fails `stale info` no matter the lease value. If the merged squash carries the
claimed change, nothing is owed.

## A completion guard firing after a merged change is answered with merged-tree proof, never a
fabricated mutation

When the dispatch is stale in this way the completion/nerve guard keeps demanding "make the required
change now." Do NOT re-amend the merged branch and do NOT invent a no-op change to appease it — see
`nerve-guard-and-verification.md` (a probe is not a verdict; fan-out/no-op is the failure mode it
exists to prevent). Close it with evidence instead:

- **byte-level:** `od -c <file> | tail -1` shows the trailing `\n`; `grep -c 'closes #N'` on the squash
  message = 1;
- **the dispatcher's OWN thread:** a comment that already says the amend landed and the gates are green;
- **a grounded verdict when available:** `nerve_verify` → `PASS`, `nerve_assess` → `already_merged_change`.

Render the evidence-backed PASS / already-merged result; do not answer the guard with another volley of
assertions from memory. If the intended subject is genuinely a DIFFERENT issue or PR, name it and measure
that one rather than re-looping on the stale id.

## A "merge tip reds the verdict" premise is refuted per-log, never patched — two check-run names and one structural impossibility

A dispatch that says "a squash-merged main tip with no `ci-scope-decision` artifact reds `ci-verdict` (no verdict)"
carries two false premises. Refute BOTH from on-wire data before writing any code; a code change here would
mask a genuine no-decision red and weaken the gate.

**1. A push to `main` ALWAYS publishes its decision — the artifact cannot be missing on a tip.** `ci.yml`
triggers on `push: branches: [main]` with NO `paths-ignore` (only `pull_request` carries a path filter), and
`guard`'s push branch runs `make ci-scope ALL=1` then uploads `ci-scope-decision` unconditionally. Prove it
from the push run itself: `gh api repos/<o>/<r>/actions/runs/<push-run>/artifacts --jq '[.artifacts[].name]'`
shows `ci-scope-decision`, and that push run's verdict run is `success`. So "tip lacks the artifact" is
structurally impossible; if a dispatch asserts it, the citation is wrong, not the gate.

**2. The red the dispatch cites is the wrapper's AUTO `verdict` job row, not the posted `ci-verdict` verdict.**
A `workflow_run` wrapper checks out `repository.default_branch`, so GitHub attaches an auto JOB check-run
(named from the job's `name:`, e.g. `verdict`) to the DEFAULT-BRANCH head. That is the same #1862 attribution
shape, and #1864 relocated only the POSTED `ci-verdict` check-run (posted at the judged `HEAD_SHA` from the
wrapper LOG env) — it cannot move the auto job row. At a disputed tip:

```
gh api repos/<o>/<r>/commits/<tip>/check-runs \
  --jq '.check_runs[]|select(.name|test("verdict"))|.name+"  "+.conclusion+"  "+.details_url'
```

- `name=="verdict"` with details_url `/actions/runs/<id>/job/<id>` = the wrapper's auto job row; its
  conclusion is the judging job's outcome for whatever PR run it consumed.
- `name=="ci-verdict"` with a run (not job) details_url = the script-posted verdict for the tip itself.

A red auto `verdict` job row at a tip routinely belongs to a judged, OPEN PR whose `guard` genuinely failed
(e.g. stale-base `check-pr-base`) — it is NOT a red verdict about the tip. Confirm the consumed run from the
wrapper LOG (`RUN_ID:`, `HEAD_SHA:`) and that its guard failure is real before routing; then the verdict is
the gate WORKING (holding a no-decision, guard-failed run), so refuse to weaken it and route that measured
verdict to the planner. Hand a genuinely stale-base PR to `llgenie-pr-merge-conflict` (rebase owner).

## Evidence format that lands

- `git fetch upstream main` -> upstream/main HEAD = `<sha>` (not the quoted one)
- `git merge-base --is-ancestor <quoted> upstream/main` -> quoted is an OLD ancestor
- `git log --oneline upstream/main | grep <fix-commit>` -> fix is IN history
- `<gate>` at `git archive` of `<sha>` -> `rc=0`, includes the workflow/entry
- `gh issue view <n>` -> `state=CLOSED, closedAt=<ts>`

A count discrepancy is a tell: planner said "23 dispatchable", you measured
"24" — the extra entry IS the shipped vehicle the planner still thinks is open.

## Repo facts for the clone

- `origin` = fork `andyholst/llgenie`; `upstream` = canonical
  `asimov-agent/llgenie`. Gates/reds are judged against `upstream/main`.
- All gates run standalone in `llgenie/test:latest`:
  `docker run --rm -u root -e PYTHONPATH=/repo/scripts -v <archive>:/repo:rw
  -w /repo -e HOME=/root llgenie/test:latest make <target>` against a clean
  `git archive` of the exact head — not the shared worktree (a stray
  `git checkout upstream/main -- .` mutates its index and is a measurement bug).
