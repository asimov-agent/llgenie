# Gate battery: rerun, flaky infra, stale change-record counts

## An amend or force-push invalidates every gate you already ran

The head sha is the unit of verification. Amending a commit (e.g. folding a doc fix in),
rebasing, or any force-with-lease push mints a new head, and every green measured at the
old sha is now a claim about a commit nobody will merge. Before reporting the PR clean:

1. `head=$(git rev-parse HEAD)` and `git ls-remote origin refs/heads/<branch>` —
   record head == remote_head in the same artifact as the results, otherwise the reader
   cannot tell which tree the numbers describe. **Use the FULL 40-char sha, never a
   truncated `--short` form**: an 8-char prefix can be AMBIGUOUS against local object
   context, so `git rev-parse --short` on one clone resolves the prefix to a different
   (local-only, divergent) object than the wire head, and a reviewer comparing your
   reported prefix against the API head sha sees a phantom "head mismatch" that does not
   exist. Verify identity three ways at the full sha — `gh api repos/<o>/<r>/pulls/<n>
   --jq .head.sha`, `git ls-remote origin refs/heads/<branch>`, and the worktree `git
   rev-parse HEAD` — and only then claim remote == local == PR head. When a sha in a
   report was ambiguous, the local object is an ANCESTOR of the wire head (`git
   merge-base --is-ancestor <short> <full>`), not a divergent fork; check that before
   entertaining a divergence theory.
2. Re-run the gates at the new head. A doc-only amend still touches `CHANGES.md` /
   `docs/changes.d/` / `agent-wiki/`, which `openspec-tasks-check`, `check-docs` and
   `lint` read.
3. Write head, remote_head, per-gate rc and the pytest tail into one file under the
   profile scratch dir, then read it back. “X passed” without a head is a claim about
   time, not about the branch.

### A `--force-with-lease` rejection is not proof the remote moved — and never delete the worktree before the push lands

After a **rebase**, HEAD is no longer a descendant of the old remote tip, so
`git push --force-with-lease` rewrites history rather than fast-forwarding. A lease
rejection here usually means your LOCAL remote-tracking ref is stale or your local view of
the wire tip differs from what the lease expects — NOT that another lane pushed. Before
concluding the branch moved:

    git fetch origin <branch>                     # refresh the tracking ref FIRST
    git ls-remote origin refs/heads/<branch>      # the true wire tip, full 40-char
    git rev-parse FETCH_HEAD

If the wire tip still equals the sha you based your rebase on, the rejection was lease
bookkeeping — re-push after a fresh `git fetch origin <branch>` using the PLAIN lease form:

    git push --force-with-lease --force-if-includes origin HEAD:refs/heads/<branch>

The explicit `--force-with-lease=<ref>:<sha>` form is a trap here: if `<ref>` is the local
remote-tracking ref (`refs/remotes/origin/<branch>`) git still rejects with "tip of your
current branch is behind its remote counterpart" even after you `git update-ref` that
tracking ref to the true wire sha — the lease ref must name the REMOTE ref, and a tracking
ref there produces a bogus non-force rejection. Plain `--force-with-lease` reads the
configured tracking ref itself and succeeds. Only a genuinely-advanced wire tip is
"another lane pushed"; a rejection that persists after a fresh fetch + tracking-ref update
is the kwarg shape, not the remote moving.

**Never `git worktree remove` (or `rm -rf` the worktree dir) until the push has landed.**
A rebased/committed fix that is not yet pushed lives ONLY in the shared object store; delete
the worktree first and a rejected push leaves you recreating the checkout to recover it.
Recovery when you did delete early: the commit is not lost — `git worktree add <path> <sha>`
(or `git branch recover <sha>`) on the parent clone resurrects it from the object store;
confirm `git cat-file -p <sha>` resolves before assuming it is gone. Confirm
`git ls-remote` shows your sha BEFORE removing the worktree — that order turns a rejected
push into a scramble.

### Squash after a rebase: use a LIST rebase then `reset --soft`, never `--onto <oldbase>`

To collapse a multi-commit branch to ONE commit on top of fresh `origin/main`:

    git fetch origin main
    git rebase origin/main                 # plain list rebase, resolve conflicts once
    git reset --soft origin/main           # drop all commits, keep the full tree staged
    git commit -m '<squashed message>'     # one commit on top of main
    git push --force-with-lease --force-if-includes origin HEAD:refs/heads/<branch>

**Never `git rebase --onto origin/main <oldbase>` where `<oldbase>` is your own
remote-tracking branch tip** (`origin/<branch>` or a local ref that already contains your
commits). `--onto` replays only commits in `<oldbase>..HEAD`, so if `<oldbase>` is your
branch tip with N commits, ONLY the commits you added after it are replayed and every
prior commit is silently DROPPED — the branch ends up carrying just the last fix, missing
the whole feature, and every gate still passes because the missing code simply isn't
referenced. Symptom: after "successful" rebase the feature symbols are gone
(`grep -c <feature-marker> <file>` returns 0). Recovery: `git reset --hard
origin/<branch>` (the pre-rebase tip still has the full tree in the object store) and
redo with the list-rebase form above.

### Don't chase the head with the PR body — batch, amend once, then patch the body once

A PR body that cites the verification head (`… measured at head <sha>`) goes stale the
instant the head MOVES — not only an amend (`git commit --amend`) but a rebase OR a plain
follow-up commit (e.g. a `make index` / `make changes-index` regeneration pushed to clear a
red) all mint a new sha. If you alternate
“fix a doc file → amend → patch body → fix another doc file → amend → patch body”, each
amend re-stales the line you just fixed and you loop forever.

- The body is a GitHub field, not part of the commit: patching it never requires an
  amend, and an amend never changes what the body ought to say except the sha itself.
- After ANY push that advances the head past the body's cited sha — amend, rebase, OR a
  plain fix commit — re-patch the body's head-referencing lines to the live head as the LAST
  action. A fix commit pushed AFTER you already patched the body re-stales it exactly like an
  amend does. When the tree is test-identical, say so (`identical test tree to the measured
  <old-sha>`) so the count still holds, but the CITED head must be the live one: a reviewer
  reading the body at the current head must not see a sha that no longer exists on the branch.
- Batch every repo-tree correction (all change-record prose, all counts) into ONE amend,
  push, THEN patch the body to that final head a single time. No further amend after the
  body patch, or the loop restarts.
- Verify the body patch by reading it back with a robust match: replace the sha
  unconditionally (`body.replace(old_sha, new_sha)`) rather than matching a long prose
  sentence, whose surrounding words rarely match the real text and silently no-op
  (expect `replacements hit: N of M`; assert the stale sha is absent and the new one
  present before claiming success).

## A CI re-run at the SAME head is not a no-op — it re-fetches live main and can mint a NEW red

`gh run rerun <id>` replays the same commit sha, but the guard job still runs
`git fetch origin main` fresh, so the re-run re-measures `check-pr-base` against the LIVE tip,
not the base the branch was cut from. Two consequences:

- A **body-only fix (no push) CAN clear `check-pr-acceptance` on a re-run**, because the checker
  re-reads the live PR body at run time. This is the correct way to re-gate a body edit without
  minting a new head — a body PATCH does not retrigger CI, so without a re-run the patched body is
  never measured.
- But if `main` advanced after the branch was cut, the SAME re-run flips `check-pr-base`
  green→red: the branch's merge-base is the old main, the live tip is the new one. The re-run
  changes nothing on the branch — only the base it is measured against. Expect this and do not read
  the new red as your body fix having broken something.

After ANY re-run, enumerate the NEW attempt's `steps[]` (`gh run view <run> --json jobs --jq
'.jobs[]|select(.name=="guard")|.steps[]|[.name,.conclusion]|@tsv'`) — the red you were dispatched
 to fix may be green while a different gate you never touched is now red. Confirm the head sha is
unchanged and the base is live before attributing the red.

**A re-run mints NEW job ids under the SAME run id — never reuse a job id captured before the
re-run.** `gh api repos/<o>/<r>/actions/jobs/<old_id>` still answers with that job's HISTORICAL
`failure` (the pre-rerun attempt); reading it as the rerun's result reports a cleared gate as red.
Always pull the fresh jobs from `gh run view <run_id> --json jobs` (or the head sha's
`/commits/<sha>/check-runs`), never a job id you measured before dispatching the rerun.

### NEVER re-run individual jobs to chase a multi-gate red — re-run the WHOLE run, once

When several gates (`guard`/`scope`/`ci-verdict`) share one workflow run and a body/state fix has
cleared the underlying cause, do NOT re-run each failing job in turn
(`gh run rerun <run> --job <id>`, repeated). Individual job re-runs can leave the RUN itself in
`conclusion=startup_failure` at a higher attempt — and an aggregate gate like `ci-verdict` reads the
RUN's conclusion, so the run reads `startup_failure` and `ci-verdict` stays red even while every
individually re-run job shows `success`. The two signals disagree because they describe different
objects (job vs run). Re-run the whole run ONCE (`gh run rerun <run>`), let it reach a single clean
attempt, and read `gh run view <run> --json status,conclusion` — `conclusion=success` at the run
level is what clears `ci-verdict`. Re-running a job to "refresh" a body-read gate one at a time is
the churn that produced attempts 2 and 3; one whole-run attempt is the remedy. `startup_failure` on
a run whose jobs are all green is a re-run artefact, not a defect in the branch — never report it as
"CI is red on the code".

### A GREEN run whose `ci-verdict` still reds: the verdict is judging its OWN posted check-run

The `ci-verdict.yml` judge POSTs a check-run named `ci-verdict` to the head sha, and GitHub
attributes that check-run back into the JUDGED run's job list. `GET /actions/runs/<id>/jobs`
then returns one job more than the decision artifact selected, and `ci_scope.verify()` counts
the extra `ci-verdict` row (conclusion `failure`, frozen from whenever it first red'd) as a job
with no verdict — `verdict=red success=10 failure=1` on a run whose own `conclusion=success`.

Diagnostic that separates this from a real red: download the run's decision artifact and
diff its job list against the API's. Ten jobs in the decision, eleven from the API, the
difference named `ci-verdict` → self-referential artefact, not a branch defect. A rerun of the
judged run can NEVER clear it — the check-run row persists, so each re-judge re-counts it, and
chasing it with reruns is an infinite loop that also risks `startup_failure`.

The fix belongs in the verdict tool, not in the PR under review: `ci_verdict.py::main()` must
DROP the observed job whose name is `CHECK_NAME` (`ci-verdict`) before calling
`ci_scope.verify()`. Prove it against ground truth rather than by inspection — feed that run's
real jobs file + decision artifact through the patched script and require `verdict=green`, keep
a regression test whose jobs list carries an extra `ci-verdict` failure row alongside a
full-matrix decision and still judges green, and leave the real-failure red cases untouched.
File the defect as its own issue/PR (one issue, one branch) instead of silently editing a
pipeline script under a feature PR. Report the PR under review as "all N real jobs green,
ci-verdict is a pipeline defect with a tracked fix" — never as "CI is red on the code".

### A step marked `skipped` is NOT a red — name the gate from its OWN step list

A guard/scope job can `conclusion=failure` while the gate you are tempted to blame is actually
`skipping` (its diff saw nothing to check). Naming it as the cause fabricates a blocker that does
not exist. Read the job's own steps and take only the `failure` ones as the cause:

```bash
gh api repos/<o>/<r>/actions/jobs/<job_id> \
  --jq '{conclusion, failed:[.steps[]|select(.conclusion=="failure")|.name]}'
```

Two corollaries: a real `check-pr-base` red appears as its own `failure` step ("NOT cut from
origin/main — issue #845"), never as `skipped`; and a `ci-verdict: red (run <id>)` check merely
MIRRORS an underlying guard failure — do not count it as a second, independent red; chase the run
it names.

The `check-pr-base` remedy is a **rebase onto the live tip — a push**. If the dispatch said
"no push" (or #1015/#1088 scope), you cannot make it yourself: report the acceptance gate green +
the surviving `check-pr-base` red with the exact shas (old merge-base, live main tip, head) and
hand the rebase to the rebase lane / planner. Never push a rebase outside your dispatch merely to
"make the run green" — that is the one thing the dispatch's no-push clause forbids.

### An "arm auto-merge" dispatch is CONDITIONAL — arm only when the WHOLE gate set is green

A dispatch that says "re-run then arm auto-merge" carries an unstated premise: that the *named*
stale red was the only thing between the branch and merge. The rerun can falsify that premise — it
clears the named red (acceptance) and simultaneously reveals a *different* red (`check-pr-base`
base-drift) the dispatch never saw. Treat the arm instruction as contingent on the gate, not as an
order to arm a specific sha.

- Before `gh pr merge <n> --squash --auto`, enumerate the current head's guard `steps[]` and
  confirm NO gate reds. `mergeStateStatus=BLOCKED` on the PR is the one-line tell that something
  still holds it — read `gh pr view <n> --json mergeStateStatus,mergeable`, do not assume.
- Arming a PR while a gate is red is a false claim that it is mergeable-green. The arm call itself
  may even exit 0 and arm nothing; the exit code is not the fact. Read `autoMergeRequest` back —
  and do not arm at all on a red, because the honest state is "blocked", not "queued".
- `autoMergeRequest=null` on a read-back AFTER a clean `gh pr merge --auto` does **not** always mean
  the arm failed. If a required review landed between the arm and the read-back, auto-merge can have
  ALREADY CONSUMED the PR and merged it — the null is the post-merge state, not a dropped arm. Before
  re-arming, check `gh pr view <n> --json state,mergedAt,mergeCommit`: `MERGED` means the arm worked
  and a re-arm is a no-op that looks like another failed attempt. `mss=UNKNOWN` in the same readout is
  the transient recompute tell that a state change is in flight — re-read once before concluding.
- `mergeStateStatus=BLOCKED` with **every check-run green and `reviewDecision=null`** is a *pending
  required review*, not a gate defect and not base-drift. The missing input is the reviewer/owner's
  approving review; a rerun or rebase cannot supply it. Do not chase it as a red or hand it to the
  rebase lane — report all-green + `mss=blocked (pending required review)` and leave the approve to
  the owner. Distinguish it from a genuine hold by checking `gh api repos/<o>/<r>/commits/<sha>/
  check-runs`: all `success` + null reviewDecision = review wait.
- When the rerun exposes a new red, do what you would for any merge-blocker you do not own: report
  the now-green gate + the surviving red with exact shas, hand the fix (rebase) to its lane, and
  state plainly that you did NOT arm because the head is not gate-green. Skipping the arm on a red
  is correct behaviour, not a missed instruction.

## `check-wiring` scans step NAMES for a literal `make <target>` — prose in a name fakes a red

`make check-wiring` greps every workflow step's `name:` (not only its `run:` block) for the
literal token `make <target>`, and fails if that token is not a real Makefile target. A step
NAME written as prose — `name: "… is a host-only make target (make test-engine-serve)"` — makes
the parser read `make test-engine-serve` from the name and red the gate with a phantom missing
target. Keep `make …` out of step `name:` strings (word it `make-target` or move the command to
the `run:` block / a `#` comment, which the checker does not scan); reword the name and re-run
`make check-wiring` before concluding a target is genuinely missing.

## A workflow `on:` change must rewrite its contract tests in the same PR

A PR that changes a workflow's `on:` triggers — removing `workflow_run`, flipping to
`workflow_dispatch`-only, adding/removing `schedule` — MUST rewrite the tests that pin that
trigger contract in the SAME PR. Repository tests read the workflow YAML
(`run-failure-reactor.yml`, `ci-verdict.yml`, …) and assert its `on:` keys, required inputs and
the roster that names it. Change the workflow without the test and the test keeps asserting the
OLD contract, reding `linux / unit` with a `KeyError` or bare `assert` on the removed key — a
failure in a test your diff never touched by name.

- Before pushing a workflow change, grep the test tree for the workflow filename and the trigger
  key you removed: `grep -rnE 'workflow_run|<workflow-file>|run_id' tests/`. Rewrite each hit to
  the new contract (dispatch-only, `required: True` on the input, no `workflow_run`/`schedule`).
- CI runs the `refs/pull/<n>/merge` ref (the PR merged into base), so the failing test can live on
  the merged tree even when your bare head looks clean — when a unit red does not reproduce at the
  head, `git fetch origin refs/pull/<n>/merge` and inspect the test at that ref.
- Drop any always-true no-op assertion a rewrite leaves behind (`assert {"run_id": {"required":
  True}}`) — it proves nothing; assert the real shape.
- Run the sibling modules too (`test_ci_verdict.py`, `test_run_failure_reactor.py`,
  `test_workflows_valid.py`) so the fix does not leave a second stale assertion behind.

The rule generalises to ANY behaviour change a PR ships, not just workflow `on:` triggers:
when a Dockerfile flips from source-compile to a prebuilt base, or a builder stops running
an install step, grep the test tree for assertions pinning the OLD behaviour
(`assert "engine_runner.py install" in df`, `prebuilt: false`) and rewrite them in the
SAME PR. A sibling test still asserting the removed step reds `linux / unit` on a file your
diff never touched by name; the fix is to assert the NEW shape (prebuilt base present,
install absent), never to widen the old assertion to keep it passing.

## `ci-verdict` re-judges on a rerun's completion — a red verdict is the OLD run's verdict

The `ci-verdict` judge triggers on `workflow_run: [completed]`, i.e. it judges a run only when
that run finishes. Two consequences to state plainly when asked "why is ci-verdict still red":

- A `gh run rerun <id> --failed` puts the run back to `in_progress` and it must COMPLETE AGAIN —
  that completion re-fires the judge, so a rerun does re-judge (this is correct, not a gap).
- The red the user is staring at is usually the verdict from the run's PREVIOUS completion. It is
  stale the moment a rerun is in flight and flips only when the rerun re-completes; if the rerun's
  unit leg is still genuinely red, the fresh verdict stays red HONESTLY — chase the underlying
  test, not the verdict.
- `UNJUDGED RED` in the verdict message means a check-run at the head still reads
  `conclusion=failure` (the judge refuses to call a head green while a check is red), not a judge
  fault. Clear the underlying check and let the run re-complete; do not re-dispatch the judge
  against a head whose real CI is still red.


`make lint` (and any containerised gate) can print
`docker: Cannot connect to the Docker daemon at unix:///var/run/docker.sock` and exit 125
while the daemon is fine — the pytest container served by the same daemon seconds earlier
ran, and `docker info` answers. That is infrastructure noise mid-run, not a lint finding.

- Retry the SAME gate before reading anything into it (`for i in 1 2 3; do ... done`).
- Do not report rc=125 / “daemon not running” as a gate failure, and do not start
  repairing lint findings that were never emitted.
- Do not paper over it either: a retry that still reds is a real finding — get the gate's
  own output line before claiming either verdict.

## Invoke gates with the arguments they actually take

Guessing a subcommand wastes a cycle and looks like a red gate:
`python scripts/lint_linefeeds.py check` dies with
`error: unrecognized arguments: check` (rc=2). Bare `lint_linefeeds.py` IS the check;
`--fix` is the only flag. Same class: run `make <target>` rather than hand-assembling the
container command, so the recipe supplies env and mounts; a hand-rolled `docker run`
around one script is a fallback for reading a single gate's output, not the gate itself.

`gh issue list` has no `--page` flag — it paginates internally and takes only `--limit`.
Passing `--page N` is accepted silently and yields an EMPTY list (rc 0), which reads as
"no issues match" instead of "bad flag". To scan the whole backlog fetch once with a high
`--limit` (`gh issue list --state open --limit 300 --json number,body`) and filter
Python-side; do not page it. Same trap class as the jq/flag mismatches above: a wrong flag
that exits 0 and returns nothing is indistinguishable from a real empty result until you
check the flag against the tool's actual surface.

## Adding a REJECTING class to a gate — scan the live corpus before shipping

When your change makes a gate newly RED a class of input (a new finding class, a stricter
regex, a new required token), first scan every live input the gate will run against and
prove the new rule does not false-red existing legitimate data. For `check-pr-acceptance`
that corpus is every OPEN issue/PR body: fetch them all, run your new predicate over each,
and confirm the only hits are the intended reds (usually zero on open items; the motivating
red lives on a CLOSED issue). A gate shipped without this scan can turn `main` red on the
next legitimate PR that happened to use the old shape. Publish the scan result in the PR
("N open issues, M carry the pattern, all form-OK → no false-reds") as the argument that
the new rule is safe, not as an afterthought.

## Change-record test counts go stale silently

Every PR here ships one change record in three places that must agree: the `CHANGES.md`
row, the `docs/changes.d/<slug>.md` fragment, and the `agent-wiki/<slug>.md` page. Each
carries a test count written when the tests were first green, so adding a regression
guard later leaves a count no gate checks.

- Derive the count from the run you just made (`24 passed`), not from an earlier run.
- Derive “N new” from the diff, not from the prose: count the added test functions
  (`git diff <base>..<head> -- tests/ | grep -c '^+def test_'`). A plausible round number
  in three files is still wrong in three files.
- Fix all three in one commit, then re-run the gates above.
- The prose must enumerate EVERY added guard, not just the first two: a record can say
  “3 new” and still list only 2 by name — a count/prose mismatch inside the same row. After
  correcting the count, re-read the sentence and confirm each added test function appears;
  the omission is invisible to every gate and reads as if the third guard is untested.

## Run the suite on a CLEAN tree — a committed-vs-working-tree diff test reds on your OWN edits

Some gates compare the committed file at HEAD (`git show HEAD:<path>`) against the WORKING tree
(`path.read_text()`), e.g. a "params file identical to the base is not deferred" test that diffs
`engine_image.py` at HEAD against its on-disk copy. CI checks out a clean tree, so such a test
passes there; on YOUR worktree with uncommitted edits the SAME test reds and looks like a
regression your change caused. Before reading any such red as a defect, `git status --short` must
be EMPTY — if it is not, commit (or `git stash`) and re-run. A red that reproduces only with dirty
files is an artifact of your own edits, not a branch defect: never report a dirty-tree red to the
PR as a code failure, and when you must run the suite mid-edit, note the dirty file set so you can
attribute the red to it.

## A pure-function unit test is not proof the shipped gate passes — drive the real gate fn

Passing a unit test of a decision helper (`decide(...)`) proves the LOGIC, not that the shipped
gate function CI actually calls (`binary_file_works(...)` here) accepts the input. Add an
integration test that (1) calls the REAL gate function, and (2) mocks the subprocess it uses so the
returned output is the EXACT measured text from the failing log (probe `LG-FLAG`/`LG-OUT-*` lines,
verbatim). That renders the whole pipeline — flag-list construction from the manifest, probe parse,
decide — and catches a fix that edited the pure decider but left the caller passing the old policy.
Assert the gate's return code AND that the documented flag was probed first; a mock that only stubs
the pure helper re-implements it and proves nothing about the shipped path.

  ## `gh --repo` is not a flag on `gh api`

  `gh --repo owner/repo api ...` prints the entire `gh api` help and exits 1 (`unknown flag:
  --repo`) — `--repo` is a flag of `gh pr`/`gh issue`/`gh run`, not `gh api`. To target a
  repo, either run `gh api` from inside the worktree (it infers the repo), pass the path
  explicitly (`gh api repos/<owner>/<repo>/pulls/<n>`), or export `GH_REPO`. A help dump
  written into an evidence artifact is a bad capture: redo it, don't quote it.

## gh belongs in `terminal()`

`git`/`gh` mutations in this repo go through `terminal()`. A Python kernel call that
shells out to `gh` can die with `FileNotFoundError: 'gh'`, so keep `execute_code` for
parsing and measurement and run `gh api` / `gh pr view` through `terminal()`.

## Keep `--jq` expressions flag-free of shell-quoting traps

When a `gh api` call is wrapped in `bash -lc '...'`, a jq object expression that uses
curly braces and colon keys (`--jq '{m:.mergeable, base:.base.ref}'`) fails to parse —
`failed to parse jq expression ... unexpected EOF` — because the single-quoted `bash -lc`
wrapper mangles the braces/quotes. Use one `--jq .field` per field and concatenate them
(`gh api ... --jq .mergeable_state; gh api ... --jq .base.ref; …`), or emit the raw JSON
and parse it Python-side. Do not quote a jq-parse error as if it were PR state — the exit
code is 0 but the field was never read. A related shape inside a valid program: jq's object
shorthand `{id,name}` works for plain keys, but a dotted accessor is not a key —
`--jq '{id,name,.path}'` dies with `failed to parse jq expression … unexpected token ".path"`.
Write `{path:.path}`; when a selector errors, print the raw JSON and parse it Python-side
rather than iterating on the program.
