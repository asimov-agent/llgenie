# Lessons from closing kindred2025 (2026-11-07)

These are durable pitfalls observed while driving PR #2025 (issue #1400) through CI to green, and while landing other PRs this session. Keep them tight and reproducible.

## 1. A new test imports a scripts/ module as `from scripts import <name>`, never bare `import <name>`

Measured on PR #2025: `tests/test_check_main_ruleset.py:14` used `import check_main_ruleset as rs`, which added a NEW bare-import root and tripped the `check-import-roots` ratchet (issues #796/#1101) — recorded bare count 55→56, and `make ci-unit` redded naming exactly that `file:line`. The `sys.path.insert` / `sys.path.append` bootstrap lines still in sibling tests are REMAINING refactor debt the ratchet allows only to SHRINK, never to grow — copying them copies the forbidden shape. A new test imports a guard/script module as `from scripts import <name>` (the shape `test_check_pr_closing.py` uses), which the ratchet does not count.

Proof before pushing: `python3 scripts/check_import_roots.py ratchet` must exit 0 with counts unchanged (`{'sys-path': 35, 'bare': 55, 'syntax': 0}` as of 2026-11-07).

## 2. A stale `check-pr-base` red under a frequently-moving main is a base-drift race, not a code defect — re-base and RE-RUN on the final checkout

On #2025, `origin/main` advanced three times in one window (every other lane merged a PR), so each fresh run redded `check-pr-base`: the branch was not cut from the current `origin/main` tip (issue #845). The fix is to re-base onto the just-fetched tip and force-push (content-identical rebase of my own commits, allowed with `--force-with-lease --force-if-includes` on my own PR branch). The rebase/fix lane often gets there first and moves the branch under me — check `git fetch origin <branch>` + `git rev-parse origin/<branch>` BEFORE force-pushing; if the remote already carries byte-identical content, don't fight it, just re-run the failing job.

Key trap: **a run that instantiated while the branch moved checks out the OLD head**, so its `check-pr-base` finding can name commits that are no longer the HEAD — read `git log --oneline -1 <head>^` to confirm the parent equals the current `origin/main`. The decisive green is the run whose job checked out that settled head; re-run the pipeline run (`gh run rerun <id>`) once the branch has the right base.

## 3. A `ci-verdict` check that completes FAIL before the CI run's final SUCCESS is the fleet's judge-race (#2010/#1990), not the PR's defect

The ci-verdict judge reads the run mid-waveform — light jobs done, heavy jobs still queued — and can conclude FAIL before the run finishes green. Its own re-judge runs (workflow_run-triggered) clear it. On #2025 the verdict read FAIL at 17:03:36Z while the run concluded SUCCESS at 17:15:54Z. Do not chase or weaken it as a PR red; the authoritative signal is the pipeline run's own `conclusion` and its failing-jobs list.

## 4. Watch for the branch being moved by other lanes; report the board, do not tidy it

A branch I author is often re-based by the rebase/fix lane while I work. That is their lane, not mine to fight. Measure the remote head, adapt (content-identical), and let the fleet's auto-merge/fix-bot/rebase-bot land the PR once green+CLEAN. Never prune/destroy worktrees the kanban board owns (`make worktree-prune` correctly refuses an unattended bot, issue #794).
