# PR metadata gates: when the red is in the body, not the code

A `guard` / `ci-scope` red on a bot PR is often not a code defect at all. A family of gates reads the PR **body** and the head **commit message**, never the diff: `check-pr-hygiene`, `check-pr-acceptance-form`, `check-pr-closing`, `check-pr-authors`, plus the body-carried `AGENTS:` and per-profile `SYNC:` lines. A red on one of these is fixable from your own vehicle with no code change, no re-cut and no reviewer — treat it as a metadata defect, not a broken gate.

## Identify which gate and why

1. Read the failing step's OWN log, never the badge — a `conclusion` is a verdict, not a cause.
   ```
   gh api repos/<o>/<r>/actions/runs/<run>/jobs \
     --jq '.jobs[]|select(.conclusion=="failure")|.id'
   gh api repos/<o>/<r>/actions/jobs/<job>/logs --allow-escape-sequences \
     | grep -E "\[check |Error 1"
   ```
   The failing step's name (`make check-pr-…`) names the gate; the line immediately above `make: *** [Makefile:…] Error 1` is the gate's own refusal message and states exactly what is missing.

2. Reproduce the gate locally in isolation — do not spend a CI cycle to relearn the same fact:
   ```
   gh api repos/<o>/<r>/pulls/<n> --jq .body > /tmp/body.md
   python3 scripts/check_pr_hygiene.py acceptance-form \
     --head <sha> --base origin/main --body-file /tmp/body.md
   ```
   Run it from a clone that actually has the script on disk — the main clone can lag or lack it; locate one with
   `find $HOME/repository/git -maxdepth 3 -name check_pr_hygiene.py`.

## Fix and re-prove

- **Body-only reds** (`acceptance-form`, hygiene, `AGENTS:`, `SYNC:`): edit the body file, re-run the local gate until it prints `OK`, then patch the body on the wire:
  ```
  gh api -X PATCH repos/<o>/<r>/pulls/<n> -F "body=@/tmp/body.md"
  ```
  Use `-F body=@file` for a multi-line file — `--field body="$(cat …)"` mangles newlines. Read it back and confirm the section landed (`…/pulls/<n> --jq '.body' | grep -n '## Acceptance criteria'`).
- **Commit-message reds** (`check-pr-closing`, authors): amend the head commit (`git commit --amend`), then force-push `--force-with-lease --force-if-includes` after a fresh fetch.

## Traps

- `## Acceptance criteria` must be a real markdown checklist — one `- [ ]` box per provable outcome. A prose paragraph that merely describes the outcomes does not satisfy the gate; the gate rejects it by name and quotes the rule.
- A body-only change never justifies re-cutting the branch, cancelling a run, or a code push. PATCH the body and let the guard re-run at the same head.
- `AGENTS:` and the per-profile `SYNC:` lines are body-carried too: a body edit that claims code wiring without them re-reds the same gate.
- Never act on a dispatch's quoted head sha without fetching: the vehicle is frequently amended or merged before the dispatch reaches you. `gh api …/pulls/<n> --jq '.head.sha,.merged_at'` first — if it is already merged there is nothing to amend, and a push would rewrite a landed branch.
- A red whose step name is a `check-pr-*` target is **never** a reason to ask the owner for approval or to hand off to another lane: it is a one-line metadata edit on your own vehicle.
