# Diagnosing a red CI job and proving the fix locally

Use when a PR check fails and you must explain it, or when a workflow/bot fix must be verified
before it is pushed. Repo-wide gate rules live in AGENTS.md; this is the working procedure.

## 1. Read the RIGHT run and the RIGHT job

```bash
gh run view <RUN> --repo <owner/repo> --json name,conclusion,jobs   # which job, which step
gh run view <RUN> --repo <owner/repo> --job <JOB_ID> --log-failed  # only the failing step
```

- A symptom in a *separate* workflow (auto-merge, run-failure reactor) has its own run list:
  `gh run list --repo R --workflow auto-merge.yml --limit 5 --json databaseId,createdAt,conclusion`.
  A `pull_request` run being green tells you nothing about a `workflow_run` workflow that reacted to it.
- A run whose `name` is the file PATH with **zero jobs** is a startup refusal (bad `${{ }}` in the
  file), not a failed job — chase the YAML, not the code the run would have tested.

## 2. Check what the branch or main ACTUALLY contains

A stale local checkout lies about CI: a job that "does not exist" in your working tree may exist on
`origin/main` in a different file, and vice versa.

```bash
git fetch origin main -q
git show origin/main:.github/workflows/<file>.yml | sed -n '/^  <job>:/,/^  [a-z]/p'
git ls-tree --name-only origin/main .github/workflows/
git grep -l '<STEP NAME>' origin/main -- .github/workflows/
```

GitHub runs a `pull_request` workflow from the PR's ref and a `workflow_run` workflow from the
**default branch**. So a PR cannot fix the gate that judges it (auto-merge, reactors): ship the fix,
merge it, and say plainly that the next PR is the live proof.

## 3. Actor/identity gates

- `github-actions[bot]` is a **GitHub App** login, never a collaborator:
  `gh api repos/R/collaborators/github-actions[bot]/permission` 404s. A guard that only accepts the
  owner or `admin|maintain|write` therefore refuses every PR the repo's own bot opened (a bot creates
  its PR with the job token when the PAT lacks Issues write).
- The safe widening is **same-repo head only**:
  `github.event.pull_request.head.repo.full_name == github.repository`. A same-repo head can only be
  produced by a token with write access; a bot actor on a foreign head (a bot comment/label on a
  stranger's fork PR also yields that actor) and on a non-PR event (no head repo) stay refused.
- Read the guard's intent comment before "fixing" behaviour: these comments routinely claim a bot is
  allowed while the code never allowed it. The comment is evidence, not the spec.

## 4. `gh` CLI traps that fake-`gh` fixtures never catch

- **`gh api` prints a 404's error BODY on stdout.** `n=$(gh api ... || true)` therefore yields
  `{"message": "Not Found", ...}` — non-empty, so a `[ -z ]` fallback never fires, and the blob later
  breaks `$GITHUB_OUTPUT` (`Invalid format`). Treat a value as a number/ID **only when it is digits**:
  anything else is "no answer" and falls through. Never let a command's raw stdout reach
  `$GITHUB_OUTPUT` unvalidated, and keep it one line.
- **`gh pr view --json` field names are a closed set.** A name it does not have (e.g.
  `authorAssociation`) fails the call with `Unknown JSON field`, which kills the whole step. Verify a
  field list against the real binary before shipping: `gh pr view <n> --repo R --json <list>`.
- A fake `gh` on PATH that ignores the `--json` argument will happily accept an invalid field, so a
  green suite proves nothing about it. When a fake is the stand-in, add one case that asserts the
  requested field/flag vocabulary (or probe the real binary), or the class of bug is invisible.

## 5. Prove a fix in a test that runs the real logic

- Prefer extracting shell logic out of a workflow into a script/make target with a test that runs it
  against a real fake external binary on PATH (real `subprocess`, real parsing). Text assertions on
  YAML are the fallback, not the first choice.
- Prove the OLD artifact fails the new test: run the new test against `git show origin/main:<file>`
  (write it to a temp path) or a temp copy of the old recipe, and show exit 1 vs exit 0. A test that
  passes on both is vacuous.

## 6. Makefile recipes differ per host — never assert one host's shape everywhere

llgenie's Makefile branches on `HOST_OS` (Linux: container via `TEST_RUN`; macOS: the native 3.11
venv), so a test that asserts `-v "<checkout>":/repo:rw` and the image name only holds on Linux.

- Assert the **variable** both hosts resolve, not one host's expanded recipe:
  `make -p -n <target> VAR=value | grep '^TEST_OPTS '` (the `:=`/`=` inside the value is harmless if
  you split on the first `=`).
- Expand the other host's branch locally: `make -e HOST_OS=Darwin -n <target>` — a plain
  `HOST_OS=Darwin make ...` does NOT work, because a makefile `:=` assignment overrides the
  environment and only `-e` gives the environment precedence.
- To exercise a test's Darwin branch on Linux, drive the module with `platform.system` patched and a
  `subprocess.run` wrapper that inserts `-e HOST_OS=Darwin` for `make` argv, then call the test
  functions directly. Report it as a simulation; the CI macOS job is the real proof.

## 7. Edit only the worktree

`execute_code` runs in the **session** working directory, not the worktree you just created: a
relative `Path(".github/...")` silently edits the user's checkout (and `make` targets there). Use
absolute worktree paths in `execute_code`, or a `cd <worktree> && ...` in `terminal`. If it happens,
`git checkout -- <paths>` in the user's checkout immediately and redo the edit in the worktree.

## 8. Closing the loop

Run the repo's gates before pushing (`make lint`, `check-docs`, `check-wiring`, `check-workflows`,
`make openspec-validate NAME=<change>`, plus the focused `pytest`), push, then poll the PR's run with
`gh run view <RUN> --json jobs -q '[.jobs[]|select(.conclusion!="success" and .conclusion!="skipped")]'`
— and report the failing job's real output, never a guess. The agent never merges: report the PR URL
and let CI or a human land it.
