# Confirming an issue is really free before dispatch

An issue that reads "open, `agent:implement`, no `bot-claim:` comment, no branch" is not yet proven
free. Confirm all four checks below before handing it to an implementer; each one has produced a
false "free" verdict.

## 1. Match OPEN PRs, never branch-name globs

Branch naming in llgenie is NOT uniform. Newer lanes use `agent/issue-<n>-<slug>`, but older and
fix-class lanes use `fix/<n>-<slug>`, `fix/<slug>`, `docs/<slug>`, `agents/<slug>`. So

```bash
git ls-remote origin 'refs/heads/agent/issue-<n>*' | wc -l   # 0 proves NOTHING
```

A count of 0 only means no branch matched that one pattern. The authoritative check is the PR list:

```bash
gh pr list --state open --json number,headRefName,title \
  --jq '.[] | "\(.number) | \(.headRefName) | \(.title)"'
```

Then match the issue number against `headRefName` **and** `title` (and skim the PR body for
`closes #<n>`). One open PR carrying the issue means it is taken.

## 2. A conflicting/dirty PR is still a live vehicle

`mergeStateStatus: CONFLICTING` / `DIRTY` is not "free". The merge-conflict / rebase-sweep lane owns
it — it rebases the existing branch. Dispatching a fresh implementer there is the two-vehicle race;
route it to the rebase lane, not a second implementer.

## 3. Re-check the issue is still open, and that no other lane claimed it

The issue may have been closed by a merged PR your stale view predates. Read `state` and any
`bot-claim:` comment from the API in the same breath as the PR scan — do not trust a report (a
cron tick's or a bot's) that says the queue is empty.

## 4. A bot's "ready for #N" can be stale

If a bot reports "ready for #N" but #N has already merged/closed (verify at the head), the report is
stale, not a signal to re-dispatch. Reconcile it on the issue, then assign genuinely unclaimed work.

## The resulting dispatch comment still records the decision

When a candidate legitimately fails one of these checks, say so in the ledger comment — "#N not
free: live vehicle PR #M, rebase target" — so the next reader does not re-flag it as idle-capable
and dispatch a duplicate.
