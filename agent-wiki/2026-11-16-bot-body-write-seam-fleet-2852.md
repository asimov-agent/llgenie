# Bot body-write seam extended to the whole fleet (issue #2852)

## What was done

Extended #2131's guarded PR-body write seam (`make bot-body-write`) to every lane measured to replace a
PR body on `origin/main` `fbf613d83`:

- `engine-bump.yml`, `registry-sync.yml`, `semgrep-rules-refresh.yml` — the OPEN-PR branch now keeps a
  title-only `gh pr edit` and routes the stamped body through `make bot-body-write PR=$(gh pr view …
  number) NEW=/tmp/pr-body.md`. `gh pr create --body-file` (opening a new PR) is not a replacement and
  stays as is.
- Measured classification (grep over all `.github/workflows/*.yml` + `scripts/` + `mk/`): no other lane
  writes a PR body. `issue-bot.yml`/`issue-refiner.yml` post only `gh issue comment` (append-only);
  `rebase-bot.yml`, `engine-bump-rebase.yml`, `auto-merge.yml` carry no body write — the issue's "rebase-bot
  and auto-approve" wording is replaced by this measured set in the issue body.

## Verification

- `tests/test_bot_body_write_fleet.py` (3 tests): fleet scan finds zero hand-rolled body replacements and
  pins the wired-caller set to {fix-bot, engine-bump, registry-sync, semgrep-rules-refresh}; append-only /
  body-write-free lanes pinned; a planted `gh pr edit --body-file` in a fake workflow text is caught and
  the same text cleared by inserting the seam call.
- `make check-workflows` rc=0 (actionlint clean on the three edited YAML files), `make check-wiring` rc=0.
- OpenSpec `bot-body-write-seam-fleet` validates; the spec adds the fleet-wiring requirement to the
  existing `bot-body-write-guard` capability.

## Behaviour note

A weekly re-bump whose fresh template would drop a heading or proven tick the live body carries is now
SKIPPED with a PR comment naming the section (the seam's designed outcome) instead of silently rewriting
the body — reviewers see the refusal on the PR rather than discovering lost evidence via a ci-scope red.

