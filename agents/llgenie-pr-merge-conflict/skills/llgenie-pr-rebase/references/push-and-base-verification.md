# Verifying a rebase push actually landed

Rules for the push/verify/report boundary of a rebase. These are gates, not
optional checks: a rebase is not done until the wire proves it, and a report is
not true until it is measured after the push.

## 1. Prove the push landed before you report it

A `git push` that is rejected — non-fast-forward, lease mismatch, protected
ref — can still return without aborting the surrounding shell, and if you only
read the later log lines you will believe it succeeded. Before any "pushed
`<sha>`" claim:

```sh
git push --force-with-lease=<remote-ref> <remote> <local>:<remote-branch>
echo "push rc=$?"                                   # must be 0
git ls-remote <remote> refs/heads/<remote-branch>    # must equal local HEAD
# or, via API:
gh api repos/<owner>/<repo>/pulls/<n> --jq .head.sha
```

Require the remote head to EQUAL your local HEAD. Reporting a sha that never
left the machine forces a retraction on every durable record (PR comment, inbox
trail), and a retracted "pushed" claim poisons the next report. The wire is the
only proof of a push; a local `git rev-parse` of the prepared branch is not.

## 2. `base.sha` is not proof the branch is cut from main

`check-pr-base` requires `git merge-base <head> origin/main` to EQUAL
`origin/main` itself. A branch can show `base.sha == main` in the PR API yet red
the guard, because its merge-base is an OLDER main commit — the branch was
re-cut onto a stale tip, or stacked on another base that has since merged.

```sh
test "$(git merge-base <head> origin/main)" = "$(git rev-parse origin/main)" \
  && echo cut-from-main || echo NOT-cut-from-main
```

Run this — not a `base.sha` comparison — before claiming "base == main" or
"rebase clean". `base.sha` reflects the PR's declared base; the merge-base
reflects the commit graph the guard actually tests.

### `check-pr-base` lives in `ci.yml` and runs AFTER the guard — read its verdict locally

The guard job is a chain of `make check-pr-<gate>` steps and stops at the first red, so a red earlier
in the chain means `check-pr-base` **never executed** and its absence from the log is not a pass.
Prove it directly at the pushed sha in the worktree:

```bash
make check-pr-base PR_BASE=origin/main
# [check-pr-base] OK: `HEAD` is cut from `origin/main` (merge-base == base)
```

### Fixing one gate UNMASKS the next one — a newly-appearing red is not your regression

Because the chain stops at the first failure, a branch can carry a second, older red that was never
reported. Clearing the first (for example re-stamping `agents-line`) lets the run proceed until the
next gate reds — `check-pr-openspec-change` or `check-docs`' `change->note` — and that red looks new
even though it shipped with the branch. Attribute before you apologise for it: re-run the newly-red
gate against the branch's **original head** (`git worktree add --detach /tmp/attr <original-sha>`), and
if it reds identically there it is pre-existing branch content, disclosed on the PR and routed to the
author lane — never "caused by the rebase".

## 3. Anchor main on the freshly-fetched ref, never a clone's local main

A shared working clone's local `refs/heads/main` can be a stray or stale sha
that no longer matches upstream. Fetch the canonical remote explicitly and
re-verify against the API before branching, rebasing, or citing the sha:

```sh
git fetch <canonical-url> +refs/heads/main:refs/remotes/origin/main
gh api repos/<owner>/<repo>/commits/main --jq .sha   # must match what you fetched
```

`asimov-agent/llgenie` is the canonical upstream; a fork named `origin` is not.

## 4. A rejected lease means another actor moved the branch — stop

Rejection is information, not an obstacle to route around. Re-fetch, check
whether the branch is already MERGEABLE or already re-cut (the other lane may
have done the right thing), report the transition, and stop. Never escalate a
rejected `--force-with-lease` to a bare `--force` — that overwrites another
lane's live work. If the branch is another lane's recent push
(last-pusher-owns-the-head), do not force over it; report and let the owner
lane re-cut, or offer your prepared sha and wait for a go-ahead.
