# Tasks

## The dry flag through the pick path

- [x] 1.1 `pick(gh, repo, dry=False)`: with `dry=True`, print the `action=`/`canonical=`/`copy=` protocol and skip the `dedup-in.md` write (issue #564).
- [x] 1.2 `main()` passes `args.dry` to `pick` (flag already parsed; `bots.mk` already appends `--dry` on `DRY=1`).

## Proving it

- [x] 2.1 New test `test_a_dry_pick_prints_the_pair_and_writes_nothing`: dry pick prints the pair protocol, returns the decision, and no `dedup-in.md` appears (RED on today's script, GREEN after 1.1/1.2).
- [x] 2.2 `pytest tests/test_issue_dedup.py` fully green (the existing real-pick test keeps asserting the write).

## Ship

- [x] 3.1 changes.d fragment + agent-wiki entry naming issue #564; `make lane-preflight` green; commit + push + PR mirroring the issue.
