# Bot claims, leases and branch orphans

Depth for the status sweep: how an automation claim is written, how to decide whether it is still live,
and how to find the branches that keep a queue re-offering the same work.

## The claim comment

A claiming bot posts an HTML comment so it does not render in the thread:

```
<!-- bot-claim: <actor> <ISO-8601-Z> implement ttl=<minutes>m run=<run-id> -->
`<actor>` is implementing this now. Other bots: leave it alone for the next <N/60> hours.

branch `<branch>`; one issue per run, at most <N>/day, PR left for review (never merged).
```

Fields worth parsing: actor, the ISO stamp, `ttl=<N>m`, `run=`. The stamp is when the claim was WRITTEN,
not when it expires.

## Liveness arithmetic

```python
import datetime, re
stamp = datetime.datetime.fromisoformat(iso.replace("Z", "+00:00"))
live = datetime.datetime.now(datetime.timezone.utc) < stamp + datetime.timedelta(minutes=ttl)
```

Rules that follow:

- **Multiple claims on one issue: the live one wins.** A repo can carry a claim from three days ago and a
  fresh one; a stale claim is not evidence of current work and must not be reported as such.
- **A claim with no branch is vapour** — check the branch exists before believing the work started:
  `gh api repos/<o>/<r>/branches/<branch>` answers **HTTP 404** even when the run's own summary says
  `changed=true (make implement-issue rc=0)`. That summary means "the agent computed a diff", never "a
  branch exists".
- **A live claim on a nonexistent branch is worse than an expired one: it is a lock with no work behind
  it.** Every other implementer is told to leave the issue alone for the TTL, so the highest-value item in
  the backlog sits idle for hours. Post a comment stating the 404 and the `PR: none opened` line, declare
  the claim released, and dispatch the work again at once — nothing retries a claim on its own, so waiting
  for the TTL only wastes it.
- **A claim with a branch but no PR, past TTL, is an orphan.** Either reopen the work (open the PR the run
  failed to open) or delete the branch; leaving it means the next sweep re-offers the issue.
- **Expiry is not completion.** Nothing in the comment stream marks a claim finished; the absence of a PR
  is the only signal, so join against `gh pr list` rather than reading the comment stream alone.

## Sweep one-liners

```bash
d=$(mktemp -d)
gh issue list --repo <o>/<r> --state open --limit 300 \
  --json number,title,labels,assignees,createdAt,updatedAt,comments > "$d/issues.json"
gh pr list  --repo <o>/<r> --state open --limit 100 \
  --json number,title,headRefName,mergeStateStatus,author,createdAt > "$d/prs.json"
gh api repos/<o>/<r>/branches --paginate --jq '.[].name' > "$d/branches.txt"
date -u   # the clock every TTL comparison runs against
```

Then in Python: build `{issue_number: [claim…]}` from the comment bodies with
`re.search(r"bot-claim: (\w+) ([\d\-T:Z]+)", body)`, compute liveness, and cross the open-PR
`headRefName` prefix (`agent/issue-<n>-…`) back to the issue number.

## Which branches are orphans

A branch is orphaned when ANY of these holds:

- `agent/issue-<n>-…` and issue `<n>` is **closed**;
- `agent/issue-<n>-…` and issue `<n>` is open but has **no open PR** and **no live claim**;
- `agent/<workflow>-<timestamp>` (e.g. an architecture/doc refresh) whose PR has merged or closed.

Report the orphan count with the branch names in one line each — the fix is a single sweep (delete, or
re-open the PR), not one issue per branch.

## Local vs. in-repo automation

The actors that write claims and trackers here are GitHub Actions running as `github-actions`, triggered
by `issues`, `workflow_run` and `schedule` events. A local Hermes cron store
(`~/.hermes/cron/jobs.json`) holding no matching jobs is the normal case, not a fault. Verify with
`gh run list --limit 25 --json name,event,createdAt` before describing any bot as "local" — the
attribution decides who can be asked to act.
