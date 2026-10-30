# 2026-10-30 — a `CHANGES.md` row must have its `docs/changes.d/` fragment and appear once (issue #1063)

The change index is a directory of one-row fragments (issue #934): a change adds
`docs/changes.d/<stem>.md`, and `make changes-index` renders `CHANGES.md` from **all** fragments.
Nothing enforced that every rendered row still had a fragment behind it, so two defects could merge
into the aggregate: a **hand-written row** with no fragment, and a **union-merge duplicate** — two
copies of the same row.

## Why a "must not touch CHANGES.md" rule was wrong

The obvious rule — "a change PR must not modify `CHANGES.md`" — would red the whole open board.
Measured while checking the forward-looking guarantee: **all six open PRs carried a `CHANGES.md`
diff** (#1065, #1049, #935, #932, #919, #885), every one legitimately, because each lane runs
`make changes-index` and the regen rewrites the file from all fragments. The conflict was never
caused by hand-edits; it is caused by every PR rewriting one shared file. A rule about *touching the
file* would therefore retro-red every open PR on its next `linux/unit` run — the exact outcome the
issue exists to prevent.

## The invariant actually wanted

> Every row in `CHANGES.md` must correspond to a fragment in `docs/changes.d/`. Currentness is not
> required.

Two conditions, both needed:

1. every row's note has `docs/changes.d/<stem>.md` — a change adds its fragment, never a hand-written
   aggregate row (a stale index still passes: currentness is not the contract);
2. no note appears in more than one row — a fragment is exactly one row, so a union-merge duplicate
   is refused. Condition 1 alone does **not** catch it: a duplicate row points at the same note that
   already has a fragment, so both copies satisfy condition 1. Measured: appending an exact duplicate
   of a real row left `check_docs` at rc=0, and `changes_index.check()` at `[]` — nothing caught it.

## Implementation

A `changes-index` subcommand in `scripts/check_pr_hygiene.py` (beside `agents-line`), wired into the
`check-pr-hygiene` recipe so it runs in both `ci-unit` and `issue-bot-gates`. It is a **tree
consistency** check: it reads `CHANGES.md` and `docs/changes.d/` on disk and reuses
`changes_index.ROW_RE` + `_stems()` (one parser, #934). No git diff, no `PR_BASE`, no base ref — so it
behaves identically in every path and passes a legitimate regen by construction. Forward-looking: no
cut-off sha is needed because nothing legitimate is caught.

## What was measured, not assumed

- `tests/test_pr_hygiene_changes_index.py` → 8 passed (real `CHANGES.md`/`docs/changes.d/` trees in
  `tmp_path`, behavioural — positive control, hand-added row, duplicate row, stale-index pass,
  fragment-presence-alone miss, missing-file tolerance, wiring).
- Existing `tests/test_pr_hygiene*.py` → 32 passed (no regression to the static checks).
- `make check-pr-hygiene` → rc=0 on clean main (`249 rows = 249 fragments`, the no-op case pinned).
- Real duplicate row through the gate → one finding naming the stem **and** its fragment path.

## Scope

In: the gate (both conditions), behavioural controls, wiring into `check-pr-hygiene`, docs. Out (per
the issue): stopping the regen habit (a separate instruction — a change PR adds its fragment only,
the publish step renders) and `.gitattributes merge=union`, which is safe only once this gate cannot
let a duplicate merge silently.
