# Why a green PR is not auto-merged/auto-approved (owner question shape)

Owner asks "why is PR <n> not auto merged and auto approved?" — often with a pasted auto-merge
refusal naming a head sha. Answer with three separate measurements; never from the refusal text alone.

## 1. The live verdict at the CURRENT head (the pasted reason is usually stale)

```bash
export GH_TOKEN=$(gh auth token)     # auto-merge-explain needs it in env; empty token = silent no-op
make auto-merge-explain PR=<n> REPO=<owner>/<repo>
```

This prints the PR's `mergeable`/`mergeStateStatus`/`reviewDecision`/`headRefOid` plus the decision:
`would approve …, then merge` vs. the named blocker. **Read `headRefOid` first** — a refusal/rebase
cycle moves the head, so a refusal quoting an older sha (red guard, missing acceptance tick) describes
a head that no longer exists. Check `gh pr view <n> --json headRefOid` against the sha in the paste
before repeating any reason: relaying a stale head verdict is a wrong answer delivered confidently.

## 2. Is the head actually green? (read the PR-trigger run, not the refusal)

```bash
gh api repos/<o>/<r>/actions/runs?head_sha=<head> --jq '.workflow_runs[]|{name,event,status,conclusion}'
gh api repos/<o>/<r>/actions/runs/<ci-run-id>/jobs --jq '.jobs[]|"\(.name)\t\(.conclusion)"'
```

A red the PR outgrew is not the current blocker; a still-red `guard`/`check-pr-acceptance` is.

## 3. Did the merger ever RUN at this head? (the usual real answer)

```bash
gh api 'repos/<o>/<r>/actions/workflows/auto-merge.yml/runs?head_sha=<full-40-char-head>&per_page=20' \
  --jq '[.workflow_runs[]|{id,created_at,s:.status,c:(.conclusion//"?")}]'
```

Empty = the merge job has never evaluated this head, whatever the explain says. Only two mechanisms
explain it:

- **Concurrency saturation.** The merge job runs in one `auto-merge-success` group with
  `cancel-in-progress: true`. A PR CI completion that lands during a burst of main-tip completions
  (merges landing back-to-back) is cancelled/coalesced before a run row exists at the PR head. Compare
  the PR CI run's `updated_at` (its completion time) against the auto-merge runs around that minute:
  if every run in the window carries a *main-tip* head sha, this is the cause. Note that a CI run's
  `created_at` is when it was queued, not when it completed — a long matrix makes the two hours apart.
- **Recheck marker dedupe, post-#1914.** The recheck job evaluates a PR once per current head
  (`<!-- auto-merge: deferred <sha> -->`, one marker per head) — dedupe, never a skip of green. A
  head that moved after its last deferral marker made that marker STALE-BY-MOVE, and `recheck` now
  sweeps it too: `scripts/auto_merge.py::has_any_deferral_marker` + `recheck` re-evaluate a PR whose
  CURRENT head is green even when the *deferred* sha is an older one
  (proven: tests/test_auto_merge.py::test_a_stale_marker_green_head_is_retried_and_merged). So "the
  merger never ran at this head" is now a *scheduling/queue* cause, never a dropped doc: if the head
  is green and the marker names an older sha, the next recheck cron evaluates it. A RED head is still
  not retried (#1386) — recheck evaluates green heads only.

Confirm the marker state: `gh api repos/<o>/<r>/issues/<n>/comments` and take the sha out of the last
`auto-merge: deferred` comment; if it is not the current `headRefOid`, verify the head is green and
let the next recheck cron sweep it (or run `make auto-merge-recheck REPO=<o>/<r>` manually).

## Fix routing

This is a **mechanism** gap, not a review gap and not a PR defect. File a six-section issue against the
CI-pipelines lane (`agent:implement` + `agent:refined` + the CI label) with the candidate fix named in
the Technical section (e.g. on finding a green head whose deferral marker is stale-by-move, post the
current-head marker so the next cron evaluates it — dedupe still prevents spam). Never hand-merge to
make the symptom go away, and never re-run a judged CI run just to fire the `workflow_run` trigger.

## What NOT to report

- "It needs a human approval" when the merge job's own approve-then-merge path (approve with the
  workflow `github.token`, merge with the owner PAT) would clear a required review — the mechanism, not
  a human, is the defaulter. Bot-authored PRs cannot self-approve; that is why the two-identity design
  exists.
- A red guard at an older head as the *current* reason.
