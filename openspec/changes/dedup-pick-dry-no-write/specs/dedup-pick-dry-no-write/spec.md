# Spec: `issue-dedup-pick DRY=1` previews the pair without writing dedup-in.md

## ADDED Requirements

### Requirement: `pick` honours `--dry` — the pair is printed, nothing is written

`scripts/issue_dedup.py`'s `pick` takes a `dry` flag and `main()` passes the parsed `--dry` into
it. When `dry=True` the command prints the full decision protocol (`action=`, `canonical=`,
`copy=`) and touches no file — `dedup-in.md` is neither created nor modified. When `dry` is
false (the default, the agent leg's input path) `dedup-in.md` is written exactly as before.

#### Scenario: a dry pick on a board with a similar pair writes nothing

Given a stub `gh` on PATH whose open board contains one similar pair
When `pick` runs with `dry=True`
Then stdout carries `action=pick`, `canonical=<older number>`, `copy=<newer number>`
And the log line reads `would write dedup-in.md`, not `wrote dedup-in.md`
And `dedup-in.md` does not exist in the working directory
And the returned decision (canonical/copy/score) is identical to the real pick's

- **Test:** `tests/test_issue_dedup.py::test_a_dry_pick_prints_the_pair_and_writes_nothing`

#### Scenario: the real pick still writes the pair file the agent leg reads

Given the same stub board
When `pick` runs with the default `dry=False`
Then `dedup-in.md` exists and contains both issue bodies with the older one as canonical

- **Test:** `tests/test_issue_dedup.py::test_pick_writes_the_pair_for_the_agent_leg` (existing)
