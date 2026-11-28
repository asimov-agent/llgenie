# Audit-dispatch counts must carry their command (issue #3120)

Two consecutive per-pass docs-audit dispatches quoted counts that did not match the sha they named. At `ba000e934d3287d7a1e56411ff6f244786b1fc08` the dispatch said `980 fragments / 980 notes / 980 rows … current`; `python3 scripts/changes_index.py report` at that sha measured 997 fragments, 997 notes, 997 parsed rows and **996 committed vs 997 rendered — 1 row behind**. At `f9f32f0ca073193d827d317f203f8fc49fed16d4` the dispatch again quoted 980/current; the same command measured 999/999/999, current. The board records had to contradict the dispatch every time (`#2371`, comments `7229910090`, `7230864851`, `7231149537`).

## Decision

Fleet rule 15 already required a count to name its sha; the prose did not require the command, so a cached number could be quoted as if the named command had just produced it. `agent-wiki/2026-10-29-rule15-sha-baseline.md` now requires the exact command beside every count, forbids quoting a number that command did not produce at that sha in that moment, and labels cached numbers from earlier shas as stale (or re-measures them). Its `docs/changes.d/` row says the same.

## Why it matters

A count with a sha but no command still hides which predicate produced it. The auditing lane cannot treat a dispatch's numbers as a measurement; each pass re-measures and contradicts the dispatch, and a future pass that skips re-measurement would publish a false clean audit.

## Verified

- `git show origin/main:agent-wiki/2026-10-29-rule15-sha-baseline.md` and `git grep` at freshly fetched main `b93e0c8ca6f6732101a667cca24c30c49fd44453` were the source of the quoted prose — the dirty primary tree was not used.
- The two measurements above came from `python3 scripts/changes_index.py report` at each sha in a clean detached worktree; the current tip `d5858e8615cb780858bef441cb48d4ae46ab9436` measured `make -s check-docs` rc=0 and 999/999 current.
- No script, test, workflow or gate was changed; the correction is prose under `agent-wiki/` and `docs/changes.d/`, with the generated `CHANGES.md` row.

## PR

Closes #3120. One docs-only PR, ready for review; nothing merged or armed by this lane.
