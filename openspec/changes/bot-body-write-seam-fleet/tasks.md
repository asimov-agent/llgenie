# Tasks — bot-body-write-seam-fleet (issue #2852)

## 1. Wire the replacement lanes

- [x] `engine-bump.yml`: the OPEN-PR branch reads the PR number from `gh pr view` and hands the stamped
      body to `make bot-body-write`; the `gh pr edit` keeps only `--title`.
- [x] `registry-sync.yml`: same shape for `chore/registry-sync`.
- [x] `semgrep-rules-refresh.yml`: same shape for `chore/semgrep-rules-refresh`.

## 2. Assert the fleet

- [x] `tests/test_bot_body_write_fleet.py`: fleet scan (replacement lanes wired; append-only lanes
      classified; planted violation caught) wired into the unit battery.

## 3. Docs + close

- [x] `docs/BOTS.md` seam section records the fleet wiring; `agent-wiki/` entry + `docs/changes.d/` row;
      `make check-docs` green.
- [x] `make openspec-validate NAME=bot-body-write-seam-fleet` passes and `make test-unit` is green at the
      final head (tick only after both run green).

