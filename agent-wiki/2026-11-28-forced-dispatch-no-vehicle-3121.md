# 2026-11-28 — forced dispatch must not report a no-vehicle success (#3121)

Observed on `origin/main d5858e861`: forced `issue-bot` runs `46091159027` and `46091817304` each
passed the agent-image source check, then died at `mk/bots.mk:135` with `[agent] Error:
unknown_skill`. The state.db error that followed 0.1 ms later was a consequence: no Hermes session
had been created because the triage leg never started. Both runs ended `completed success`, posted
`verdict: none reached`, opened no branch and no PR.

Two independent defects were fixed:

1. **Profile-scoped skill registration.** `scripts/install_hermes_ci.sh` registered
   `/repo/.hermes/skills` only in the global `$HERMES_HOME/config.yaml`. A bot leg runs as
   `hermes -p <lane> …`, which resolves skills from that profile's own config, so `issue-triage`
   was invisible even though it is in the mounted checkout. The installer now registers the
   checkout in every installed lane profile and reads each registration back at build time.
2. **No-vehicle outcome guard.** The workflow swallowed the triage rc and treated
   `action=dispatch` as a successful hand-off. A new step after the durable outcome comment fails
   the job when the triage leg failed, no verdict was reached, or `verdict=implement` produced no
   changed tree, no pushed branch and no PR. `refine`/`close`/`hold` remain legitimate no-PR verdicts.

A forced dispatch onto an issue with the `blocked` label is now refused as `action=blocked` in
`scripts/issue_implementer.py::dispatch`, before a claim or branch is written.

Proof: old-tree negative control failed both new regression tests (`2 failed`); at the fixed tree
the four focused tests pass (`4 passed`). The regression suite covers the triage-leg failure
layer, not only the `action=dispatch` layer.
