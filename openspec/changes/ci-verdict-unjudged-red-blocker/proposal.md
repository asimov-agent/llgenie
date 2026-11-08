# ci-verdict-unjudged-red-blocker

## Why

After #2231 merged, `scripts/ci_verdict.py::UNJUDGED_RED_CONCLUSIONS` became a STRICT SUBSET of
`auto_merge.RED_CONCLUSIONS` — #2231 exempted the whole `cancelled`/`neutral` conclusion class to stop a
green `main` head redding on its OWN rows and on auto-merge's `merge=cancelled` transient, but that
exemption was wider than the transient it needed. Measured at `main` `da83db09` (this change's branch
base):

```
BLOCKING_CONCLUSIONS       = ['cancelled', 'failure', 'neutral', 'startup_failure', 'timed_out']
UNJUDGED_RED_CONCLUSIONS   = ['failure', 'startup_failure', 'timed_out']
UNJUDGED == BLOCKING? False     UNJUDGED subset? True
'cancelled' in UNJUDGED? False  'cancelled' in auto_merge.RED? True
```

So a PR head whose ONLY unjudged row is a `cancelled`/`neutral` check-run from a non-`ci-verdict`
workflow (engine-build-pr-trigger, holds, ...) read `ci-verdict: success` (green) while
`scripts/auto_merge.py` refused the merge (`RED_CONCLUSIONS` names both, #1250 Finding B) — the exact
#2116 false-green `docs/BOTS.md` promises never occurs.

## What changes

1. `scripts/ci_verdict.py::UNJUDGED_RED_CONCLUSIONS` is pinned equal to `BLOCKING_CONCLUSIONS` (which is
   pinned equal to `auto_merge.RED_CONCLUSIONS` by test), so a `cancelled`/`neutral` unjudged row from a
   workflow the verdict did not judge is again a NAMED blocker.
2. `unjudged_reds` exempts a transient per WORKFLOW FILE (`TRANSIENT_FILES = {auto-merge.yml}`), not per
   conclusion class: only auto-merge's OWN `merge=cancelled`/`neutral` rows (a `main`-push sweep that
   was superseded or had nothing new) and the verdict's OWN rows (`OUR_WORKFLOW_FILE`) are skipped. A
   like conclusion from ANY other workflow still blocks and is named.
3. `tests/test_ci_verdict.py::test_the_blocking_conclusions_are_the_merger_s_rule` now also asserts
   `UNJUDGED_RED_CONCLUSIONS == auto_merge.RED_CONCLUSIONS` — the pin #2231 would not have shipped.

## Change-first

Issue #2237 is the surviving tracker. `#2231`'s fix (own-surface rows excluded by FILE, title names the
effective verdict) is preserved, not rolled back; only the over-broad conclusion-class exemption is
narrowed to auto-merge's own file. `auto_merge.RED_CONCLUSIONS` is unchanged (the merger's #1386 rule is
out of scope). Branches: `fix/2237-unjudged-red-subset`.
