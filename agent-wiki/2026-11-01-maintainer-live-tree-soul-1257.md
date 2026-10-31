# LLGenie Pipeline Maintainer: version the post-reload live lessons back into the tree

Versions live→tree drift for the `llgenie-ci-pipelines-maintainer` lane (issue #1257; does **not**
close any prior drift row — this is the lane's first live→tree versioning under the #791/#1062
convention, folding in the reload directive).

The live profile kept absorbing rules **after** the reload directive asked it to re-anchor to current
main. Owner confirmed the live Hermes profile is the authoritative newest copy; the tree copy at
`1db367a2` LAGS it by one rule:

- **owner 2026-11-01 rule** — "A defect in the pipeline files is this lane's pull request": when the
  red is a workflow, a gate, or a make target this lane owns, open the fix PR + `message_agent`
  `@llgenie-planner` with PR number, head sha, run id; a red in another lane's product change stays a
  report (do not take their fix, do not rebase; `llgenie-pr-merge-conflict` owns rebases).

The tree `SOUL.md` (96 lines) is copied **byte-identical** from the live 97-line profile, so a future
sync cannot shrink the live copy back to the stale tree. This change-note ships in the **same** PR as
the SOUL.md edit, per the change→note gate (a live→tree skill/soul sync edits `agents/**` and owes its
own change-record note in that PR).

## Verification
- Before: tree `agents/llgenie-ci-pipelines-maintainer/SOUL.md` = 96 lines, md5
  `3ef833405f…`, owner-2026-11-01-rule grep = 0.
- After: 97 lines, md5 `6b1d2904ea…` == live profile byte-for-byte, rule grep = 1.
- Confirms live is authoritative; the tree catches up via PR (never a private edit).
