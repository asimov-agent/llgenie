# Architecture re-audit of four structural merges (issue #3095)

## Change

`docs/ARCHITECTURE.md` was re-audited at `origin/main=499532275692a025d899399f34e28b832decfe69`
after a 4-merge structural burst (`dac7ef060..origin/main`) left it with **0 touches**. Each of the
four surfaces was measured against the tree at that sha (the merge's own changed-file list and the
relevant diff hunk), then either reflected below or recorded as needing no architecture-doc change.

## Measured per surface

1. **`499532275` (#3085/#3084) — planner merge behavior.** `agents/llgenie-planner/SOUL.md` now
   says "Never hand-merge, never push to `main`" and "An approval is neither a precondition for
   landing nor a licence to merge — `REVIEW_REQUIRED` is not a human gate to wait on" (AGENTS.md
   rule 7). **Reflected** in **Bots**: auto-merge lands a green conflict-free PR without a human
   click; approval is no longer a precondition.
2. **`be5009ee4` (#3086/#3026) — agent-model re-pin.** The doc's old sentence "(alias
   `nous-deepseek`, `deepseek/deepseek-v4-flash-0731`)" no longer matches the tree: the chain's one
   home is `agents/hermes-base-config.yaml` (`meituan/longcat-2.5:free` default, Nous free first,
   paid deepseek last), and `scripts/agent_model_pin.py` now admits a repeated chain id only when
   `model.documented_duplicate_issue` names it and a catalog-absent member only when
   `model.catalog_known_absent` tracks it. **Reflected** in **Bots / model chain**.
3. **`f3e97527f` (#3079/#3057) — ci-hf-live drift filing.** The workflow now files a named drift
   from its own `build/trend-staleness-drift.json` handoff and re-raises a filing failure as exit 3
   instead of the unreadable exit 2. **Reflected** in **CI** beside the `ci-unit` gate bundle.
4. **`5594b488b` (#3094/#3076) — engine-bump gate contract.** `.github/workflows/engine-bump.yml`
   restamps the COMMIT acceptance block through the same composer before the lane pushes.
   **Reflected** in **Engine images** and the workflow's row in the **CI** table.

No script, test, workflow or gate was changed by this re-audit — the four merges' own PRs and their
OpenSpec changes stay read-only. `make check-docs` rc=0 at the new head (measured in the PR body).
