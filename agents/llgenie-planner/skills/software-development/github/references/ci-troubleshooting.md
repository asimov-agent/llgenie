# CI Troubleshooting Quick Reference

Common CI failure patterns and how to diagnose them from the logs.

## Reading CI Logs

```bash
# With gh
gh run view <RUN_ID> --log-failed

# With curl — download and extract
curl -sL -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/$GH_OWNER/$GH_REPO/actions/runs/<RUN_ID>/logs \
  -o ~/.hermes/cache/scratch/ci-logs.zip && unzip -o ~/.hermes/cache/scratch/ci-logs.zip -d ~/.hermes/cache/scratch/ci-logs
```

**Per-JOB logs when `gh api .../jobs/<id>/logs` refuses to print them.** That
endpoint's text carries ANSI colour codes and `gh api` bails before emitting any
of it: `the response contains terminal escape sequences; pass
--allow-escape-sequences to output it anyway`. Piping to `sed` does not help —
the check runs before any output. Use curl with the same token and strip the
escapes yourself; this is also the fastest read of ONE job while the rest of the
run is still unfinished:

```bash
export TOKEN=$(gh auth token)
curl -sSL -H "Authorization: Bearer $TOKEN" \
  "https://api.github.com/repos/<owner>/<repo>/actions/jobs/<JOBID>/logs" \
  | sed -e 's/\x1b\[[0-9;]*m//g' | grep -vE '^\s*$' | tail -60
```

Job ids come from `gh pr view <N> --json statusCheckRollup` (each `detailsUrl`
ends in `/job/<id>`) or `gh run view <RUN> --json jobs`. Anchor the grep on the
assertion, not the noise: `grep -nE 'FAIL|Error|assert|Traceback|passed'`.

**A run that is `failure` but shows NO jobs.** When `gh run view` reports a
failed run whose job list is empty (or all `skipped`), and `--log-failed`
returns nothing, the run did NOT fail inside a job — it failed at WORKFLOW
COMPILE. The only evidence is an annotation on the run, which `gh` does not
surface. Fetch the check-runs API: it carries the annotation in each check
run's `output.title` / `output.summary` (e.g. `Invalid workflow file ...
Unrecognized named-value: 'matrix'`, at a `file#L<line>,Col<col>`):

```bash
SUITE=$(gh api "repos/<owner>/<repo>/actions/runs/<RUN_ID>" --jq .check_suite_id)
gh api "repos/<owner>/<repo>/check-suites/$SUITE/check-runs" \
  --jq '.check_runs[] | {name,conclusion,status,output:.output.title}'
```

Check `latest` in the check-suite: `0` check runs + a failed conclusion is a
sure sign the workflow never compiled. The run page's `workflow` tab (rendered
HTML, fetch with a browser/extractor) also prints the annotation. Fix the
workflow file, then re-run — a compile failure never generates a retryable
job log.

---

## Answering "why is this PR failing?" (triage order)

1. **One call, every verdict:**
   `gh pr view <N> --repo <o>/<r> --json number,title,state,mergeStateStatus,statusCheckRollup`,
   then read the names only: `-q '.statusCheckRollup[] | "\(.conclusion)\t\(.name)"'`.
   `mergeStateStatus: BLOCKED` + a handful of red checks means the required checks
   ARE the answer; do not go looking for branch-protection causes.
2. **Only the failing jobs' logs**, by job id (recipe above). Identical
   assertions on two OS legs (`linux / unit` and `macos / unit`) are ONE bug —
   say both legs fail identically instead of writing it up twice.
3. **Tell a repo guard from a broken test.** A message that names the artifact
   and the command that regenerates it ("... is stale — regenerate it with
   `make <x> report`", "... files missing a trailing newline") is the repo's own
   consistency guard firing on YOUR diff, and it usually states the fix. Read
   that as "the change is incomplete", not "something is broken".
4. **Reproduce the guard against the PR head; never regenerate blind.**

```bash
git fetch -q origin pull/<N>/head:pr<N> && git worktree add /tmp/pr<N> pr<N
```

   Then run the failing check there. For a stale-generated-artifact guard, DIFF
   the freshly generated artifact against the committed block — that prints the
   one row that changed, where pasting the whole regeneration hides it:

```bash
cd /tmp/pr<N> && python3 - <<'PY'
import sys, difflib; from pathlib import Path
repo = Path('.').resolve(); sys.path.insert(0, str(repo / 'scripts'))
import check_dispatch_forms as cdf          # the module the guard test imports
new = cdf.table(repo).rstrip('\n').split('\n')
old = (repo / 'README.md').read_text().split(cdf.BEGIN)[1].split(cdf.END)[0].strip('\n').split('\n')
print('\n'.join(difflib.unified_diff(old, new, 'committed', 'generated', lineterm='', n=1)))
PY
```

5. **Group by cause before reporting.** One diff commonly trips 4–5 unrelated
   guards at once (a trailing newline in each new file, an env-var allowlist, a
   time-budget arithmetic assertion, a regenerated doc table). Give one bullet
   per cause: what asserted, why this diff broke it, the exact one-line fix and
   the file it lives in. Do not narrate the log, and do not offer to "rerun CI".

---

## Common Failure Patterns

### Test Failures

**Signatures in logs:**
```
FAILED tests/test_foo.py::test_bar - AssertionError
E       assert 42 == 43
ERROR tests/test_foo.py - ModuleNotFoundError
```

**Diagnosis:**
1. Find the test file and line number from the traceback
2. Use `read_file` to read the failing test
3. Check if it's a logic error in the code or a stale test assertion
4. Look for `ModuleNotFoundError` — usually a missing dependency in CI

**Common fixes:**
- Update assertion to match new expected behavior
- Add missing dependency to requirements.txt / pyproject.toml
- Fix flaky test (add retry, mock external service, fix race condition)

**When a legitimate argument is inserted into a pinned command, fix the assertion — not the command.**
A test that pins a CONTIGUOUS string (`"scripts/a.sh && scripts/b.sh" in recipe`) reds the moment the
change puts anything between the two (`a.sh && VAR="$(X)" b.sh`), even though the invariant — a runs before b,
in one invocation — still holds. Assert the invariant instead: `recipe.index(a) < recipe.index(b)` plus
containment of both inside the same `bash -lc '…'` segment. Keep the strict half (both present, correct order,
same shell) so the check still fails when a command is dropped or moved; only the adjacency pinning goes.

**Stale test asserts the OLD workflow shape.** When a PR changes a workflow's
`on:` triggers (e.g. `push: ["**"]` → `pull_request` + `push` on `main`), a
test that locks the trigger contract (`assert list(triggers) == ["push"]`)
fails on every OS the unit job runs, even though the change is intentional.
Before changing a workflow's `on:` block, grep the test tree for the old
assertion and update it in the SAME commit — a CI-trigger change and its
contract test must land together or the unit job goes red.

**When `patch` keeps corrupting a block, use an exact python replace.** The
`patch` tool's fuzzy matching can re-indent or mangle a multi-line block it
keeps matching (extra indentation, doubled characters) even after several
retries. Stop retrying `patch`; do a precise string replace with a heredoc and
assert the old block is present, then re-check syntax:

```bash
python3 - <<'EOF'
p = "path/to/file.py"; s = open(p).read()
old = "...exact current text..."; new = "...corrected..."
assert old in s, "old block not found"
open(p, "w").write(s.replace(old, new))
EOF
python3 -c "import ast; ast.parse(open('path/to/file.py').read())"
```

Read the file fresh first so `old` matches the on-disk bytes exactly.

---

### Matrix jobs that can legitimately be empty — emit a `none` row, gate STEPS

A matrix job whose `include` list can legitimately be empty (e.g. a PR that
changes no engines) must never be left empty, because two separate GitHub
behaviours both bite here:

1. **An empty `include` list fails the WORKFLOW at compile** — before any job
   `if:` is evaluated — so the job never even gets a chance to skip itself.
2. **`matrix` is not a legal name in a job-level `if:`** — only in a step-level
   `if:`. A job-level `if: ${{ matrix.engine != 'none' }}` dies with
   `Unrecognized named-value: 'matrix'` and the run never starts.

So the durable fix is: make the matrix **never empty** by having the matrix
producer emit one `engine: none` placeholder row, and gate **every step** (not
the job) of the matrix job with the placeholder skip:

```yaml
strategy:
  matrix: ${{ fromJSON(needs.engine-matrix.outputs.matrix) }}   # always >= 1 row (one is 'none')
steps:
  - uses: actions/checkout@v4
    if: ${{ matrix.engine != 'none' }}   # steps skip the none row, build nothing
  - name: build
    if: ${{ matrix.engine != 'none' }}
    run: make build-engine
```

Keep the job-level `if:` to event/needs conditions only — never reference
`matrix` there. A skipped step's job still shows green while doing nothing for
the placeholder row.

Do NOT use `continue-on-error` for the skip: it is illegal on a `uses:`
(reusable workflow call) job — GitHub stops treating the job as a workflow call
and then reports `uses`/`with` unexpected and `runs-on` missing.

When a unit test asserts "no CI job or step is skipped", update its contract in
the SAME commit as the workflow change or the unit job goes red on every OS:
allow exactly the `${{ matrix.engine != 'none' }}` step skip plus the allowed
job checks (`!cancelled()`, `always()`, `runner.os`, `github.event_name`, a
needs result), and no other job skip.

---

### A live-network job reds with a traceback naming `ssl.py` — the retry loop never saw it

`TimeoutError: The read operation timed out`, raised through `http/client.py` → `socket.py` → `ssl.py`, is a
CONNECT-ESTABLISHED read timeout. In Python 3.10+ `socket.timeout` **is** the builtin `TimeoutError`, and it
is NOT a `urllib.error.URLError` subclass (`issubclass(TimeoutError, urllib.error.URLError)` → `False`;
`URLError` wraps the connect phase only). So a retry loop written `except urllib.error.URLError:` never sees
it: the exception escapes, the CLI exits 1, and the acceptance test reports "must exit 0". Triage it as a
defect in the retry seam, not as a flake to re-run — fix `except (urllib.error.URLError, TimeoutError):` on
the same backoff/budget, and prove it with a REAL local server that accepts the connection and then answers
nothing (stall retried; exhausted budget raises the seam's own message; `TimeoutError` never escapes). Grep
the sibling seams in the same repo for the same omission — one path catching both classes while another
catches only `URLError` is the usual shape.

---

### Lint / Formatting Failures

**Signatures in logs:**
```
src/auth.py:45:1: E302 expected 2 blank lines, got 1
src/models.py:12:80: E501 line too long (95 > 88 characters)
error: would reformat src/utils.py
```

**Diagnosis:**
1. Read the specific file:line numbers mentioned
2. Check which linter is complaining (flake8, ruff, black, isort, mypy)

**Common fixes:**
- Run the formatter locally: `black .`, `isort .`, `ruff check --fix .`
- Fix the specific style violation by editing the file
- If using `patch`, make sure to match existing indentation style

---

### Type Check Failures (mypy / pyright)

**Signatures in logs:**
```
src/api.py:23: error: Argument 1 to "process" has incompatible type "str"; expected "int"
src/models.py:45: error: Missing return statement
```

**Diagnosis:**
1. Read the file at the mentioned line
2. Check the function signature and what's being passed

**Common fixes:**
- Add type cast or conversion
- Fix the function signature
- Add `# type: ignore` comment as last resort (with explanation)

---

### Build / Compilation Failures

**Signatures in logs:**
```
ModuleNotFoundError: No module named 'some_package'
ERROR: Could not find a version that satisfies the requirement foo==1.2.3
npm ERR! Could not resolve dependency
```

**Diagnosis:**
1. Check requirements.txt / package.json for the missing or incompatible dependency
2. Compare local vs CI Python/Node version

**Common fixes:**
- Add missing dependency to requirements file
- Pin compatible version
- Update lockfile (`pip freeze`, `npm install`)

---

### Permission / Auth Failures

**Signatures in logs:**
```
fatal: could not read Username for 'https://github.com': No such device or address
Error: Resource not accessible by integration
403 Forbidden
```

**Diagnosis:**
1. Check if the workflow needs special permissions (token scopes)
2. Check if secrets are configured (missing `GITHUB_TOKEN` or custom secrets)

**Common fixes:**
- Add `permissions:` block to workflow YAML
- Verify secrets exist: `gh secret list` or check repo settings
- For fork PRs: some secrets aren't available by design

### A fork head cannot publish — the row reds AFTER it built and tested

A workflow that PUBLISHES on `pull_request` (pushes an image to GHCR, a
package, a registry) runs on a fork PR with the fork's read-only token. The
build and the post-build test PASS, and then only the publish step fails:
`denied: installation not allowed to Write organization package` or
`permission_denied: The token provided does not match expected scopes`. The
artifact is fine; the identity is not — confirm with
`gh pr view N --json isCrossRepository` before touching any code.

Fix the identity, not the step: push the branch into the BASE repo and point
the PR at a same-repo head (`gh pr create --repo <base> --head <branch>`, or
`gh pr edit` to re-point), which gets a write token. Never make a fork PR
"green" by adding `continue-on-error` / `if: fork==false` to the publish step —
that silently stops publishing for every PR.

**Checks are pinned per sha, not per PR.** Re-pointing the PR at a same-repo
branch that holds the SAME commit leaves the earlier fork run's red checks
attached to that sha, so the PR still reads red with no new run. Push a NEW
commit (an empty commit is enough) so a fresh run reports on a new sha, then
confirm `gh pr view N --json headRefOid` equals what you pushed.

**Workflow `GITHUB_TOKEN` cannot create PRs — the run goes red but the branch
push already succeeded.** When a workflow's PR step fails with
`GraphQL: GitHub Actions is not permitted to create or approve pull requests
(createPullRequest)`, the repo setting "Allow GitHub Actions to create and
approve pull requests" (Settings → Actions → General) is OFF. The workflow
pushes the branch BEFORE it tries to open the PR, so the bump/commit work is
done and only the PR step failed. Do NOT re-run the workflow — recover by
creating the PRs yourself from the already-pushed branches with a token that
has `repo` scope:

```bash
# find the pushed branches the workflow created
gh api "repos/<owner>/<repo>/branches" --jq '.[].name' | grep <branch-prefix>
# for each: confirm no PR exists, then create it against main
gh pr list --repo <owner>/<repo> --head "<owner>:<branch>" --state all --json number
gh pr create --repo <owner>/<repo> --base main --head <branch> \
  --title "<commit subject>" --body "<body>"
```

Use the commit subject from `gh api repos/<owner>/<repo>/commits/<branch>` as
the PR title so it matches what the workflow would have titled it. The fix is
an admin action on the repo setting; until then, every run of that workflow
fails at the PR step and needs this manual recovery. The `gh` keyring token
usually has `repo` scope even when the workflow token does not.

---

### Timeout Failures

**Signatures in logs:**
```
Error: The operation was canceled.
The job running on runner ... has exceeded the maximum execution time
```

**Diagnosis:**
1. Check which step timed out
2. Look for infinite loops, hung processes, or slow network calls

**Common fixes:**
- Add timeout to the specific step: `timeout-minutes: 10`
- Fix the underlying performance issue
- Split into parallel jobs

### A job that "just stops" mid-step and the run ends `cancelled` — read the ANNOTATION and the step timeline, not the log

When a user reports "the download/step just stopped," do not assume a bandwidth wall. Pull the job's STEP
timeline and the run's ANNOTATIONS — both survive as JSON even when the log does not:

```bash
gh api repos/<o>/<r>/actions/jobs/<JOBID> \
  --jq '.steps[] | {n:.name[0:55], concl:.conclusion, started:.started_at[11:19], fin:.completed_at[11:19]}'
gh api repos/<o>/<r>/actions/runs/<RUN_ID> --jq '{conclusion,status,event,head_sha}'   # run-level
```

- **The dying step shows `conclusion: null` and every downstream step is `null` too** — they never ran. That
  step, not the last green one, is where the job died.
- **The annotations are the cause.** A job whose run concludes `cancelled` with
  *"The hosted runner lost communication with the server"* + *"The run was canceled by @github-actions[bot]"*
  did not hit a timeout or a slow network — the runner process itself dropped mid-step and GitHub cancelled
  the job. Raising `timeout-minutes` cannot fix this; the remedies are a re-run (the runner was unhealthy) or
  a lighter/self-hosted runner. A step that reached GitHub's own `timeout-minutes` instead shows
  *"The job running on runner … has exceeded the maximum execution time"* — that one IS the budget. Read which
  annotation fired before proposing a fix.
- **The raw log is often `BlobNotFound`.** GitHub retires raw job logs for killed/cancelled runs
  (`gh api .../jobs/<id>/logs` → an XML `<Error><Code>BlobNotFound</Code>`). That is NOT "no evidence" — the
  step timeline and run annotations above are the authoritative evidence, so quote them instead of inventing
  per-line progress you cannot read.
- **Separate a download problem from a CPU-bound build.** Before saying "speed up the download," check whether
  the pipeline already caches layers: a buildx build carrying `--cache-from type=registry,ref=…` +
  `--cache-to …,mode=max` reuses completed layers across runs, so a killed re-run inherits the cache and the
  long pole is the compile (e.g. a multi-hour `-e .` CUDA/ROCm install across many arches with `MAX_JOBS`), not
  the wire. Grep the build script for `cache-from`/`cache-to`/`no-cache` before diagnosing bandwidth. A died
  run contributes nothing to the cache (`cache-to` lands only on success), so "just re-run" only helps if
  PRIOR successful layers exist — say which.

---

### Docker / Container Failures

**Signatures in logs:**
```
docker: Error response from daemon
failed to solve: ... not found
COPY failed: file not found in build context
```

**Diagnosis:**
1. Check Dockerfile for the failing step
2. Verify the referenced files exist in the repo

**Common fixes:**
- Fix path in COPY/ADD command
- Update base image tag
- Add missing file to `.dockerignore` exclusion or remove from it

---

## Auto-Fix Decision Tree

```
CI Failed
├── Test failure
│   ├── Assertion mismatch → update test or fix logic
│   └── Import/module error → add dependency
├── Lint failure → run formatter, fix style
├── Type error → fix types
├── Build failure
│   ├── Missing dep → add to requirements
│   └── Version conflict → update pins
├── Permission error → update workflow permissions (needs user)
└── Timeout → investigate perf (may need user input)
```

## PRs that show "no checks reported"

A PR whose head branch lives in a FORK, against a base repo whose workflow
`on:` triggers only on `push` to the base repo's branches, gets NO CI run —
`gh pr checks` reports "no checks reported" and the run list stays empty. The
fork push only runs the FORK's Actions (which may sit queued forever), never the
base repo's workflow. The durable fix is to add a `pull_request` trigger to the
workflow's `on:` block so the UPSTREAM pipeline runs the PR and its checks
report on it:

```yaml
on:
  pull_request:
    branches: ["main"]    # fork PRs: upstream pipeline runs and reports checks
  push:
    branches: ["main"]    # merges: build + publish (if the workflow publishes)
```

If the workflow also publishes images to GHCR on `push`, keep `push` but scope it
to `main` only — never `branches: ["**"]`, or every bare feature-branch push
burns CI. A `push: ["**"]` + `pull_request` pair double-runs same-repo PRs; scope
`push` to `main` and let `pull_request` cover PRs. Verify the PR is actually
cross-repo before assuming the fork is the problem: `gh pr view N --json
isCrossRepository` (true = fork head).

## PR blocked with all reported checks green — a skipped `uses:` job hides required checks

When a PR is `BLOCKED` but every check you can see is green, the merge API is
the AUTHORITATIVE diagnostic — the ruleset API and GraphQL can both look clean
while the merge is still refused:

```bash
# The merge API names the blocker exactly:
curl -sS -X PUT -H "Authorization: Bearer $GITHUB_TOKEN" \
  "https://api.github.com/repos/<owner>/<repo>/pulls/<N>/merge" \
  -d '{"merge_method":"squash"}'
# -> 405 "4 of 14 required status checks are expected."
```

Do not trust `gh pr view --json mergeStateStatus` alone, the repo ruleset API
(`repos/<owner>/<repo>/rules/branches/main`), or GraphQL `statusCheckRollup`:
`statusCheckRollup` only lists checks that were REPORTED, never
expected-but-unreported ones, so it can show all-SUCCESS while the merge is
still blocked. The merge API is the one that tells you the real required-check
count.

**Root cause:** a job skipped via `if:` reports NO check names. When that job is
a `uses:` (reusable-workflow) caller whose child check names
(`parent / child-matrix-*`) are required by branch protection, the merge waits
forever on "Expected — Waiting for status to be reported" — the check never
exists to pass. This is distinct from the fork/no-trigger case above: the job IS
in the workflow, it just never runs on a PR.

**Fix:** make the job run on `pull_request` too, not only on `push`, so the
required check names actually report. For a reusable-workflow caller that
publishes images, run it on a PR against the already-published images (its
matrix producer is the `none` placeholder on a PR, so its steps skip and it
builds nothing):

```yaml
linux-published:
  needs: [engine-image, ci-images]
  if: ${{ !cancelled() && (github.event_name == 'pull_request' || needs.engine-image.result == 'success') }}
  uses: ./.github/workflows/published.yml
```

A skipped `uses:` job is the common case because it is the one that carries the
required check names — a skipped plain job just shows as skipped, but a skipped
reusable-workflow caller leaves its required child checks permanently
"expected". When you change the `if:`/`needs:` of such a job, update the
no-skip contract test in the SAME commit or the unit job goes red.

## Confirming a CI failure is pre-existing on main (not from your change)

Before spending time on a red job, prove it is not yours: `git show
origin/main:<file>` the file the failure points at (a vendored data file, a
fixture, a test) and check the offending value/link is present on main too. A
dead external link or a live-registry digest drift in a vendored/committed file
fails every PR identically — it is a pre-existing data/maintenance issue, not
this change. Verify your own new tests are in the "passed" count of the same
run, then report the red as inherited and file the root cause separately rather
than expanding the PR's scope to fix unrelated drift.

**When that drift reddens EVERY open PR, the fix is a small PR of its own — off the default
branch, not on top of a blocked PR.** Confirm the blast radius first (`gh pr checks <n>` per open
PR, plus the default branch's most recent run), then:

- **Fix the expectation, from the payload.** A live-data case must pin the invariant it exists
  for — the format and the repo, "the raw maximum is not the recommendation" — never an exact
  upstream filename or a measurement upstream may rename or re-measure. Which build a repo
  publishes is upstream's business.
- **When the premise loses its witness, assert the rule that still holds.** If the stronger half
  of an assertion has no subject left upstream (nothing in the live data matches it any more),
  say so in a comment and keep the invariant that does hold — never `skip` (a no-skip policy
  turns a skip into a failure anyway) and never widen a pass into a tautology.
- **Verify against the LIVE source before pushing**, by exact node id
  (`pytest path::test_name path::test_name -q`) — the live payload moving is the whole point.
- **Land it as its own PR closing its own issue, then rebase each blocked PR**
  (`git fetch origin main && git rebase origin/main && git push --force-with-lease`) so every PR
  picks the fix up in one move and the linkage stays on the fix's own PR.

## A job that fails in SECONDS, inside its own pre-flight, is a credential verdict

A job red inside the first minute at a step named `*-check` / `*-pre-flight` /
`make *-push-check` never reached the work it exists to do: the run is 30s where
the real job takes minutes, and every step after it is `skipped`. Read that
step's OWN line instead of hunting a build bug — the registry/API refused the
credential and named the reason (`permission_denied: The token provided does not
match expected scopes`, `Resource not accessible by integration`). Do not "fix"
this by re-running, and do not widen a credential on a hunch.

**Compare with the most recent GREEN run of the same workflow.** The diff
between the green and the red run IS the answer: a login step naming a different
secret, a different `-u`, a different `permissions:` block, a bumped action.

```bash
gh run list --workflow <wf> --limit 10 \
  --json databaseId,conclusion,headBranch,headSha,createdAt
gh run view --job <JOBID> --log | grep -iE "login|check|denied|403|401"
```

If a green run exists for the SAME step, the working shape is measurable — copy
it (the sibling job's secret + permission block) instead of theorizing. A green
run on a *branch* and a red one on `main` means the fix was written and proven
but never merged: search for it before writing code.

```bash
git log --oneline -S"<symbol or step name the failure prints>" -- <file>
git branch -a --contains <sha>                                  # where it lives
gh pr list --repo <o>/<r> --head <branch> --state all           # was it ever PR'd?
```

A commit pushed to a branch AFTER that branch's PR merged is STRANDED: not on
`main`, no PR carries it, and nobody will ever see it. Re-cut a fresh branch off
`origin/main`, cherry-pick it (plus whatever change record the repo requires),
and open its own PR instead of re-deriving the fix. Treat any justifying COMMENT
in the failing workflow as unverified prose: check its claim against the live
service (`gh api /users/<owner> --jq .type`, `gh secret list`) before believing
it.

## `gh` argument traps that surface as job failures

Two `gh` behaviours break a step in ways that look like logic bugs:

**`gh api` prints a 404's error BODY on stdout.** A command substitution with
`|| true` discards the exit status but keeps the output, so
`n=$(gh api .../pull_requests --jq . || true)` holds `{"message": "Not Found",
"status": "404"}` — non-empty, so a `[ -z "$n" ]` fallback never fires and the
multi-line blob later breaks `$GITHUB_OUTPUT`
(`##[error]Invalid format '  "message": "Not Found",'`). Accept a value only
when it is digits/well-formed, treat everything else as "no answer" and fall
through; never append raw command stdout to `$GITHUB_OUTPUT` unvalidated.

**`gh pr view --json` field names are a closed set.** A field it does not have
fails the whole call (`gh pr view N --repo R --json ... failed (1): Unknown JSON
field: "authorAssociation"`) and kills the step before any logic runs —
`authorAssociation` is a GraphQL concept, not a `gh pr view` field; read the
collaborator permission (`gh api repos/R/collaborators/<login>/permission`) or a
GraphQL query instead. Verify a field list against the real binary before
shipping it.

A fake `gh` on PATH that ignores the `--json`/flag arguments accepts anything,
so a green suite proves nothing about either trap: when a fake is the stand-in,
add a case that asserts the requested field vocabulary, or probe the real binary
once.

## Verifying a CI fix locally before pushing

- **Edit only the worktree, and give `execute_code` absolute paths.** A notebook-style
  kernel keeps the SESSION's cwd, not the worktree you just added, so
  `Path(".github/workflows")` silently edits the user's checkout. Use absolute
  worktree paths, or `cd <worktree> && …` inside a terminal call; if it happens,
  `git checkout -- <paths>` in the user's checkout immediately and redo it.
- **A recipe that branches per OS must be asserted per OS.** A Makefile with
  `HOST_OS := $(shell uname -s)` and an `ifeq` block expands differently on Linux (container)
  and macOS (native toolchain), so a test asserting one host's expanded command fails on the
  other. Assert the shared variable instead — `make -p -n <target> VAR=value` prints what
  make resolved (`grep '^TEST_OPTS '`) — and expand the other branch with
  `make -e HOST_OS=Darwin -n <target>`: only `-e` lets an environment variable win over the
  makefile's `:=`.
- **Prove the OLD artifact fails the new test.** Write `git show origin/main:<file>` to a temp
  path and run the new test (or the real script) against it: old fails, new passes. A test
  that is green on both proves nothing.

## A job that reds in SECONDS at a GUARD is an identity verdict

A `guard` job that fails before anything else — a few seconds, every other job skipped or never
started — is deciding WHO may run the workflow, not what the code does. Read its env block and its
refusal line before touching any code.

- `ACTOR: github-actions[bot]` with `Refused: ... permission: none` means the actor is a GitHub
  **App** login. An App login is never a repository collaborator, so
  `gh api repos/<r>/collaborators/<login>/permission` 404s and the guard's `|| echo none` becomes a
  refusal. A guard that must admit the repository's own bot has to do it explicitly **and**
  narrowly: admit the App login only when the run's head repository is this repository
  (`github.event.pull_request.head.repo.full_name == github.repository`) — a same-repo head can
  only be produced by a token with write access — while a bot actor on a FOREIGN head (a bot
  comment or label on a stranger's fork PR) and on a non-PR event (no head repo at all) stay
  refused.
- **A dispatched run's actor IS the dispatching token's identity.** `gh workflow run` with the job
  token yields a run whose `github.actor` is `github-actions[bot]`, so a guarded target workflow
  refuses the dispatch and the repair bot never runs. Dispatch with the owner PAT, passed by ENV
  NAME only (never argv, never a log line), defaulted from the ambient token for local use, and
  make a missing one a loud failure instead of a red no-op run nobody notices.
- **A re-run does not change the actor.** Replaying the same job re-evaluates the same token, so a
  refused bot run stays refused; the branch has to move (rebase + push, or a fresh dispatch with
  the right identity) before a new decision exists.
- **Grep every guard site before changing one.** Fan-out workflow fleets carry the same step
  verbatim, so a rule fixed in one file silently misses the others; keep them byte-identical and
  assert that in a test. Then prove the change by RUNNING the guard: extract its `run:` block,
  execute it under bash with a fake `gh` on PATH, and check every actor × head combination —
  reading the YAML asserts nothing about the decision.

## Polling the checks: an empty page is not a green page

`gh pr checks <n>` can transiently print NOTHING (the run has not registered its checks yet, or the API
hiccuped) and exit 0. A poller that stops as soon as it sees no `pending` line therefore reports "settled"
the first time it runs — before CI even exists — and the next turn claims green on an empty page. Require
two conditions before declaring settled: at least one line matching `pass|fail`, AND no line matching
`pending`. Re-watch after every push (a force-push starts a brand-new run), and confirm the edge with
`gh pr view <n> --json headRefOid` against the sha you actually pushed.

```bash
for i in $(seq 1 100); do
  out=$(gh pr checks <N> --repo <o>/<r> 2>/dev/null)
  if echo "$out" | grep -qE 'pass|fail' && ! echo "$out" | grep -q pending; then
    echo "$out"; exit 0          # settled: real rows, nothing pending
  fi
  sleep 60
done
```

## Re-running After Fix

```bash
git add <fixed_files> && git commit -m "fix: resolve CI failure" && git push

# Then monitor
gh pr checks --watch 2>/dev/null || \
  echo "Poll with: curl -s -H 'Authorization: token ...' https://api.github.com/repos/.../commits/$(git rev-parse HEAD)/status"
```

## Re-running a run that is stuck or failed

`gh run rerun <ID>` refuses while the run is still `in_progress` — it answers
`cannot be rerun; This workflow is already running`. A single hung job (a macOS
runner starved by the queue, a job stuck since its start time) holds the whole
run in `in_progress` and blocks the PR's green state, and you cannot rerun
around it. The recovery is cancel-then-rerun:

```bash
gh run cancel <ID> --repo <o>/<r>          # submit the cancel
# wait for the run to reach status=completed, conclusion=cancelled
gh run view <ID> --repo <o>/<r> --json status,conclusion --jq '"\(.status)/\(.conclusion)"'
gh run rerun <ID> --repo <o>/<r>          # only now does rerun accept it
gh run view <ID> --repo <o>/<r> --json status,attempt --jq '"status=\(.status) attempt=\(.attempt)"'
```

Cancellation of a hung job can take a couple of minutes to land; poll
`status`/`conclusion` until it is `completed`/`cancelled` before rerunning.
Confirm the rerun took by reading `attempt` (it increments) — a `queued` status
with a bumped attempt is the rerun scheduled. When the hung job is a known
runner-queue starvation (a normally ~10-minute job stuck for an hour), cancel
and rerun rather than waiting it out; the run will not finish on its own.

## Getting signal from a failed job while the run is still in progress

The RUN-WIDE log (`gh run view <id> --log`, `--log-failed`, `.../runs/<id>/logs`) is locked until the whole
run completes, so right after one job goes red those return empty. **A single COMPLETED job's log IS readable
in the meantime** — reach it through the jobs endpoint with the flag `gh` demands for ANSI output:

```bash
gh api "repos/<o>/<r>/actions/jobs/<JOBID>/logs" --allow-escape-sequences \
  | sed 's/\x1b\[[0-9;]*m//g' | grep -aE "FAIL|denied|Error|assert|OK " | tail -20
```

That is the fastest diagnosis of a matrix while it drains, and the way to name the real failing STEP of a job
whose log is otherwise locked. `gh run view --job <id> --log` refuses with *"run … is still in progress; logs
will be available when it is complete"*, and a bare `curl` of the same URL hits the redirect-header cap — the
`gh api` form is the one that works per completed job. Grep to the decisive lines; these logs are megabytes.

While the run is in progress you can still diagnose the completed job from
machine-readable endpoints — no log needed:

```bash
gh api "repos/<o>/<r>/actions/jobs/<JOBID>" \
  --jq '"status=\(.status) conclusion=\(.conclusion) name=\(.name)"'
# just the red steps (each `make <target>` is one step):
gh api "repos/<o>/<r>/actions/jobs/<JOBID>" \
  --jq '.steps[] | select(.conclusion != "success") | "\(.name) -> \(.conclusion)"'
# the check-run annotation: names the failing file+line when there is one,
# else only a bare "Process completed with exit code N".
gh api "repos/<o>/<r>/actions/jobs/<JOBID>" --jq '.check_run_url'
gh api "<check_run_url>/annotations" \
  --jq '.[] | "\(.path):\(.start_line) \(.title): \(.message)"'
```

An annotation that says only "Process completed with exit code N" (no test
name, no assertion) means the step's real output stays oracle-only until the
run finishes. Do not fabricate a cause from an empty/annotated log: either
wait for the run to complete (then `--log-failed` works and names the failing
test), or use the structural checks below.

## Proving a red job is not your change, then re-running only that job

When a required check is red but the run-wide log is locked, decide whether it
is yours before waiting it out:

1. **Scope by the make target, not the check name.** Read the failing job's
   recipe and which test files it runs. If the job's target list does not
   include any file your change touched, the failure cannot be caused by your
   diff — it is a flake or a pre-existing Hub/live issue. Grep the actual
   test filenames the target (and its sub-targets) names before asserting
   this.
2. **Check the same job on a merged base.** If the identical job is green in
   `main`'s recent CI runs, a red on your branch that does not exercise your
   files is an environmental flake, not a regression.
3. **Rerun only the single failed job** — `gh run rerun <RUN_ID> --failed`
   queues a fresh attempt of just the failed jobs (one new `run_attempt`),
   leaving still-pending green jobs alone. Confirm it took by re-reading the
   job: `status=queued` with the attempt bumped. This is the standard remedy
   for a live-Hub/acceptance flake, and is safe exactly when steps 1–2 say the
   failure is not yours; if the rerun fails again, the log is then unlocked
   and you must read it and fix the real cause rather than re-running a third
   time.

Don't treat a red required check as noise without this proof — a rerun without
the scope/Main evidence is how a genuine regression sails through green. But do
not block your PR on a job that cannot touch your code either: scope it, rerun
it, and only dig deeper if it comes back red.

## Auditing bot / scheduled-workflow health ("do the bots work?")

To answer "are the GitHub Action bots working as intended", survey every bot
workflow's run history, then drill into the broken ones. Do not eyeball one run
— the signal is the PATTERN across many runs.

```bash
# one pass per bot workflow: recent runs with event + conclusion
gh run list --repo <owner>/<repo> --workflow <wf.yml> --limit 12 \
  --json databaseId,createdAt,event,status,conclusion \
  --jq '.[] | "\(.createdAt[:16])  \(.event[:17])  \(.status)/\(.conclusion)"'
```

Classify each bot from the pattern, not a single run:
- **working** — consistent green on its schedule.
- **can never succeed** — every scheduled run fails at the SAME gate. This is a
  logic/ordering bug, not a flake; the bot will never complete until the gate is
  fixed. A bot that opens a PR only after a validation step will silently never
  open it if that step always fails.
- **stale** — the schedule is not firing at all (no runs for the expected
  cadence). GitHub drops scheduled runs; a missing run is a delivery problem,
  distinct from a red run.
- **startup failure** — 0-job, ~0-second `failure` runs on every push: the
  workflow file is invalid (see the compile-failure section above).
- **green no-op** — every run concludes `success` in seconds and the bot changes nothing, so the
  Actions list looks healthy while the work never happens. Read the DECISION line in the log
  (`[<bot>] …`, `action=<x>`), never the run conclusion. Two rules starve a bot this way: a
  decision that stands down globally while ANY item is queued behind it (the bot is blocked by
  exactly the backlog it exists to drain — the fix is to skip the claimed item and pick the next
  one, or to yield only on a LIVE claim rather than a label), and a per-run budget smaller than
  the cron cadence (`MAX_PER_DAY = 3` under an hourly `cron:` — the schedule advertises work the
  bot's own cap forbids).

Drill into a failing run:
```bash
gh run view <ID> --repo <owner>/<repo> --json jobs \
  --jq '.jobs[] | "\(.name) \(.status)/\(.conclusion // "-")"'   # job-level vs 0-job
gh run view <ID> --repo <owner>/<repo> --log    # the actual error text
```
`--log-failed` returns nothing for a 0-job startup failure (no failed job to
log) — use `--json jobs` to confirm the job count and `--log` for the error.

**Pitfall — a gate that ignores the decisions file.** When a bot's validation
gate hard-fails on data that already has a recorded decision (an allowlist, a
`unsupported-engines.json`, a dated decision), check whether THAT gate actually
honors the allowlist. Two sibling gates can disagree on the same data: one
(`check-engine-skill-gap`) tolerates recorded decisions, another
(`skills-validate`) errors on any unskilled entry and ignores the allowlist
argument. The bot then dies at the stricter gate before reaching its PR-open
step, forever. Reproduce locally with the exact `make`/command the workflow
runs, and compare the two gates on the same input to prove the disagreement
before filing the fix.

## An alarm workflow's red is the SIGNAL — walk one level down before diagnosing it

A scheduled health-check/alarm workflow (a sweep-age alarm, a queued-run alarm, a freshness check) exists to
go red when *another* pipeline stops delivering. Its log names the subject: the newest delivery it can see,
that run's id and conclusion, slots missed. Do not debug the alarm step — open the run it names. The answer
to "why is run <id> failing?" is usually two runs away: alarm → failing producer → the producer's own silent
step.

- Corroborate the claim across the producer's history, not one run:
  `gh run list --workflow <producer> --limit 12 --json databaseId,createdAt,conclusion`. Red on EVERY
  scheduled run is one bug; a single red is not.
- Grep what each red run actually ATTEMPTED, to find the repeating shape:
  `grep -oE "Sweeping #[0-9]+|issue=[0-9]+$"` across several runs exposes the same item being taken every
  hour — the classic reason a cadence never delivers.
- Say why the alarm is LOUD, not merely late: a producer that spends 20–30 min per run and fails at the
  same late step burns the whole cadence, so nothing lands.

## Prove a suspected ref/state bug with a throwaway ref, not with reasoning

A check that reads remote branches or open PRs to decide "already handled" can be unreachable while every
test is green. Prove it against the live API in reversible steps instead of arguing from the source:

```bash
SHA=$(gh api repos/<o>/<r>/git/ref/heads/<base> --jq .object.sha)
gh api -X POST repos/<o>/<r>/git/refs -f ref="refs/heads/<prefix><n>-probe-test" -f sha="$SHA" --jq .ref
make <the-real-target>          # the same target/env the workflow runs
gh api -X DELETE repos/<o>/<r>/git/refs/heads/<prefix><n>-probe-test
```

Creating a ref through the API triggers no push workflow, so the probe is quiet; DELETE it in the same call
so nothing is left behind. Then read the helper's own value in-process
(`python3 -c "import scripts.<mod> as q; print(q._branches('<o>/<r>'))"`) — that value next to the value the
comparison expects IS the bug report, and it is evidence rather than inference.

Two shapes this exposes:

- **A ref name is fully qualified.** `GET /git/matching-refs/heads/<prefix>` and every `/git/refs` read
  return `refs/heads/ci/data-gap-7-x`; `ref.rsplit("/", 1)[-1]` yields `data-gap-7-x`, silently dropping the
  `ci/` segment, so a `startswith("ci/data-gap-7-")` comparison never matches and the skip is dead code. Only
  `ref.removeprefix("refs/heads/")` gives the branch name the code compares against.
- **A skipped lookup cascades.** When a second read is gated on the first (`pull = ... if branch else None`),
  one failed read disables the independent check too — an open PR on that head no longer holds the item
  either. Audit every gate that depends on the read you just fixed.

## A stub that answers `[]` hides a dead check; `2>/dev/null` hides the collision it causes

- A `gh` stub on PATH that returns an empty list for an endpoint makes every "found something?" branch
  untested — the suite stays green with the branch unreachable. Before trusting green on a remote-state
  check, run the real call once (`gh api <endpoint> --jq length`) and compare its SHAPE with the fixture; a
  fixture written from imagination is worse than none.
- A mutating step that discards stderr (`gh pr create ... 2>/dev/null`) turns a legitimate collision into an
  unexplained exit 1: no message, no captured URL, every later step skipped. An idempotent bot step must
  treat `a pull request for branch "<b>" into branch "<base>" already exists` as "adopt the existing PR"
  (`gh pr list --head <b> --state open --json number,url`) instead of failing. Never silence stderr on a
  command whose failure mode is a state you can recover from.

## Force-pushes pile up queued runs on the fork

Every `git push --force` to a fork branch creates a NEW queued workflow run; a
long squash/amend loop leaves a backlog of stale queued runs that can sit
"queued" for many minutes and starve the current head's run. If the PR shows no
checks and the fork's run list is full of `queued` entries for older shas,
cancel the stale ones so the current head's run can schedule:

```bash
gh run list --repo <fork> --branch <branch> --status queued --json databaseId,headSha
gh run cancel <ID> --repo <fork>   # for every run whose headSha != current HEAD
```

A run stuck `queued` with no job started is a scheduling backlog, not a workflow
error — clear the queue before assuming the workflow is broken.
