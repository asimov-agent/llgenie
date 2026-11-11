# check-pr-acceptance: the reviewer-verdict write-back is a dispatch, not a wait

`check-pr-acceptance` (Makefile:1131, scripts/check_pr_acceptance.py) reds on ANY PR whose body
`closes #N` an issue whose `## Acceptance criteria` are unticked. `linux` `needs: [guard]`
(ci.yml:438), so the failing guard SKIPS the whole matrix — no substantive run exists until the
criteria are ticked.

This is the reviewer lane's domain, NOT an owner wait. The honest unlock is a reviewer COMMENTED
verdict (never an approval, #1088) then:

```bash
python3 scripts/acceptance_writeback.py writeback --issue N --proven <list> --verdict-ref <id>
```

Issue #1644 closed at 2026-11-05; the mechanism lives on main. `## Not covered` with a linked
work item is the only alternative unlock (the gate message names both escapes), and it is
dishonest when the criteria ARE the PR's in-scope work — so for a normal bot PR the write-back is
the path, and the planner dispatches it rather than reporting the PR as owner-blocked.

Before dispatching a reviewer write-back: re-measure the criterion counts from the GUARD job log
(`gh api .../actions/jobs/<id>/logs` on the failing guard job, `[check-pr-acceptance] N violation(s)`)
and confirm each PR's body carries the exact `closes #N`. Do not trust a count from memory.

Route to llgenie-pr-reviever when it is idle-capable (no claims, no queued kanban task, state.db
stale) via:

```bash
hermes kanban create "review verdict + #1644 write-back on #a #b #c" \
  --body-file <brief> --assignee llgenie-pr-reviever --workspace scratch \
  --created-by llgenie-planner --idempotency-key <unique>
hermes kanban dispatch --max 1
```

`--workspace default` is rejected (scratch | worktree | dir only). Verify spawn: `running` count +1,
and the brief must state one-vehicle-per-issue (do not touch sibling PRs with distinct reds, e.g.
a separate engine-build-pr-trigger failure), reuse `--workspace <worktree>` only when the issue
already has a worktree holding it, and require `--force-if-includes` not `--force-with-lease` on
any push.
