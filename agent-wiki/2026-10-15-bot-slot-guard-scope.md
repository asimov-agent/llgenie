# 2026-10-15 — the bot-slot guard derives its scope (issue #301)

Work record for issue **#301** (PR: the branch `fix/bot-slot-collisions`).

## What was wrong

`#275` isolated the bots by giving each a unique cron slot, enforced by
`tests/test_bot_pipeline_isolation.py`. Its `BOT_WORKFLOWS` was a **hand-written tuple of six
filenames**, and three scheduled bots merged afterwards were never added to it:

| workflow | cron | merged by |
|---|---|---|
| `rebase-bot.yml` | `23 */6 * * *` | #246 |
| `issue-refiner.yml` | `43 * * * *` | #264 |
| `code-review-bot.yml` | `23 7 * * 1` | #269 |

Because the scope was a list, the guard could not fail for a bot it did not know — and it didn't.
`issue-bot` (`23 6 * * *`) and `rebase-bot` (`23 */6 * * *`) both started at **06:23 UTC daily**,
the exact failure `#271`/`#272` exist to prevent.

## Measured

```
$ python -m pytest tests/test_bot_pipeline_isolation.py -q          # 3 passed   (shipped guard)
$ python -m pytest tests/_ext_guard_tmp.py -q  # same file, 3 bots added
E   minute 23, weekday 1: owned by both rebase-bot.yml and code-review-bot.yml
E   minute 23, weekday 2: owned by both issue-bot.yml and rebase-bot.yml
E   ... weekdays 1-6 ...
FAILED tests/_ext_guard_tmp.py::test_no_workflow_shares_a_minute   # 1 failed, 2 passed
```

Rule 6c was then proved the other way round: with the crons reverted in place, the rewritten guard
fails (`1 failed, 3 passed`); with the fix applied it passes (`4 passed`).

## What changed

1. `BOT_WORKFLOWS` is derived — any workflow with a `schedule:` is a bot (9 today). A new scheduled
   bot is in scope with no edit here.
2. Reserved minutes are derived from the every-hour crons (`_runs_every_hour`), so a new hourly bot
   reserves its minute automatically.
3. A regression test pins the derivation: `BOT_WORKFLOWS` must equal what the filesystem yields.
4. `rebase-bot` `23 */6 * * *` -> `29 */6 * * *`; `code-review-bot` `23 7 * * 1` -> `31 7 * * 1`.

Minutes are now unique: `7, 17, 19, 23, 29, 31, 37, 41, 43, 53`.

## Lesson (durable)

A guard whose subject set is a **hand-maintained list** is not a guard: it cannot fail for anything
added after it was written, so it reports green while the condition it encodes gets worse. Derive
the scope from the artifact itself, and pin the derivation.

## Verification

`make lint`, `make test-unit`, `make check-docs`, `make openspec-validate
NAME=bot-slot-guard-derives-its-scope`, and the guard proven red on the pre-fix crons and green
after.
