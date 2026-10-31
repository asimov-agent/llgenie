# Four formerly-ungated lanes now declare the rule their SOUL states (#1108)

## What changed

`agents/manifest.json` declared `rules: []` for four profiles, so `check-agent-profiles` reported them
`UNPROTECTED` — nothing in their `SOUL.md` was gated, and a deleted rule would have passed CI silently:

```
[check-agent-profiles] UNPROTECTED llgenie-issse-implementer: the manifest declares no standing rule …
[check-agent-profiles] UNPROTECTED llgenie-security: …
[check-agent-profiles] UNPROTECTED llgenie-documentation-maintainer: …
[check-agent-profiles] UNPROTECTED llgenie-ci-pipelines-maintainer: …
```

Each now declares the rule its SOUL **actually states**, measured against `stated_text()` (the
quote-stripped view the gate matches) — not the rule it "should" have:

| profile | declared | statement matched |
|---|---|---|
| `llgenie-issse-implementer` | `never-merge` | "**Never push to `main`, and never merge by hand.**" |
| `llgenie-security` | `never-implement` | "This lane reports scope; it does not implement." |
| `llgenie-documentation-maintainer` | `never-implement` | "6. **You never implement.**" |
| `llgenie-ci-pipelines-maintainer` | `never-merge` | "**You never merge.**" · "5. **I never merge …**" |

`llgenie-documentation-maintainer` is deliberately **not** declared `never-merge`: the regex matches a
conditional about *stacked* PRs ("is never merged into `main` on its own"), while that SOUL explicitly
merges its own docs PRs (lane rule 4, "Then merge it yourself… No approval needed"). Declaring it would
gate the lane on a rule it rejects by design.

## What was verified

- `UNPROTECTED` count **4 → 0** at the pushed head.
- `tests/test_agent_profiles.py` **123 → 124 passed**, including a new test that pins both halves per
  lane (a known rule is declared, and its pattern appears in the SOUL's stated text); the test uses a
  subset check (`declared <= STANDING_RULES`) so a lane declaring more later does not red it.
- Gate exit in the CI environment (`HERMES_PROFILES_HOME=/nonexistent`) is **0** on the pushed head.

## Negative controls (three, each re-run after the first did not fire)

1. Removing only "**You never merge.**" from `llgenie-ci-pipelines-maintainer` left the rule stated by
   "**I never merge …**" and the gate stayed silent — the sabotage had to remove **both** to red it:
   `FAIL standing-rule: … no longer states 'never-merge'`. Restore → clean.
2. Per-lane delete-test on all four profiles: each removal produced `FAIL standing-rule` naming that
   profile (fires = 1 for each of the four).
3. Reverting `llgenie-security` to `rules: []` reds the new test:
   `llgenie-security declares no standing rule — its SOUL is ungated (issue #1108)`; restore → 124 passed.

## Not covered

- The gate still reports 46 `absent-from-tree` findings when run against a live host profile (live-only
  skills). That is issue #1060's scope, unchanged here, and absent in CI (no live profiles there).
- `check-docs` is red on this base for an unrelated reason: the architecture census's pointer
  `564e938` is not a commit in history. Measured identical at the base, so it is not caused by this
  change and is left to its own issue.
