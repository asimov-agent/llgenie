# Splitting the gates domain out of the 2,083-line Makefile (issue #2457)

## What changed

The top `Makefile` carried the whole build — 2,083 lines across every domain. `#2457`
(decomposed from the closed big-bang split PR #2454 per issue #800) moves ONLY the host / gate /
coverage / lint domain — `bash-check`, `check-host-space`, `reclaim-tmp-worktrees`, every
`check-*`, `*-report`, the `git-identity-*`, `openspec-*`, `lint`, `lint-fix` and the rest — out of
the top file into a new `mk/gates.mk`, byte-for-byte. The top `Makefile` keeps the shared
environment, `.PHONY`, `version`/`help` and adds `include mk/gates.mk`.

Measured parity at the PR head:

- `make -qp` target list identical before/after (377 targets, `diff` empty).
- `make help` byte-identical.
- `make check-wiring` output byte-identical before/after (371 make targets, CI calls 130).
- `make check-docs` output byte-identical before/after (337 user-facing targets documented).

Every Makefile-text reader now resolves `include mk/*.mk` before reading targets, or it would go
blind the moment a target moved behind the include. Updated readers: `scripts/check_wiring.py`
(`_makefile_list`), `scripts/check_docs.py` and `scripts/architecture_bot.py` (`_makefile_text`),
`scripts/check_dispatch_forms.py` (`makefile_targets`), `scripts/issue_bot_gates.py`
(`_makefile_text` — its `FAST_GATES` are all gate-domain targets), and `tests/conftest.py`
(`makefiles_text`). The tests that sliced a gate target out of the top Makefile now read through the
resolver instead.

## Verification

- target/surface parity: `make -qp` + `make help` identical (commands above).
- gate parity: `make check-wiring` / `make check-docs` byte-identical before/after the move.
- the affected unit modules are green in the test container (the Makefile-slicing assertions that
  pinned the old single-file layout were updated to the include-resolving reader).

## Issue / PR

Implements issue #2457, closes #2457; parent decomposition issue #800.
