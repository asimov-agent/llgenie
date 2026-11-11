# The bots' workflows: starting one by hand, and reading why it did not run

The repository's bot workflows (`issue-bot`, `fix-bot`, `issue-refiner`, `rebase-bot`,
`run-failure-reactor`, `registry-sync`, `engine-bump*`) share one shape: guard → a
`make <bot>-…` decision → the agent image → a verdict/PR leg, never a merge. Most "the bot does
not work" questions are answered by one of the checks below, in this order.

## 1. Can it be started at all?

`gh workflow run <file>` fails **before a run exists** when a dispatch input is required:

```
HTTP 422: Required input '<name>' not provided
```

Read `workflow_dispatch.inputs` first. A bot whose schedule picks its own work almost always already
supports a manual "pick one yourself" run — the declared default is what decides:

```bash
grep -n -A6 'workflow_dispatch:' .github/workflows/<bot>.yml
make -n <bot>-dispatch FORCE_ISSUE=      # does an empty value omit the flag, or pass an empty one?
```

A `required: true` input with `default: ""` is the defect: the capability exists behind a form that
refuses it. The fix is `required: false` plus a description that states what blank does, and the same
sentence in the file's `Trigger surface` header, because that header is the contract a dispatcher
reads. Keep the pinned path (`-f <input>=<value>`) working.

Do NOT assume the pick logic is missing — check the dispatcher's default (`force_issue: int | None`
with `None` meaning "pick" is the common shape) before writing any.

## 2. Does the run survive its first gate?

A bot run that fails in about a second never reached the actual work: a leg's pre-flight (smoke, JEV
preflight, credential check) stopped it. Read the step that failed, not the job status:

```bash
gh run view <run-id> --json jobs --jq '.jobs[]|"\(.name) \(.conclusion)"'
gh run view <run-id> --log-failed | tail -40
# the job log with escape codes stripped, when gh refuses the log for escape sequences:
gh api --allow-escape-sequences repos/<owner>/<repo>/actions/jobs/<job-id>/logs \
  | tr -d '\033' | sed 's/\[[0-9;]*m//g' | grep -i -E 'fail|error|Traceback' | head -20
```

A 0-job run whose `name` is the file path is a **startup** refusal (a YAML/expression GitHub could
not parse), not a failed step — a different bug class entirely.

## 3. A precondition must not require its own product

A gate that asserts a path exists BEFORE the action that creates it can never pass on a fresh image:

```
[hermes-smoke] FAIL: no transcript at /root/.hermes/state.db - Hermes wrote no session
```

`state.db` is what a successful `hermes` run CREATES, and the agent image ships without it, so the
check refused the very run that would have written it. The rule: run the action first, then judge what
it left (absent / unreadable / no new record are each loud, named failures). Prove it against the real
image rather than by reading:

```bash
docker run --rm <image> sh -c 'test -f <the path> && echo EXISTS || echo MISSING'
```

## 4. The slug a recipe hands to `gh`

`Makefile` defines `REPO := $(shell pwd)` globally, so a recipe written as `--repo $(REPO)` passes an
absolute path and every `gh` call dies with
`expected the "[HOST/]OWNER/REPO" format, got "/home/…"` — including the "default" half of
`$(if $(REPO),$(REPO),<slug>)`, which can never apply because `REPO` is always set. Give the slug its
own variable (`SLUG=`), and pin it with a test that asserts the recipe never forwards `$(REPO)` to
`gh`.

## 5. The guards a workflow change must keep green

```bash
make check-workflows          # every YAML parses, top-level name, trailing newline
make check-dispatch-forms     # name states the work, every input documented (+default or required:true),
                              # header block present, README table current
make dispatch-forms-report    # prints the table — paste it between the markers, never hand-edit
make openspec-tasks-check     # FAIL <change>: unchecked task checkbox(es) at lines [N]
```

`openspec-tasks-check` runs in BOTH the `linux` and `macos` openspec jobs: a change whose last task is
still unticked reddens the PR even when every other gate is green. Tick the verification task in the
same commit that verifies it, and say in the PR body which push fixed it.

## 6. What a manual run still cannot prove

`workflow_dispatch --ref` only accepts a ref that exists in the BASE repository, so a branch that lives
on the fork cannot be dispatched upstream: `HTTP 422: No ref found for: <branch>`. Prove the form with
tests + `check-workflows`, and name the post-merge acceptance check in the PR body
(`gh workflow run <file>` with no input) instead of claiming a run you never made.
