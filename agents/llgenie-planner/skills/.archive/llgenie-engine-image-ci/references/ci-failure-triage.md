# Triage a red llgenie PR, read its logs, and reproduce it locally

Use when a PR on the repo is red or "blocked" and you must decide whether the code is wrong,
the pipeline is racing itself, or the change simply cannot publish.

## 1. Separate "queued" from "failing" before touching anything

`gh run list --commit <sha>` reports the RUN's status, and one queued job (macOS runners are
scarce) makes the whole run read `queued/` while 20+ jobs have already finished — some red. Never
triage from the run status.

```bash
gh pr checks <n> --repo <owner>/<repo> | grep -Ei 'fail|pending'
gh run view <run> --repo <owner>/<repo> --json jobs \
  --jq '.jobs[] | select(.conclusion=="failure") | "\(.name)\t\(.databaseId)"'
```

A PR with no `fail` line is queued, not broken. Say so instead of "fixing" it.

## 2. Read a job's log while its run is STILL in progress

`gh run view --job <id> --log-failed` refuses with "run … is still in progress; logs will be
available when it is complete". The check-run annotations only say `Process completed with exit
code 2`. The job log endpoint works anyway:

```bash
gh api repos/<owner>/<repo>/actions/jobs/<job_id>/logs --allow-escape-sequences \
  | sed 's/\x1b\[[0-9;]*m//g' | grep -E 'FAILED|AssertionError|Error:|failed,' | head -20
```

## 3. Classify the failure before writing any fix

Three shapes look identical in a PR's check list and need opposite responses:

| Symptom in the log | Real cause | Response |
|---|---|---|
| `[install] FAIL <engine>/cpu: … was never published (HTTP 404)` and `test_ci_publish_order.py::test_every_image_install_pulls_is_published` | the unit gate asks GHCR for the tag its own run is still building (engine-bump PR) | not the PR's code: rerun once the tag is published, or land the deferred-tag fix and rebase the branch |
| `denied: installation not allowed to Write organization package` on `make push-engine` | fork head + `pull_request` token scoped read-only to the base repo | not the PR's code: it cannot publish by design; the image is published by the run that lands it |
| one test failing on macOS only, in a network/download-heavy acceptance test | the runner is slower than the test's own subprocess timeout | reproduce the single test locally with the real network; if it passes, it is a flake — rerun the job |

A rerun is only possible after the whole run completes (`gh run rerun <run> --failed` says
"cannot be retried" while siblings are queued).

## 4. Reproduce one test locally in the worktree (same command shape as CI)

Copy the docker invocation `make -n test-unit` prints — it mounts the **parent clone** so a
worktree's `.git` file resolves:

```bash
make -n test-unit          # take TEST_RUN from here
cd ../llgenie-wt/<name> && docker run --rm -u root \
  -v "$PWD":/repo:rw -w /repo -e HOME=/root \
  -v "/path/to/main/clone":/path/to/main/clone:rw \
  llgenie/test:latest python -m pytest tests/<file>.py -q
```

Dropping the parent-clone mount makes every test that shells `git show origin/main:<path>` fail,
and the failure reads like a product bug (an empty deferral set, a wrong base). Add the mount
before you believe the result.

## 5. Worktree mechanics that silently invalidate a check

- `make openspec-new` runs the CLI in the container: the new change dir is **root-owned**. Fix it
  before writing `proposal.md`/specs/tasks: `sudo chown -R "$(id -u):$(id -g)" openspec/changes/<name>`.
- `git checkout <path>` restores from the INDEX, not HEAD. After `git add -A`, use
  `git restore --source=origin/main --staged --worktree <path>` to actually revert a file —
  otherwise your "old tree" still has the change and the negative proof is meaningless.
- Prove a new guard test really fires: restore the old file as above, run the test, see it FAIL,
  restore yours, run it again. Otherwise you have only shown that a test passes.
- Before any push, `git merge-base --is-ancestor origin/main HEAD`; `main` moves while CI runs
  (another PR merges mid-session). Rebase, then `git push --force-with-lease` on your own branch.

## 6. Where a scenario decision may live

`tests/test_ci_images.py::test_no_ci_step_or_job_is_skipped` requires every job/step `if:` in
`ci.yml`/`pipeline.yml`/`published.yml` to be one of a small allowlist (the `none`-matrix
placeholder skip, an OS guard, `always()`). A new scenario-scoped `if:` — even a correct one such
as "only a head that can write may publish" — fails that guard. Put the policy in the make target
or the Python script (`scripts/engine_image.py`), where it is one code path and hermetically
testable, and keep the workflow step unconditional.

## 7. Shell portability inside tests

The macOS CI job runs GNU Make **3.81**, which has no `--eval`. A test that needs an ad-hoc make
target must feed it on stdin, which every GNU Make supports:

```python
subprocess.run(["make", "-s", "-f", "Makefile", "-f", "-", "print-var"],
               input="print-var: ; @echo $(VAR)\n", capture_output=True, text=True, cwd=REPO)
```

Linux ships Make 4.x, so an `--eval` test passes locally and reds only on macOS.
