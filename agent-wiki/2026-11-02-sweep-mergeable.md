# The rebase sweep reads `mergeable`, not just `mergeStateStatus` (issue #1566)

The fleet's in-repo rebase automation (`scripts/rebase_bot_sweep.py`, the CI `rebase-bot` job in
`.github/workflows/rebase-bot.yml`) exists to bring conflicted PRs back onto main. Until this
change it decided "needs a rebase" from `mergeStateStatus` alone:

- `NEEDS = ("BEHIND", "DIRTY")` → `rebase`;
- every other value — `BLOCKED`, `UNSTABLE`, `CLEAN`, `HAS_HOOKS`, `DRAFT` — collapsed to `NONE`;
- the PR/`mergeable` field was never read (`grep -c 'mergeable'` on the file was 0 across its
  whole history, and `git log -S mergeableState` returned nothing).

The stale-read consequence is the #536 class, which #536 closed without its fix ever reaching this
script: a PR that is genuinely `mergeable: CONFLICTING` (a real merge conflict) but whose
`mergeStateStatus` GitHub reports as `BLOCKED` (a required review is pending) or `UNSTABLE` (a
check is failing) was classified `NONE` and passed over — the only automatic rebase that runs
every 6 hours skipped the exact PR it exists for, until GitHub's lazy recompute happened to flip
the state to `DIRTY`. This contradicted the fleet's own standing rule (#1015, in
`agents/llgenie-pr-merge-conflict/SOUL.md`: measured fresh with `mergeable == "CONFLICTING"`, never
`mergeStateStatus` alone).

The fix reads the platform's conflict answer rather than guessing behind the mask:

- `outcome(state, mergeable=None)` now returns `rebase` when `mergeable == "CONFLICTING"` — even
  when the state reads `BLOCKED` / `UNSTABLE` / `CLEAN`. A crash still wins over a conflict (a
  crashed read is never read as a rebase), and a plain `BLOCKED` PR with `mergeable: MERGEABLE` is
  still `NONE` (the override is the conflict, not the field).
- `pr list --json` and the `resolve_state` re-query both carry `mergeable` (the re-query now
  returns `(state, mergeable)`), so the swept PR's true conflict state is known even behind a
  pending review or a red check.
- The coexistence logic is unchanged: the fix-bot's red-and-behind rule still applies to `BEHIND`,
  and a genuinely conflicting PR is taken even when red (the rebase is the precondition for a fix).

A regression test proves the #536 evidence shape end-to-end: a `BLOCKED` PR with
`mergeable: "CONFLICTING"` is returned `action=rebase` by the sweep, and the `pr list` read must
have asked for `mergeable`. `make ci-unit` and the sweep path carry the change.

Delivered as a reviewable PR on branch `fix/1566-sweep-mergeable` (base `origin/main@b5a44aec`),
ready for the #1088 owner gate.
