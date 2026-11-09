# Keeping a verdict anchored to the sha it judged

A verdict is a judgment of ONE tree. The branch moves; the verdict does not follow it. These rules keep the board from reading a stale green/fail as current, and keep a check-run `success` from being credited as a gate pass it never ran.

## When the head moves mid-review, re-anchor — never re-report the old verdict as current

- Detect the move: `gh pr view <n> --json headRefOid` differs from the sha your verdict cites. The moment that happens your verdict is a valid judgment of *that tree only*; the branch at the new head is a **fresh** judgment needing its own concluded run.
- Post a correction record naming **both** shas — the sha judged and the new head — so a reader cannot mistake the old verdict for the current branch state. A verdict re-reported at a moved head is a ghost-frame (same failure class as a verdict on a PR that closed under you).
- A head can move more than once in one review cycle; re-check `headRefOid` immediately before any branch-green claim, not only once.
- Issue/acceptance state is **not** branch state: a ticked acceptance criterion, or a criterion verdict you already proved, persists across the head move. Only the *branch run* must be re-measured at the new head.

## Re-anchor vs re-judge: decide by the GRADED files, not the sha

Before paying for a fresh judgment at a moved head, ask what actually changed:

```bash
git fetch --force origin refs/pull/<n>/head:refs/remotes/live/pr<n> -q
git diff --stat <judged-sha> refs/remotes/live/pr<n>            # what the move touched
git diff --quiet <judged-sha> refs/remotes/live/pr<n> -- <graded-file> <graded-test>; echo rc=$?
```

- `rc=0` for **every graded file** (the workflow/source the acceptance criteria grade, plus its tests) means the evidence you paid for still describes the tree: **re-anchor** the `(proven: … head=…)` pins and the verdict's sha to the new head, post a short correction naming both shas, and do **not** re-run the acceptance matrix. A doc/spec/changelog commit landing on top is the common case.
- Any graded file differs → **re-judge**: a new verdict, from evidence measured at the new head.
- Name the graded files explicitly in the diff command. Without the pathspec, accumulated base history between an old pinned sha and a rebased head shows a huge diff and reads as "fully re-judge", which is the expensive wrong answer.
- Cheap independent confirmation at the new head before re-anchoring: re-run the one gate the fix was meant to turn green (e.g. `openspec validate --changes`, the named test file) and quote its totals. A re-anchor carried without that check is an assumption.

## Mid-flight is NO branch verdict

- If any check-run at the head is `in_progress`/`queued`/`pending`, the branch has **no verdict at this head**: say "no verdict exists at this head" and stop. Do not sum `success + pending` into green; a partial run is never green, and `cancelled` is its own bucket (no verdict), not red.
- Grade branch-green only on a **concluded** run at the current head. `gh run view` needs the workflow-run id / run number, not a check-run id.

## A `guard` check-run `success` is not proof the acceptance gate ran

- Multiple `guard` check-runs can share a head (push-scoped, PR-scoped, an owner/collaborator trigger guard). One `success` does not mean the gate executed.
- Before crediting an acceptance-gate pass, enumerate the job's steps: `gh api repos/<owner>/<repo>/actions/jobs/<job_id>` → `.steps[].name` and confirm the `check-pr-acceptance` / `make` step is present. A short-circuited guard may show only `checkout` + `trigger guard` + `Complete job` and never reach the gate.
- A gate `success` counts only when a run whose step list contains the gate step concludes `success`. Otherwise it is no evidence at all — not a soft pass.

## Reproducible gate evidence, not a claim

- A gate-clear is a command exit code, not prose: run the real gate against the LIVE linked issue body + PR body and record the findings count / `rc`. The gate reading a live ticked issue (all `- [x]`) and returning `0` findings is the evidence; a reviewer's assertion that it "should" clear is not.
- A comment does not auto-re-trigger CI. After a body/issue edit or a tick, the green chain needs a fresh run (owner push / re-trigger) at the new head — a re-trigger is not this lane's call, so report "needs a concluded run at head X", do not fabricate one.
