# bot-decision-loud — a crashed bot decision must fail the step (issue #312)

Implements **#312**. Part of the "exercise every bot dispatcher one at a time" sweep; the per-bot
crashes it generalises from were fixed by #310 (rebase-bot) and #316 (issue-refiner).

## The live defect

`issue-bot.yml`'s `dispatch` step:

```yaml
          set +e
          out=$(make issue-bot-dispatch REPO="$REPO" FORCE_ISSUE="${FORCE_ISSUE:-}")
          rc=$?
          echo "$out"
          echo "rc=$rc" >> "$GITHUB_OUTPUT"
          ...
          if [ "$action" = "cap" ] || [ "$action" = "none" ]; then echo "dispatch=false" …; else echo "dispatch=true" …; fi
          exit 0
```

`rc` is captured and published, then **never read**. A crashed dispatch leaves `action` empty, the
cap/none test is false, so `dispatch=true` — and the run proceeds to the JEV gate, the smoke, triage
and implementation with **no issue picked**, failing (if at all) far from the decision.

The other two measured swallows are already fixed: `rebase-bot.yml` (#310) and `issue-refiner.yml`
(#316) carry an rc check; `fix-bot.yml` runs its `make` as the step's command under `set -euo
pipefail`, so a crash already fails it.

## The fix

`issue-bot.yml`'s dispatch step now fails loudly on a non-zero decision, naming the target and rc.

## The guard — behaviour, not grep

`tests/test_bot_decision_loudness.py` (wired into `test-unit`) reads every workflow step that runs a
decision target (`…-sweep`, `…-pick`, `…-dispatch`) and **runs that step's own shell** with a `make`
on `PATH` that exits 7, requiring a non-zero exit. A grep would not do: `set -e` in the wrong place,
an `exit 0` at the end of the step, or an rc that is captured but never read all look guarded.

Three things the file also pins, each earned by a mistake made while writing it:

- **The scope is read from the tree** (`issue-bot.yml`, `issue-refiner.yml`, `rebase-bot.yml` must be
  in the set), so a bot workflow added later is covered the moment it exists — the "derive the set or
  the guard goes blind" rule from #302.
- **A `${{ … }}` is substituted before the step runs** (the way the runner does). `fix-bot.yml` really
  does use `REPO="${{ github.repository }}"` in a `run:` block; left in place it crashes bash, which
  would have made the loudness test pass for the WRONG reason. The substitution is itself asserted.
- **The other direction**: a decision that answers cleanly leaves the step green, so the rule is not
  "always fail".

## Verification (real output)

- Rule 6c: on a pre-fix worktree (`origin/main` + the new test file) →
  `2 failed, 3 passed`, the failures reading
  `assert 0 != 0 … fake make: issue-bot-dispatch REPO=asimov-agent/llgenie FORCE_ISSUE=`; on this
  branch → **5 passed**.
- `make lint`, `make check-wiring`, `make check-docs`, `make check-workflows`,
  `make openspec-validate NAME=bot-decision-loud` green.

## Status

Branch `fix/bot-decision-loud`, PR against `asimov-agent/llgenie:main`.

## Related, closed while working this

- **#330 fixed by the merged #331** (`fix/check-workflows`) — my PR #334 was a duplicate and is
  closed. Verified: no `engine-bump-rebase.yml` run has been created since that merge, so the red
  0-job run on every workflow-touching push to `main` is gone.
- **#318 closed** as fixed by the same merge.
