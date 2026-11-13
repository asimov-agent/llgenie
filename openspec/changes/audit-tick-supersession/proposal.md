# Change: audit-tick-supersession

<!-- FOLLOWUP-2288 (issue #2631) -->

## Why

Issue #2288 / PR #2630 made NEW acceptance ticks honest, and the append-only
`<!-- AUDIT-2288 -->` addenda recorded that 178 already-ticked criteria across
46 closed issues cite runs whose live conclusion is not green (41 runs: 40
failure/cancelled, 1 unreadable 404). The addenda are scars, not resolutions:
issue #2631 exists to resolve them. The repo tool re-measured the corpus live
on 2026-11-13: 1308 closed issues, 311 ticked criteria citing `run=<id>`,
172 unsuperseded stale criteria across 44 issues, 40 cited runs (39 with a
red conclusion at 39 distinct heads, 1 unreadable 404 `43073777356`).
`head_green` shows the 39 distinct red heads carry ZERO completed/success
runs of the cited workflows (3 heads have no green run at all, 36 carry green
runs only for unrelated workflows — a same-head green of another workflow
never re-proves the tick), so a same-head green re-tick cannot be minted
honestly for those criteria; the honest resolutions are a green re-tick where
a live green run proves the criterion today, and an explicit supersession note
everywhere else.

## What Changes

- Add `scripts/audit_acceptance_ticks.py`: the corrected audit as a repo tool.
  `audit` pages all closed issues (GraphQL), collects ticked criteria citing
  `run=<id>`, looks each run's live conclusion + head, classifies stale/green,
  and EXCLUDES criteria covered by a machine-readable `<!-- SUPERSEDE-2288 -->`
  supersession note on the issue. Reports 0 only when no unsuperseded stale
  tick remains, and records the counting method in its own header line.
- Add `render_supersede_note` (one renderer, never hand-built): deterministic
  supersession comment body keyed to the same cited run ids as the issue's
  AUDIT-2288 addendum.
- Add `post` subcommand: append-only, idempotent posting of supersession notes
  (marker-checked, ticks stay as written).
- Re-tick none: measured 2026-11-13, the 39 distinct red heads carry zero
  completed/success runs of the cited workflows, and the criteria
  sentence-level-cite historical run ids that no fresh run can honestly
  replace (e.g. #2472's cited run is 404 and its cron has since been re-shaped
  to `17 6 15 * *`). Every honest resolution is therefore a supersession note;
  zero new ticks are minted.
- Make targets: `audit-ticks`, `audit-ticks-notes`, `audit-ticks-post`.
- Register the script in `scripts/package-layers.json`; wire tests
  (`tests/test_audit_acceptance_ticks.py`, fake-gh fixtures).

## Impact

- Affected specs: `acceptance-evidence` (MODIFIED: supersession exclusion in
  the audit denominator; supersession note as a first-class artifact).
- Affected code: `scripts/audit_acceptance_ticks.py` (new), Makefile,
  `scripts/package-layers.json`, docs pairing.
- GitHub wire: 46 supersession comments posted, zero issue-body re-ticks.
