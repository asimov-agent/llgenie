# The rebase-bot's four failure modes (llgenie)

Every one of these produced a green-looking run that rebased nothing. Read this before changing
`scripts/rebase_bot_sweep.py`, `scripts/rebase_bot.sh` or `.github/workflows/rebase-bot.yml`.

## 1. `UNKNOWN` merge state is not "no rebase needed"

GitHub computes mergeability lazily, so a fresh `gh pr list` right after a push/comment returns
`mergeStateStatus: UNKNOWN` for every PR. Treating that as "clean" skips exactly the PRs that
conflict. Re-ask the PR itself: `gh pr view <n> --json mergeStateStatus`, bounded
(`UNKNOWN_ATTEMPTS` / `UNKNOWN_DELAY_S`, CLI `--unknown-attempts`/`--unknown-delay`); a PR that
stays UNKNOWN is reported as **deferred to the next run**, never as "nothing to do".

## 2. "Already rebased today" must be read from the DONE marker, never from prose

Matching `rebase-bot` + today's date across comments counts the bot's own **claim**
(`<!-- bot-claim: rebase-bot ... -->`) and its failure comments as completed work. Count only
`bot_claims.DONE_RE` markers with `bot == REBASER`, today's date and kind `rebased`. The actor
(`scripts/rebase_bot.sh` `comment()`) must write kind `rebased` on the push path and `gave-up` on
every failure path.

## 3. A conflicted `Makefile` stops `make` before any target

GNU make parses `Makefile` before running a target, so on a rebase that stops with conflict
markers in `Makefile`, `make rebase-bot-agent` and `make rebase-bot-sweep` both die with
`Makefile:N: *** missing separator`. Consequences:

- snapshot the Makefile BEFORE the checkout and invoke through it: `make -f $MK_SNAPSHOT <target>`;
- the container side must run `hermes -z "$$(cat)" $(nous-alias) --reasoning medium --yolo`
  directly, never a nested `make _internal-target` (it would re-read the conflicted file);
- the actor aborts its own stopped rebase on every failure path, so the loop's next decision has a
  parseable tree;
- every `hermes -z` line in the Makefile must carry `$(nous-alias)` (checked by
  `tests/test_issue_implementer.py`) -- a literal `-m nous-deepseek` is a red gate.

## 4. One PR per run cannot drain a backlog, and the day marker must not bar a re-dirty

`main` moves while the bot sleeps, so a PR rebased this morning is `DIRTY` again by afternoon.
Two rules together fix it:

- the run loops: re-ask the sweep after each rebase until it answers none/cap, bounded by a
  documented `max_prs` dispatch input (step-level `MAX_PR="${MAX_PR:-10}"` so the step still fails
  when a decision crashes and `MAX_PR` is unset -- `tests/test_bot_decision_loudness.py` runs steps
  alone);
- eligibility is the merge state, NOT today's marker (markers only bound `MAX_PER_DAY`). Pass
  `--skip` with the PRs the run already handled -- **including the failed ones**, or the loop retries
  the same conflict up to `max_prs` times.

## Testing these without a model or a real repo

- `gh` is driven through a generated fake on PATH that records argv and answers from JSON fixtures
  (`pr list`, `pr view --json comments|mergeStateStatus`, `pr checks`, `search prs`).
- The actor is driven against a real scratch git repo with a real bare remote and `GATES=true`, so
  the rebase/abort/push are real; only the agent command is a stub.
- Workflow shape assertions (`yaml.safe_load`) are the cheap tests for the loop, `SKIP=` and the
  step env; behaviour of the sweep is tested through the real module.

## Note on the host skill

`SKILL.md` for `llgenie-engine-image-ci` is at its 100k limit, so this file is not linked from it;
load it explicitly with `skill_view(name='llgenie-engine-image-ci',
file_path='references/rebase-bot-pitfalls.md')` when touching the rebase bot. The next change to
that skill should split the existing SKILL.md into references first.
