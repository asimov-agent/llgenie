# Skip a stacked base in the auto-merge decision, and detect hand merges into one

## Why

A stacked PR — one whose base is another open PR rather than `main` — can be merged **instantly and
unreviewed** into that base by its own author (issue #963). Measured 08:19:55Z: `#958`
base=`feat/agent-profile-implementer-skill`, `gh pr merge 958 --auto --squash` → MERGED the same second,
because `ci.yml` gates `pull_request` on `main` so a non-`main` base produces **zero workflows** (#945/#950)
and the ruleset requires **no status checks** (#880). "Auto" had no gate at all.

The default-branch half of this is split: the required-check half is a ruleset change that only the owner
can make (tracked in #880), which is why this change does not touch it. What an implementer *can* land is
the code half: the merger must never arm/merge a PR whose base is not `main`, and a hand merge that lands
anyway must be detectable.

## What Changes

- **`scripts/auto_merge.py`** — `decide()` returns a deferral reason when `baseRefName != "main"`, so a
  stacked PR is never armed or merged by the merger and the run summary says exactly that. `baseRefName`
  joins `PR_VIEW_STATE_FIELDS` (it is already in gh's own `gh pr view --json` allowlist fixture).
- **`scripts/auto_merge.py`** — a new `stacked-merged` command lists the PRs merged into a non-`main` base
  and reports each with its author, head sha and the count of check-runs that ran at the head (expected 0).
- **`.github/workflows/auto-merge.yml`** — the scheduled recheck job also runs the stacked-base report
  (schedule-triggered only), so a hand merge into a non-`main` base is visible to the same sweep that owns
  the merge gate.
- **`docs/BOTS.md`** — one line states the rule: *arm only on a PR whose base is `main`; a stacked PR arms
  on retarget*.
- **`tests/test_auto_merge.py`** — the negative control: a test seeds a PR with a non-`main` base, arms it,
  and asserts the merger skipped it (never calls `pr merge`); plus the standalone detector report.

## Specifications

- `specs/auto-merge-skip-stacked-base/spec.md`

## Tasks

- [ ] OpenSpec change: `proposal.md`, `specs/auto-merge-skip-stacked-base/spec.md`, this checklist
- [ ] `scripts/auto_merge.py`: `decide()` skips `baseRefName != "main"`, `baseRefName` in
      `PR_VIEW_STATE_FIELDS`, and the run summary names the base as the reason
- [ ] `scripts/auto_merge.py`: `stacked-merged` command reports author + head sha + check-runs count
- [ ] `.github/workflows/auto-merge.yml`: the scheduled recheck runs the stacked-base report
- [ ] `tests/test_auto_merge.py`: the negative control (non-main base armed → merger skips) + detector test
- [ ] `docs/BOTS.md` one-line rule + README/Makefile help + `agent-wiki` note + `docs/changes.d` fragment
- [ ] Verified: targeted pytest green, `make lint`, `make check-wiring`, `make check-docs`,
      `make check-workflows`, `make openspec-validate NAME=auto-merge-skip-stacked-base`,
      loop gate (`make test-unit`)
