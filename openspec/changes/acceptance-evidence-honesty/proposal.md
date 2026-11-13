# Proposal: acceptance-evidence-honesty

## Why

A ticked acceptance criterion is only as honest as the evidence behind it, and today both
seams let dishonest evidence through:

- The gate's provability check (`scripts/check_pr_acceptance.py::_is_provable_tick`) accepts
  ANY `run=<digits>` token without consulting the run's actual conclusion. A tick citing a
  run that concluded `failure`/`cancelled` — or a run pinned at a head that is not the PR's
  current head — passes the run-id branch untouched (issue #2288 measured 11 such ticks on
  closed issues, citing 4 red run ids).
- The write-back seam (`scripts/acceptance_writeback.py::tick_acceptance`) stamps any
  `--verdict-ref` string verbatim: it never validates that the verdict names a run that
  concluded success, nor that it names the PR's live head sha at measurement time.

Both classes make a tick look proven when nothing green proves it — the exact #745 honesty
contract, defeated at the write and read ends.

Issue: #2288.

## What Changes

- `scripts/check_pr_acceptance.py`: for every TICKED criterion whose `(proven: …)` cites a
  `run=<id>`, the gate looks the run up LIVE (`gh api …/actions/runs/<id>`, through the
  existing `--gh` seam) and:
  - conclusion `failure`/`cancelled` → blocking finding
    `tick-cites-red-run` (names the run and its conclusion);
  - conclusion absent (queued/in_progress) → non-red `proven-awaiting-writer` entry, never
    a green pass;
  - the run's `head_sha` differing from the revision the criterion belongs to (PR head /
    squash-parent) is reported INSIDE the finding as stale-head context, and a cited
    `head <sha>` token that matches neither the live head nor the run's head is a blocking
    `tick-stale-head-unflagged` finding.
- `scripts/acceptance_writeback.py`: `tick_acceptance` rejects a `--verdict-ref` that (a)
  names a `run=<id>` whose live conclusion is not `success` (queried via the `--gh` seam in
  the `writeback` command; `apply`/`check` stay offline and lock the grammar), or (b) names
  no head sha (`<7–40 hex>`) at all. A rejected verdict raises `BodyError` — the tick never
  gets written.
- `scripts/review_finalize.py` (the ONLY live caller of the seam, invoked by the reviewer
  leg per `verdict-finalization.md`) validates its `--verdict-ref` through the same rule
  before it calls `tick_acceptance`, so the finalize path cannot stamp an ungreen reference.

## Impact

- Affected specs: `acceptance-tick-provability` (gate side), `acceptance-writeback` (seam side).
- Affected code: `scripts/check_pr_acceptance.py`, `scripts/acceptance_writeback.py`,
  `scripts/review_finalize.py`, and the tests of all three.
- Affected gates: `check-pr-acceptance` (scope job); the seam itself
  (`acceptance_writeback writeback/apply/check`, `review_finalize finalize` — reviewer-leg
  commands, no CI trigger per docs/BOTS.md).
- Closed issues are NEVER rewritten by this change (AGENTS: closed-issue bodies stay
  append-only): the 11 stale ticks named in #2288 are handled by append-only audit addenda
  filed from the sweep — the gate still treats them honestly if a reopen ever re-reads them.
