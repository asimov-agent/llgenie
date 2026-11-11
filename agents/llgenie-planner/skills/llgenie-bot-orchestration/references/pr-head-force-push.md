# Force-push moves a green head: re-read the TRUE current head

When a lane force-pushes (e.g. a re-author during the run to fix the author allowlist, #840), the PR head MOVES. A set of green check-runs you verified at the OLD head ceases to be the current truth.

- `mergeable_state` reads `dirty`/`mergeable=false` at a green head until the mergeability cache recomputes — that is usually NOT a conflict; it is the moved-head + stale-cache artifact.
- NEVER assert green at an intermediate head. Re-read the TRUE current head (`pulls/{n}` `.head.sha`) and its own check-runs rollup (`commits/{sha}/check-runs`) each turn.
- Verify one gate = not green; verify the CURRENT head's full check-runs concluded.
- A git `branch` query on the canonical repo for a fork-owned ref falls back to the default branch (returns the main tip as if the branch existed) — read fork branches by NAME (`repos/andyholst/llgenie/branches/{ref}`), never by sha, never from the canonical repo.
