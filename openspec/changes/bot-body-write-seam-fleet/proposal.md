# Route every bot body-replacement lane through the guarded body-write seam (issue #2852)

## Why

Issue #2131 landed `make bot-body-write` — the seam that reads a PR's LIVE body and refuses a write that
drops a heading or a ticked `(proven: …)` item — but wired it into `fix-bot.yml` only. The defect class is
"any bot writes a body it derived from stale state": measured on `origin/main` `fbf613d83`, three more
lanes still hand-roll a body REPLACEMENT with `gh pr edit ... --body-file` on an already-open PR —
`engine-bump.yml` (line 266), `registry-sync.yml` (line 223) and `semgrep-rules-refresh.yml` (line 167)
each re-compose their template body on every re-run and overwrite whatever the live body carries. The same
scan proves `rebase-bot.yml`, `engine-bump-rebase.yml` and `auto-merge.yml` never write a PR body, and
`issue-bot.yml` / `issue-refiner.yml` only post `gh issue comment` (append-only) — so the fleet's
replacement surface is exactly those three lanes.

## What changes

- `engine-bump.yml`, `registry-sync.yml` and `semgrep-rules-refresh.yml` stop calling
  `gh pr edit <branch> --title … --body-file /tmp/pr-body.md` on an OPEN PR: the title stays a title-only
  `gh pr edit`, and the body reaches the PR only through `make bot-body-write PR=<n> NEW=/tmp/pr-body.md`
  (the number read from the same `gh pr view` that decides edit-vs-create).
- `tests/test_bot_body_write_fleet.py` scans every `.github/workflows/*.yml`: a step that replaces a PR
  body (`gh pr edit … --body-file` / `-f body` / `PATCH … pulls/<n>` with a body field) must route through
  `make bot-body-write`; `issue-bot.yml` and `issue-refiner.yml` are proven append-only (`gh issue
  comment`, no body write); a planted violation is caught.
- `docs/BOTS.md`'s body-write-seam section records the fleet wiring; a changes.d row and an agent-wiki
  entry close the loop.

## What does not change

- The seam itself (`scripts/pr_body_write.py`, `make bot-body-write`) and fix-bot's existing wiring:
  unchanged. A refused (drop-guarded) write stays a logged skip plus a PR comment, not a red run — a
  weekly re-bump that would drop reviewer-added evidence from a still-open bot PR is exactly the case the
  skip is for.
- No workflow gains a trigger; no gate outside `lane-preflight`/`ci-unit` is touched.

