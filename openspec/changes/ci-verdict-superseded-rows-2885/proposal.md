# Change: ci-verdict-superseded-rows-2885

## Why

`scripts/ci_verdict.py`'s UNJUDGED RED scan and `scripts/auto_merge.py`'s `failing_checks` treat EVERY red check-run row ever posted at a head as blocking, even when a newer run of the same workflow at the same head concluded green with the same job name. Measured 2026-11-17 at PR #2882 head `585b03dd740c121564190f86987f9bac89f4e796`: three `scope` rows coexist (two success, one failure from the since-cleared run 44046649110); the local verdict replay of the fully-green CI run 44053645969 still posts `conclusion=failure`, naming only the dead row, and `auto_merge` refuses the head (#1386 "any red at the head"). GitHub's `filter=latest` does not collapse these rows (measured: it returns all three) because separate workflow RUNS mint separate check-run ids; only re-runs of the same run id collapse. A head that was red once therefore locks until the head sha is force-moved — measured cost: three forced head moves on 2026-11-17 (#2882, #2878, #2884). Issue #2885.

## What Changes

- NEW shared module `scripts/head_check_rows.py`: collapse a head's check-run rows to the newest CONCLUDED row per (job name, workflow file); every strictly-older concluded row of that group is superseded and never blocks. Rows that never concluded (queued/in_progress) neither supersede nor are superseded; rows whose workflow file cannot be resolved are never superseded.
- `scripts/ci_verdict.py::unjudged_reds` reports only unjudged reds that are their group's newest concluded row; a superseded red is named as an informational `SUPERSEDED RED` line, never a block.
- `scripts/auto_merge.py::failing_checks` blocks only on the newest concluded red per (job name, workflow file); superseded reds are printed as a note, not a deferral reason.
- Pinned contracts stay intact: `UNJUDGED_RED_CONCLUSIONS == auto_merge.RED_CONCLUSIONS`, the `TRANSIENT_FILES`/`TRANSIENT_CONCLUSIONS` exemption, the judged-roster exclusion, and #1551's unfinished-run deferral.

## Impact

- Affected specs: `check-row-supersede` (ADDED)
- Affected code: `scripts/head_check_rows.py` (new), `scripts/ci_verdict.py`, `scripts/auto_merge.py`, `scripts/package-layers.json`, `tests/test_ci_verdict.py`, `tests/test_auto_merge.py`
- Affected docs: `.github/workflows/ci-verdict.yml` header comment, `CHANGES.md` fragment via `changes.d/`, `agent-wiki/` entry
