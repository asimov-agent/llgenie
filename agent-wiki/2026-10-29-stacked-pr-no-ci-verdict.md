# 2026-10-29 — issue #945: a stacked PR has no CI verdict, because `pull_request.branches` filters the BASE

## What was wrong

`docs/BOTS.md` describes PRs as "waiting on CI", "green", and "blocked on checks". For a stacked PR
(one whose base is another feature branch) none of those words apply, and the page said nothing about
it. `.github/workflows/ci.yml` triggers `pull_request` with `branches: ["main"]`, and on a
`pull_request` event `branches` filters the **base**, so a stacked PR gets no run at all.

Measured at `main@5017128e` (2026-10-29), on the three stacked PRs of the moment (#944, #929, #921,
all based on `feat/agent-profile-implementer-skill`):

```
gh pr list --state open --json number,baseRefName,statusCheckRollup \
  | jq '.[] | select(.baseRefName != "main")'
944 feat/agent-profile-implementer-skill 0
929 feat/agent-profile-implementer-skill 0
921 feat/agent-profile-implementer-skill 0
gh run list --branch fix/922-quoted-rule-gate --json databaseId | jq length
0
```

`gh pr checks` renders that as `no checks reported`, which an operator reads as "a job has not
started" rather than "no job will ever start" — the same failure shape as a hold with no remedy.

## The rule, and why it belongs on the page

A doc that says a PR is "waiting on CI" when no run exists is a claim about a state it never read.
The rule the page now states: a stacked PR can never be green, it is merged only into its base, and
the base's own PR carries the verdict for `main`; the moment the base lands, retarget
(`gh pr edit --base main`) or rebase, because until then no gate is inspecting the head.

## Verified

- `make lint`, `make check-docs`, `make check-wiring` on the PR head.
- The claim is reproducible with the two commands above; the `AGENTS: <sha>` line in a PR body is
  the read-by-eye check, since a base that is not `main` means the line quotes a tree the PR will
  never merge into.

Issue: #945
