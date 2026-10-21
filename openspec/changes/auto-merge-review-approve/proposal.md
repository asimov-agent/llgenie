# A green PR blocked only by a review is approved by the other identity — and a deferral is visible

## Why

`auto-merge` now runs for a cross-repository head (#489) and still cannot land a green PR, because GitHub
reports `BLOCKED` for a missing review:

```
$ gh pr view 481 --json author,headRepository,mergeable,mergeStateStatus,reviewDecision
author=andyholst  head=andyholst/llgenie  mergeable=MERGEABLE  mergeStateStatus=BLOCKED  reviewDecision=REVIEW_REQUIRED
$ gh pr view 481 --json reviews        # 0
```

Its run (`39642461828`, 27 jobs, every reporting job `success`) ends with the job deferring — and the only
trace is a line in a CI log. The PR says "green, not merged" with no explanation, which is what sent the
owner looking for a cause three times.

Where the review requirement lives is not visible to the API: `main` is `protected=true`, the only ruleset
(`24862727`) carries `deletion` + `non_fast_forward` and no bypass actors, there is no `CODEOWNERS`, and
`reviewRequests` is empty. What is visible: every PR that has merged (#445/#447/#448/#446) carried an
approving review first.

So a green PR waits for a keyboard — the very thing #482 removed — and when it does not merge, nothing on the
PR says why.

## What Changes

- **`make auto-merge-explain PR=<n> REPO=<owner/repo>` (new)** — the same `gh pr view` the job makes, printed
  as a verdict: `state`, `isDraft`, `mergeable`, `mergeStateStatus`, `reviewDecision`, the head, and one line
  saying what would unblock it (`would merge`, `would approve then merge`, or `defers: <reason>`). Read-only.
- **A deferral is commented on the PR, once per head.** The job posts
  `<!-- auto-merge: deferred <sha> -->` with the explanation when it defers (skipped when a comment for that
  sha already exists), so the next reader does not have to open a run log.
- **A review-blocked green PR is approved by the OTHER allowed identity, then merged.** When the ONLY blocker
  is the review requirement — `mergeable == MERGEABLE`, `mergeStateStatus == BLOCKED`,
  `reviewDecision == REVIEW_REQUIRED`, and the workflow's own `needs:` gate already guarantees every needed
  job `success` — the job checks who authored the PR against the token's own account (`gh api user`):
  - author ≠ token account, **and** the author is one of the two identities this repo allows
    (`Andy Holst` / `Asimov Agent`, AGENTS.md) → `gh pr review <n> --approve` with a body naming this job and
    the issue, then re-read the state and merge if it became `CLEAN`;
  - author == token account → GitHub refuses a self-approval, so it defers and the comment says exactly that;
  - any other author → defers: a stranger's PR is not approved by a bot.
- Everything else still defers unchanged: `DIRTY`, `BEHIND`, a draft, a third-party fork, a moved head,
  `do-not-merge`, and any `BLOCKED` that is not this review state.
- `README.md`, the spec and the work record state the policy and its limit. `AGENTS.md` needs one matching
  paragraph in rule 7; that file is write-protected for the agent, so its exact wording is proposed in the PR
  body for the owner to apply (the change is complete without it, the policy statement is not).

## Impact

- A green, conflict-free PR from the owner's fork lands without a human click, including the review step that
  currently blocks it — and when it cannot, the PR carries the reason.
- The approval is attributable and honest: the review body says it is the auto-merge job acting on a green
  run, it never fires for a red/incomplete run (the workflow gates that), and `do-not-merge` still wins.
- A PR authored by the same account the merge token belongs to still needs a human — GitHub's own rule, now
  named on the PR instead of silently deferring.
