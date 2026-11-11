# Exercising the bot fleet: one dispatcher at a time

When asked to "test the bot dispatchers one at a time, monitor the pipeline, and create a
fix PR where the new logic is tested", run the fleet as a SEQUENTIAL loop, never in
parallel — each bot gets its own issue → worktree → OpenSpec change → code+tests → PR,
and you only start the next bot after the current one's PR is green (or verified healthy
with no PR needed).

1. **Enumerate the fleet** from `.github/workflows/*.yml` (the dispatchable bot files, not
   `ci.yml`/`pipeline.yml`).
2. **Exercise each bot's deterministic half against the LIVE CLI** from the repo
   (`make <bot>-sweep`, `make <bot>-pick DRY=1`, `make <bot>-scan`) and compare its
   finding/run counts against what CI reported. A bot whose runs are all green may be a
   bot that never ran — see the `set +e` section in SKILL.md. This is where the real
   defects surface.
3. **For each defect**: file the issue, cut a worktree off latest `main`, write the
   OpenSpec change FIRST, implement, prove the new tests FAIL on the pre-fix tree and
   PASS post-fix, run the gates, open the upstream PR (`closes #<issue>`), and monitor
   `gh pr checks <n> --watch` until green.
4. **A bot with no defect needs no PR** — verify it is healthy and move on. Do not
   manufacture a change to look busy.
5. **When a PR merges, verify the bot on merged `main`** — re-run its deterministic half
   against `origin/main` and confirm the defect is gone. Do this one bot at a time, in
   merge order, not all at once.
6. **Rebase your open PRs whenever `main` moves** (a sibling PR merging is the common
   cause). A PR left behind `main` rots and can be rejected at the merge gate; rebase
   and `--force-with-lease` your own branch, never force-push a shared one.

Out-of-scope findings and unresolved anomalies are filed as their OWN issues (linked both
ways), never folded into the current PR — the change you ship keeps a single objective.
