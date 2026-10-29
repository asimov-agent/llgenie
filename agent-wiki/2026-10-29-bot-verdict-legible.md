# bot-verdict-legible — 2026-10-29

Issue: [#852](https://github.com/asimov-agent/llgenie/issues/852) · PR: this branch
(`fix/852-verdict-legible`).

## What changed

- `scripts/bot_verdict.py` (new) — the ONE producer and parser of a bot review verdict:
  `<!-- bot-verdict: head=<40-hex> verdict=<approve|changes> reviewer=<login> -->`.
  - `marker` / `parse` round-trip the shape; `verdict_for_head` returns the NEWEST trusted verdict
    whose marker names exactly the given head, so a stale one returns nothing.
  - Trust: the comment's author must be one of the repo's identities or a bot login, AND the
    `reviewer=` in the marker must equal that author — a stranger cannot borrow the bot's name.
  - `post` refuses a non-40-hex head (a prefix is not a head) and an unknown verdict, and dedupes per
    (head, verdict) so a re-run posts nothing. CLI: `post`, `show`.
- `scripts/auto_merge.py` — `decide()` reads the verdict from the SAME `gh pr view` snapshot as the
  head (`pr_state` now requests `comments`, i.e. `PR_VIEW_FIELDS`) and clears a
  `BLOCKED` + `REVIEW_REQUIRED` block only when the verdict's head equals the current `headRefOid`;
  a `changes` verdict at the head holds the PR even when the state is CLEAN. `run()` merges a
  verdict-cleared PR with `--admin` (`_merge_review_cleared`) and turns a refusal into a deferral with
  the reason on the PR — never a red run. `explain()` prints the verdict it read.
- `Makefile` — `bot-verdict` / `bot-verdict-read` (both `.PHONY`), each a thin wrapper over the script.
- `docs/BOTS.md` — new subsection under the merge gate: a bot review is a verdict comment, never an
  approval, and no second identity is needed.
- Tests: `tests/test_bot_verdict.py` (marker round-trip, head matching, newest-wins, author/impersonation
  trust, allowlist cannot drift from `auto_merge`, post dedupe, short-sha/unknown-verdict refusal);
  `tests/test_auto_merge.py` (stale-sha refused, current-sha accepted and merged with `--admin`,
  untrusted login refused, impersonated reviewer refused, `changes` holds).

## Verification

- `make test-unit` modules in `llgenie/test:latest`: 70 passed
  (`tests/test_bot_verdict.py tests/test_auto_merge.py tests/test_bot_pipeline_isolation.py`).
- Control 1: making `verdict_for_head` ignore the head reds BOTH
  `test_only_a_verdict_at_the_named_head_is_returned` and
  `test_a_stale_verdict_does_not_clear_the_review_block` — a stale verdict would merge unreviewed code.
- Control 2: replacing `on.workflow_run` in `auto-merge.yml` with `workflow_dispatch` reds
  `tests/test_bot_pipeline_isolation.py::test_auto_merge_fires_by_itself_when_a_pr_run_completes`
  (issue #874) — the guard that fails if the gate loses its automatic trigger still holds.

## Decisions

- The verdict names the head it reviewed, and the marker is a comment only: it cannot flip
  `reviewDecision`, so it cannot pretend to be an approval. The merge of a verdict-cleared PR is
  `--admin` because the block is the identity (this branch has no required check in its protection),
  and the refactor keeps that refusal a deferral.
- No second identity is introduced (issue #852's direction): the bot keeps pushing with the owner PAT.
- `fix/840-author-identity` touches the author-identity guard, not these files; this change does not
  edit that branch.
