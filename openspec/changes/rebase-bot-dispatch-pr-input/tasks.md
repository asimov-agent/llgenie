# Tasks — rebase-bot-dispatch-pr-input (#2446)

- [x] 1. `scripts/rebase_bot_sweep.py`: `sweep(..., target=…)` + `--pr <n>` argparse; aimed
      evaluation restricted to the target; a not-open/not-main target answers `action=none` with
      a named reason.
- [x] 2. `mk/bots.mk` `rebase-bot-sweep`: forward `TARGET_PR` → `--pr`.
- [x] 3. `.github/workflows/rebase-bot.yml`: optional `pr` workflow_dispatch input + job env
      threading; the drain loop passes the aim to every sweep call; header comment updated.
- [x] 4. `AGENTS.md`: document the `pr` input (unset = board-wide sweep) in the rebase-bot text.
- [x] 5. `tests/test_rebase_bot_sweep.py`: aimed-pick tests (target taken despite an older
      behind PR; ineligible target refused by name; held target passed over).
- [x] 6. Verify: full test module green, `make openspec-validate`, workflow lint/wiring gates,
      and one live aimed dispatch (`pr=2686`, run 43651269491) reaching a named completing state:
      `action=rebase` evaluated, push refused at the squash-close re-check (the commit's missing adjacent
      `closes #2446` — fixed in this branch), `rebased=0 failed=1` recorded, run RED as the honest outcome.
