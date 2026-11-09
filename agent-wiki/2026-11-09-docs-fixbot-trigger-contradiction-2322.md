# Fix the stale fix-bot trigger description in BOTS.md (issue #2322)

## What changed

`docs/BOTS.md:2613` (the fix-bot make-target block) still claimed the fix-bot runs on
an "hourly `schedule` + `workflow_dispatch`" — the pre-#2293 shape. That contradicted
the same file's own manual-only declaration at `docs/BOTS.md:62-66` (owner directive
2026-11-08, #2293), which is the change that removed both auto-triggers. Measured
against `.github/workflows/fix-bot.yml` at `5cc544cf`: the workflow has no `schedule`
and no `workflow_run` — only `workflow_dispatch` with `pr_number`/`branch`/`check`
inputs. A reader landing on 2613 concluded the bot still woke hourly, which is exactly
the automation the gate (`make check-workflows`) refuses to allow back.

The sentence now reads that the fix-bot is `workflow_dispatch`-only and **MANUAL-ONLY**:
a person (or the run-failure-reactor, itself a human dispatch) hands it a PR or branch,
and a re-added auto-trigger fails `make check-workflows` (#2293). The surrounding
`make fix-bot-*` block (sweep / resolve / report) is a human-driven recipe and implies
no automation, so it is unchanged.

## Verified against the spec

- `grep -n "fix-bot\.md.*schedule\|fix-bot.?\?.*hourly" docs/BOTS.md` now returns only
  the explicit **historical negations** — the manual-only section's "used to be woken…
  on `workflow_run` and on its own hourly `schedule` … Both auto-triggers are gone", and
  the "`fix-bot`'s former `:17` hourly slot is gone" line. No sentence describes a
  *current* hourly fix-bot schedule.
- `make lint` and `make check-docs` pass; `make check-architecture-census` logic verified
  (leaf `python3 scripts/check_architecture_census.py check`) — the census concerns
  `docs/ARCHITECTURE.md`, which this change does not touch.
- The authoritative manual-only text (lines 62-66) and the workflow's own `on:` block
  agree with the rewritten sentence.

Implements issue #2322 (the docs half of the structural audit whose ARCHITECTURE.md fix
is PR #2321). This change's PR: #2334 (expected).
