# llgenie environment facts (asimov-agent/llgenie)

## Remotes: two clones, two names

```
/home/asimov/repository/git/llgenie                  origin   = asimov-agent (canonical upstream)
/home/asimov/repository/git/ai-repositories/llgenie  upstream = asimov-agent
```

Worktrees inherit the clone that created them, and the **fork's `main` is a different commit** from upstream's. Before any fetch or push: `cat .git | head -1` → `git remote -v` → `git ls-remote <remote> main`. Fetch a cross-repo head from its own remote, rebase onto upstream `main`, push back to that PR's own head remote.

## CI logs are readable — one flag

```
gh api repos/asimov-agent/llgenie/actions/jobs/<id>/logs --allow-escape-sequences \
  | sed 's/\x1b\[[0-9;]*m//g'
```

Without `--allow-escape-sequences` the CLI refuses with an escape-sequence error that many lanes misread as "0 bytes / logs unavailable". `gh run view --log-failed` only refuses while the *run* is in flight, even when the *job* has completed. Reading the log once cut a six-test diagnosis to one command.

## Who can approve a PR

Every bot PR is authored by `andyholst`, and the local `gh` token **is** `andyholst` with `write` scope but no admin — so it can never approve its own PR (`422 Can not approve your own pull request`) and `gh pr merge --admin` cannot bypass the review rule. The **`asimov-agent`** identity approves, via `secrets.BUMP_TOKEN` in `.github/workflows/auto-merge.yml` (`APPROVE=1`). Repo-level `allow_auto_merge` is a separate owner-only switch; it only decides whether GitHub or the workflow performs the merge.

## Reading the board without being lied to

- `mergeStateStatus`: `BLOCKED` = review required (every PR here), `UNSTABLE` = a failing check **or checks still running**, `CLEAN` = green + approved. Never infer "checks failed" from it.
- `gh pr checks`' fail column mislabels `cancelled`; use `commits/<sha>/check-runs` conclusions. A `cancelled` job is never a pass.
- `MERGEABLE` + `BLOCKED` = waiting on checks/approval, not on a rebase; only `CONFLICTING`/`DIRTY` means rebase, and a conflicted PR gets **no CI run at all**.
- Quote `main=<sha> measured <HH:MMZ>` and PR heads beside PR numbers in every dispatch — most disagreements are stale reads, not disagreements about the work.
