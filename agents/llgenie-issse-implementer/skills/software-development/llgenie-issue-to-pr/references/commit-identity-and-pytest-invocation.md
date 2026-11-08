# Commit identity and test-invocation pitfalls

Two failures that cost a full CI round on #1640 / issue #1638.

## 1. `check-pr-authors` rejects a lowercase bot name

The gate accepts exactly `Asimov Agent <support@docondee.com>` or `Mr. Asimov <support@docondee.com>`.
A commit authored as `asimov-agent` (lowercase) fails, even when the email is right.

Rewriting the author is fiddlier than it looks:

- Setting `GIT_AUTHOR_NAME`/`GIT_AUTHOR_EMAIL` in the environment before
  `git commit --amend` or `git rebase --reset-author` frequently does **not** change the
  authored-by identity that the gate reads back.
- The reliable fix is a rewrite of the range:

```bash
GIT_AUTHOR_NAME="Asimov Agent" GIT_AUTHOR_EMAIL="support@docondee.com" \
git filter-branch -f --env-filter '
  export GIT_AUTHOR_NAME="Asimov Agent"; export GIT_AUTHOR_EMAIL="support@docondee.com";
  export GIT_COMMITTER_NAME="Asimov Agent"; export GIT_COMMITTER_EMAIL="support@docondee.com";
' -- origin/main..HEAD
```

Then:

```bash
git log --format='%ae | %an' origin/main..HEAD     # verify BEFORE pushing
python3 scripts/check_pr_authors.py check --base origin/main --head HEAD
git diff --stat <old-head> <new-head>              # must be EMPTY: identity-only rewrite
```

- `filter-branch` rewrites every sha in the range, so the push is a force-push. Fetch
  `origin/main` immediately before and use `--force-with-lease=<ref>:<previous-sha>`.
- Delete the backup refs the rewrite leaves behind (`git update-ref -d
  refs/original/refs/heads/<branch>`), or a later rewrite refuses to run.
- The PR head updates automatically; re-check CI at the new head — the old runs are stale.

## 2. An unquoted `-m` marker silently runs zero tests

In the docker pytest invocation, `-m not network` passes `network` as a positional path:

```
ERROR: file or directory not found: network
no tests ran in 0.00s
```

The command still exits **0**, so a background job's "completed normally (exit code 0)"
notification looks like a green gate when nothing ran. Always quote the marker:

```bash
docker run ... python -m pytest tests/ -m 'not network' -p no:cacheprovider -q ...
```

And judge a unit run by its tail (`<n> passed, <m> deselected`) plus a plausible duration
(the full llgenie unit suite takes ~8 minutes / ~495s), never by the exit code alone.

## 3. Linked worktree false-reds GATES, but the change's own unit tests run fine in it

The "never a linked worktree, always a standalone clone" rule governs **gate** runs: a
linked worktree mounted into the container false-reds every *git-dependent* gate. But the
change's own unit tests — modules that mock `subprocess` and read only the working tree —
run correctly in the linked worktree. Running them by node id is the cheapest first proof
of the change, before you bother cloning:

```bash
docker run --rm -u root --network host \
  -v /var/run/docker.sock:/var/run/docker.sock -v "$PWD":"$PWD":rw -w "$PWD" -e HOME=/tmp \
  llgenie/test:latest python -m pytest tests/test_x.py::test_the_behaviour -p no:cacheprovider -q
```

- The docker socket is needed only if the target test itself shells out to docker.
- Quote bare node ids; prefer the dedicated behaviour tests that assert THIS change over a
  broad run — a `3 passed in 0.03s` at the current head is the crisp, non-fabricated proof
  to quote when a full sweep/AC is externally blocked.
- Match the module paths the repo uses (e.g. `tests/test_engine_*.py`), and treat the pass
  count as the evidence — not the exit code (see §2).
