# bot-review-verdict — proposal

Issue: [#852](https://github.com/asimov-agent/llgenie/issues/852) — *fleet: a bot pushing as the owner can
never approve — make a verdict legible instead of unreachable*

## Why

Every bot in this repository pushes with the owner's PAT, so the PR author **is** the owner account and
GitHub refuses the approval itself: `gh pr review --approve` answers `Can not approve your own pull
request`, and `reviewDecision` can never leave `REVIEW_REQUIRED` on a bot-authored PR. Measured 2026-10-29
at `main@5a367d42`: 27 open PRs, 26 reading `BLOCKED`/`REVIEW_REQUIRED`.

`scripts/auto_merge.py::decide()` gates on `mergeStateStatus`, so a complete reviewer verdict that lives as
prose in the PR thread is invisible to the merge decision. The block is the *identity*, not a gate: the
branch's classic protection declares required status checks but no review rule that a bot can satisfy, and
`gh api repos/asimov-agent/llgenie/rulesets` shows only `deletion` and `non_fast_forward`.

The alternative — a second owner PAT used as the approver — moves the problem (the author is whoever
pushed) and puts an owner credential in the review path.

## What Changes

- **`scripts/bot_verdict.py`** (new) is the ONE producer and parser of a bot review verdict, a comment
  marker that names the head it reviewed:

  ```text
  <!-- bot-verdict: head=<40-hex sha> verdict=approve reviewer=<login> -->
  ```

  It refuses a short sha (a prefix is not a head) and an unknown verdict, dedupes per `(head, verdict)`,
  and trusts a marker only when the comment's author is one of the repository's identities or a bot login
  **and** the `reviewer=` in the marker equals that author (no impersonation by a stranger).
- **`scripts/auto_merge.py`** reads that marker from the SAME `gh pr view` snapshot as the head
  (`pr_state` now asks for `comments`), and `decide()` clears a `BLOCKED` + `REVIEW_REQUIRED` block only
  when the verdict's head equals the PR's CURRENT `headRefOid`. A stale verdict counts for nothing. A
  `changes` verdict at the current head holds the PR even when the merge state is otherwise clean. The
  merge of a verdict-cleared PR is the `--admin` path (the block is the identity, not a check), and a
  refusal is a deferral with the reason on the PR — never a red run.
- **`docs/BOTS.md`** states the rule: a bot review is a verdict comment, never an approval, and no second
  identity is needed.
- **`Makefile`**: `make bot-verdict` / `make bot-verdict-read` (one code path: the script).
- **Tests**: one per property — a stale-sha verdict is refused, a current-sha verdict is accepted and
  merged, an untrusted or impersonating author does not count, a `changes` verdict holds, and the
  workflow guard that fails if `auto-merge.yml` loses its automatic trigger still passes
  (`tests/test_bot_pipeline_isolation.py::test_auto_merge_fires_by_itself_when_a_pr_run_completes`).

## Not covered

- `fix/840-author-identity` (#840) touches the commit-author identity guard; this change does not edit
  that branch and does not touch its files (`scripts/check_pr_authors.py`). If both land, they are
  independent.
- Posting a verdict automatically from a review lane is a follow-up: this change ships the producer, the
  consumer and the rule. No lane posts a verdict yet.
