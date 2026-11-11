# Worktree/branch hygiene and repo gate quirks (llgenie)

Rules for cleaning up after many agent PRs, wiring a new make target, and reading llgenie's
gate output. Each rule is a mechanism (why) plus the command that works.

## A squash-merged branch is never an ancestor of main

Never decide "did this branch land?" from ancestry, `git branch --merged`, or `git branch -d`:
llgenie squash-merges, so the squashed commit on `main` is a new commit and the branch tip stays
unreachable forever. The only durable proof is the PR's merge commit.

```bash
gh pr list --repo asimov-agent/llgenie --state all --limit 500 \
  --json number,state,headRefName,mergeCommit      # head -> number/state/mergeCommit.oid
# prunable iff state == MERGED and
git merge-base --is-ancestor <mergeCommit.oid> origin/main
```

Deleting: `git worktree remove <path>` (no `--force`, so a dirty tree stops you) and only then
`git branch -D <branch>`. Never delete the branch first — a failed worktree removal then strands a
directory with no ref.

Keep, with the reason printed, so the result is auditable:

- a branch naming an OPEN or CLOSED (unmerged) PR, or no PR at all — a human judges those;
- a merge commit that is not on the base (GitHub says merged, the base disagrees);
- a **dirty** worktree (uncommitted changes are the only way a prune loses work);
- a **detached-HEAD** worktree — it holds no branch, so no merge licenses deleting it;
- the repository's **main checkout** (always the first `git worktree list --porcelain` block).

## Worktrees that refuse to be deleted (root-owned files)

Containerized stages run as root and write `__pycache__/*.pyc` and `.pytest_cache/` into the mount,
so `git worktree remove` fails `error: failed to delete '<path>': Permission denied` **after** git
already unregistered the worktree — the branch is gone and the directory stays. `find <root> -not
-user "$(id -u)"` tells you the scale. When sudo is not passwordless on the host, delete the
leftovers with a root container over the parent directory (explicit names, never a glob):

```bash
docker run --rm -v "$PWD:/wt" -w /wt llgenie/test:latest \
  sh -c 'for d in dir-a dir-b; do rm -rf -- "$d"; done'
```

Prevent it instead of repairing it: add `--user "$(id -u):$(id -g)" -e HOME=/tmp` to ad-hoc
docker runs, and keep `sudo` out of the loop (it prompts, which a non-interactive tool call cannot
answer).

## The openspec container also runs as root

`make openspec-new NAME=<kebab>` creates `openspec/changes/<name>/` owned by root, so writing
`proposal.md`/`specs/**/spec.md`/`tasks.md` fails `Permission denied` on the temp file.
chown it through a root container first, then write:

```bash
docker run --rm -v "$PWD:/w" -w /w alpine:latest chown -R "$(id -u):$(id -g)" openspec/changes/<name>
```

`make openspec-validate NAME=<name>` must exit 0 before any "done" claim.

## `REPO` is the checkout path, not a GitHub slug

The Makefile defines `REPO := $(shell pwd)`. A recipe that writes
`--repo $(if $(REPO),$(REPO),asimov-agent/llgenie)` can never fall back: `REPO` is always set, so
`gh` receives an absolute path and dies with `expected the "[HOST/]OWNER/REPO" format`. Give a new
gh-facing target its own variable (`SLUG=`, default `asimov-agent/llgenie`) and never pass
`$(REPO)` where `gh` wants `owner/name`. (`issue-cleaner-scan`, `issue-cleaner-apply` and
`queued-alarm` currently carry that collision; do not copy their shape.)

## Wiring a new make target (what the guards demand)

- a `##` help line on the target — `make check-docs` fails a user-facing target the README does
  not name, and also fails a `tests/fixtures/docs-exceptions.json` entry that went stale;
- a `.PHONY:` entry — `make check-wiring` fails an un-declared target shadowed by a file of its name;
- a `scripts/` entry point behind it — the wiring guard also fails a script no CI-reachable target
  runs;
- a README line in the same commit, plus a dated `agent-wiki/` entry naming its issue and PR
  (`check-docs` fails an entry with neither).

The `.PHONY:` block is one `\`-continued list: a test asserting membership by scanning lines that
start with `.PHONY:` misses everything after the first line. Join the continuation lines before
asserting.

## Running and reading the gates

One test file, fast, without leaving root-owned artifacts (~1 s vs ~12-13 min for the full suite):

```bash
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -v "$PWD:/repo" -w /repo \
  llgenie/test:latest python -m pytest tests/test_x.py -q -p no:cacheprovider
```

A failed CI job's log needs the escape hatch before it will print:

```bash
gh api --allow-escape-sequences repos/<owner>/<repo>/actions/jobs/<job-id>/logs \
  | tr -d '\033' | sed 's/\[[0-9;]*m//g'
```

Two reds that are NOT your change, with how to tell:

- **`linux / openspec` + `macos / openspec` failing in ~30 s**: `make openspec-tasks-check` found an
  unticked `- [ ]` in `openspec/changes/<name>/tasks.md` (`FAIL <name>: unchecked task checkbox(es) at
  lines [...]`). Tick every task — the verification one included, with measured numbers — before the
  push that you want green.
- **`make test-unit` failing only in `tests/test_trend_pick.py::test_readme_links_answer_and_a_broken_copy_is_caught`**
  with `HTTP Error 429`: that test fires one live Hugging Face request per README link and has no
  retry. Re-run the single test; if it passes in seconds the suite hit rate limiting, not a broken
  link, and the failure is unrelated to a change that touches no link, registry data or downloader.
