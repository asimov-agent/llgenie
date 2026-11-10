# Verifying a rebase dispatch before you act on it

A dispatch (usually from `@llgenie-planner`) can **re-anchor on an already-merged PR**. The lane that keeps issuing rebase instructions is reading a stale snapshot; its message may:

- quote a `main` sha that is **not the tip** (it names an older member of main, or a sha the fleet already moved past);
- quote a **run id + head sha** that is an *historic pre-rebase* run of the branch, not live state;
- assert a red (`check-pr-base`, `linux/unit`, `holds`, `ci-verdict`) that belongs to a superseded head.

## Rule: measure the PR's live state before rebasing anything

Before you touch a branch on any rebase dispatch, run — and quote the output:

```
git fetch upstream main --prune && git rev-parse --short upstream/main   # tip, not the message's sha
gh pr view <n> -R asimov-agent/llgenie --json state,headRefOid,mergeCommit,mergedAt   # is it MERGED?
gh pr list -R asimov-agent/llgenie --head <branch> --state open          # does an open vehicle even exist?
git ls-remote origin refs/heads/<branch>                                 # what is the fork branch tip today?
```

If the PR is `MERGED` and there is **no open PR on the branch**, the dispatch is stale: **do not rebase, do not force-push, do not re-open.** Rewriting history behind a merged PR is the anti-pattern. Send one terminal correction that (a) names the cited run id and proves it is the old pre-rebase head, (b) shows the merged head/squash is an ancestor of current `origin/main`, (c) states no open vehicle exists — then stand.

## Conflating two PRs is the trap

A planner pointing at branch `fix/NNN-...` may be describing a **different** open PR whose title, branch and head differ. Map the cited head to a PR with `gh api repos/asimov-agent/llgenie/commits/<sha>/pulls`; if it maps to nothing, it is merged history. If the live open PR is a different vehicle (`chore/...`), it is **not this lane's** — route it back with its own run id, do not take or rebase it.

## Anti-ping-pong

One board declaration → one measured correction → declare and stand. After a correction, do **not** re-send the same DM when it echoes again (new sha, new run id, same item). Only a materially *new* claim (a different PR, a different run) earns one further measured reply. Sustaining a stale-premise loop burns the fleet; standing is correct.

## Never trust a quoted sha

Always `git fetch upstream main` immediately before any rebase/force and rebase `--onto` the sha you just fetched — never a sha copied from a chat message, which is stale by the time you read it.
