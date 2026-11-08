# Verify each lane's behavioural contract — a SOUL can match the tree and lose its duty (issue #2260)

## Why

`make sync-agent-profile CHECK=1` verifies a lane's files match the tree, but a
lane can match the tree byte-for-byte and still not *do its job*: its SOUL may
lack the `BOT <lane> · working on #<id> · …` report line, the never-merge rule,
bookending, or the lane's own duty. File-drift says *the file is there*; nothing
says *the lane is committed to the behaviour that makes it a lane*. A lane whose
SOUL never commits to a reporting channel behaves as if it works alone and cannot
be audited for cross-lane behaviour. And when a lane does flout its contract, the
current ownership is backwards: the lane would be told to fix its own SOUL —
the self-audit loop that ends with a lane privately editing its own rules to pass.

## The change

1. **`scripts/verify_lane_contract.py`** — per live lane SOUL (built from
   `pathlib.Path.home()/.hermes/profiles/<lane>/`, never the tree and never a
   hardcoded account path) it asserts six contract elements non-empty and
   unambiguous: the `working on #` report line, the never-merge rule, bookending,
   the issue+PR-under-`agents/<profile>/` versioning rule, the lane's own duty
   (one regex per lane in the `DUTY` map), and a communication commitment
   (`message_agent` / report to / recall) — plus ≥1 materialised non-`.archive`
   skill `SKILL.md` under `skills/` to load. It prints `N/13 lanes pass the
   behavioural contract` and, on a FAIL, names the lane and the missing element.
2. **Wired as orchestrator tick step 9** (VERIFY LANE RESPONSIBILITY) in the
   versioned procedure `agents/llgenie-planner/prompts/llgenie-orchestrator-tick.md`,
   after dispatch, requiring the quoted pass-count as evidence. A regression is
   the PLANNER's fix, not the lane's own repair: the planner files a detailed
   issue under `agents/<lane>/` and the lane lands the SOUL correction by PR.
3. **Hermetic tests** `tests/test_verify_lane_contract.py` — runs the real script
   against scratch fixtures via `--root`: a complete contract PASSES; an empty
   SOUL FAILs; a SOUL missing the report line FAILs report-line; a SOUL reporting
   to nobody FAILs communicate; an `.archive`-only `skills/` FAILs
   skills-materialised; removing a lane's own-duty marker reds that lane.

## Tasks

Behaviour changes are ticked in tasks.md. The diff lands as one ready-for-review
PR with `closes #2260`.
