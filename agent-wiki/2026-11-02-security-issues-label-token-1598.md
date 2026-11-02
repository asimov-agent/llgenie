# 2026-11-02 security-issues labels with the run's own write token, not the owner PAT (issue #1598)

Issue **#1598** (planner-dispatched to this lane: the implementer declined it — the fix is a pure
workflow/token edit, gate/workflow ownership is this lane's).

## What broke

`make security-issues` created a finding and then its label write died:

```
[security-issues] could not label #1597: gh: Resource not accessible by personal access token (HTTP 403)
make: *** [Makefile:1175: security-issues] Error 1
```

measured at report-only dispatch run **41461058238** (sha `99874a46`, `enforce=report`). An unlabelled
finding is invisible to `security-bot` (it picks ONE issue per run by label), so the finding was filed
where nobody reads it. Root cause: the step's `GH_TOKEN` was `${{ secrets.BUMP_TOKEN || secrets.GITHUB_TOKEN }}`
— the owner PAT (BUMP_TOKEN) shadowed the run's job-scoped `GITHUB_TOKEN`, and that PAT lacks
issue-label-write (`issues: write`) on this repository.

## The fix

`.github/workflows/security-scan.yml`, `scan` job, `make security-issues` step: point `GH_TOKEN` at
`${{ github.token }}` — the job-scoped `GITHUB_TOKEN`, **already** granted `issues: write` in this
job's `permissions:` block. `security_issues.py` creates the issue and POSTs the labels through the
SAME `GH_TOKEN` env (`_gh` / `set_labels` → `_gh_api`), so create-identity == label-identity == the
run's write-scoped token. The 403 cannot happen because the identity that labels now *has* the
permission and is the same identity that created.

Token remains `BUMP_TOKEN` exactly where a push must start workflows (#136): the `actions/checkout`
and the `make security-bumps` step. The `security` label requirement is untouched — an unlabelled
finding stays a visible red (a real filing failure), never a silent gap. No gate, fail_on or
severity changed.

## Acceptance (as the issue states)

1. a `security-issues` run that creates finding #N also leaves #N labelled (`security` + the finding's
   `severity:*`/`component:*`/`auto-fixable`), read back after the write — the write identity is the
   run token that has `issues: write`;
2. a 403 on a label write no longer reds the run by itself — the write can no longer 403 (same
   write-scoped identity), so there is nothing to red; a genuine filing failure still reds (recorded
   gap, never silent);
3. `enforce=report` concludes what the policies say — a label-step success with a report-mode verdict
   is not a red.
