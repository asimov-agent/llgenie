# issue-implementer — proposal

Issue: [#248](https://github.com/asimov-agent/llgenie/issues/248)

## Why

Nothing takes an issue and produces its first PR. The pieces around a bot exist —
a red PR gets repaired (#222), open PRs get kept rebased (#246 at one per day),
the agent container is specified (#238), the lifecycle is written down
(AGENTS.md, #5) — but the first implementation step is still done by hand. The
old host watch-loop is gone (#210), so this is the in-CI successor, implemented
as its own dispatcher plus the shared Hermes agent.

One hard constraint, from the issue: **at most 3 implementations a day**, one at
a time, each left as a reviewable PR that is **never merged**.

## What Changes

- **`scripts/issue_implementer.py`** — the deterministic dispatcher (no LLM,
  stdlib only, the unit-testable core):
  - `count` — how many PRs the bot already opened today
    (`gh search prs --repo <repo> --author <bot> --created ">=<today> 00:00Z"`).
  - `dispatch` — apply the cap first; pick exactly ONE issue (labeled
    `agent:implement` oldest-label first, else the oldest open `agent:ready`);
    claim it (a marker comment + a most-recent-event check so a second run
    cannot grab it); emit the branch `agent/issue-<n>-<slug>` and write
    `issue.md`. Never a batch, never a second claim.
  - `open-pr` — open a draft-free PR that links the issue (`closes #<n>`),
    states what was implemented and what was verified, and never merges.
- **`.github/workflows/issue-bot.yml`** — triggers: label `agent:implement`,
  daily `schedule`, `workflow_dispatch` with an issue number. Guard
  (owner/collaborator only), concurrency one-at-a-time, run the Hermes agent,
  push the feature branch, open the PR, report the outcome on the issue.
- **Makefile** — `issue-bot-dispatch`, `issue-bot-open-pr`, `implement-issue`
  (the Hermes call, the shared agent step), in `.PHONY` and the help text.
- **`tests/test_issue_implementer.py`** — real no-mock tests of the dispatch and
  cap logic with a `gh` on `PATH` that records argv exactly (the same shape
  `tests/test_engine_skill_gap.py` uses), asserting the count query, the claim
  comment, the branch slug and the PR open. The cap boundary is a named test:
  at 3, the 4th attempt exits 0 and opens/comments nothing.

## Out of scope

- #222 (repairing a red PR) and #246 (keeping PRs rebased) stay separate
  follow-ups — the implementer hands off to them, it does not grow its own loop.
- #238 (the Hermes container carrying the host's Nerve/JEV setup) is a
  dependency of the running layout; here the agent step is the same shared
  `make implement-issue` recipe, and #238 wires the token/plugin into the image.
- The cap is fixed at 3/day by the issue; it is data, not a knob in this change.
