# Park prepared work as a bare reference branch — a branch with no PR never fires `engine-build-pr-trigger`

When a fix's target surface only exists in ANOTHER PR's diff (e.g. a gate job and its polling script live
only in the held PR, not in `origin/main`), do not open a standalone mergeable PR against `main` — that PR's
new job would have no producer to build it. Instead:

1. Cut the branch from the HOST PR's canonical union head (verify `git log -1 --format=%p` prints that
   union sha), so the fix folds directly into the host diff when it lands and needs no rebase.
2. Publish it as a bare ref with NO pull request:
   `git push origin HEAD:refs/heads/<descriptive-name>`.
   A branch push alone creates no `pull_request` event, so `engine-build-pr-trigger` (PR-event only) does
   nothing — the branch is safely fetchable and review-ready without dispatching a matrix.
3. Verify with `git ls-remote origin refs/heads/<name>` (== your local HEAD).
4. Record the branch + head sha + parent-on-union + scope on the ISSUE (bookend), and tell the host-PR
   lane the branch exists so they fold it in — do not open the mergeable PR before the host lands.

The same shape applies whenever the owner/planner gates a change as "author on a branch, land when X lifts":
a parked branch with no PR is delivery without a trigger, and is the state the durable board record cites.

# Merge, post-merge refinement, and head verification

## Arming auto-merge: read `.auto_merge` (REST), not `.autoMergeRequest` (GraphQL)

Another lane reporting "auto-merge is NOT armed, `null` on both PRs" is unproven until the query is
named. `.autoMergeRequest` is the GRAPHQL spelling; the REST pulls endpoint
(`gh api repos/O/R/pulls/<n>`) exposes `.auto_merge`, so jq-ing the GraphQL name off REST returns `null`
for a correctly armed PR. The same trap runs the other way when a `--jq` expression collapses under
shell quoting and prints an empty string that `json.loads` then rejects — an empty read is a broken
query, never a null field.

- Armed = `auto_merge.merge_method == squash` AND `auto_merge.enabled_by.login` set. Read back and quote
  those two values (plus the head sha) as the arm's proof.
- `mergeable_state=blocked` is NOT a disarm signal: pending checks produce it while the arm stands.
  Report `auto=none (blocked: <check>)` only when BOTH fields are null.
- `gh pr merge --auto` exits 0 and arms nothing when the PR's base is not the default branch; both null
  after an exit 0 means the arm never took, not that the readback was unlucky.

## A squash merge captures the head AT MERGE TIME

When a PR is squash-merged, only the commits on the branch at that instant land — as one new commit on `main`. Commits pushed after the merge are **not** ancestors and never land. So:

- Before assuming your later fix is on `main`, prove it: `git show <main-sha>:<path> | grep -n '<symbol>'`. Count occurrences rather than eyeballing a diff — a partial baseline (e.g. one `except SystemExit` that is the SKIP path, not the retry) looks like your work landed when it did not.
- Do not use `git diff main your-branch` alone to decide what is missing: your branch may contain work already merged under a different sha. Inspect the merged file's actual content.

## `git rebase` "dropping <sha> — patch contents already upstream" means the PR already MERGED

If a rebase reports `dropping <sha> ... patch contents already upstream` and leaves the branch tip equal to `origin/main`, your PR was **squash-merged** and its content is already on main. Confirm before doing anything else: `gh pr view <n> --json state,mergedAt,mergeCommit,mergedBy`. `state=MERGED` means the work is delivered — do NOT re-implement it, and do NOT open a fresh branch for it.

- A squash merge produces a NEW sha on main; the branch head you watched is never an ancestor, so `git log` on the branch shows only the squash commit and looks "empty vs main". That is the merged state, not a lost commit.
- A dispatch that names an OLDER tip than `origin/main` and asks you to branch fresh may be **stale** — the work it describes can already be merged past that tip. Always read the live merge state of the PR/issue before re-branching. Re-implementing delivered work is the failure mode; verifying merge state first costs one `gh pr view`.
- Report the merged state (commit sha, mergedAt, mergedBy) to the planner so it stops re-dispatching the completed scope.

## A conflicting rebase is NOT proof your change is still needed

The clean `dropping <sha> ... patch contents already upstream` rebase line is only ONE way
"already resolved" shows up. The harder case: `main` advanced past your branch base and another
lane's merged commit fixed the SAME gate with a byte-different but semantically equivalent rewrite
(e.g. `import scripts.x as y` vs `from scripts import x as y`). Your rebase then CONFLICTS instead
of cleanly dropping, which reads like "my change is still needed" — but it isn't.

Trigger for this check: `main` moved since you branched (your recorded base sha is not the tip).
Do NOT rely on rebase output. Instead, measure the gate at fresh `origin/main`:

1. `git fetch origin main` and record the new tip sha.
2. In a **clean detached worktree** at `origin/main` (no local change), run the exact gate the
   issue names (e.g. `python3 scripts/check_import_roots.py ratchet`) plus the target test file
   (`pytest tests/<file> -m "not network"`).
3. If the gate is already green there (rc 0, at/below the committed baseline) and the target file
   already carries the required shape, the dispatch is **found-already-resolved**: report the
   resolving merge sha + the green gate measurement, recommend the issue be closed, and push NO
   duplicate PR. A byte-different equivalent merge still counts as resolved.

Re-implementing delivered work as a redundant PR is the failure mode this prevents; the one clean
worktree measurement (`git rev-parse --short HEAD` prints the tip; the gate prints its rc) is the
proof, not a claim that "main looks fixed".

## A refinement that arrives post-merge is follow-up scope, not a rebase

If the owner refines an issue whose PR already merged:

1. New worktree + branch from **fresh** `origin/main` (fetch first; never from the old worktree head).
2. Read the **merged** file (from `main`), not your local branch copy — your branch may be ahead of or behind what landed.
3. Patch the merged file, then re-verify the whole gate set in one sweep.
4. Open a NEW ready PR against the merged baseline; do not reopen or re-target the merged one.

## Verify the head from git, not the PR API

After a push, `gh pr view --json headRefOid` and `gh run list` can lag by minutes (GitHub recomputes the PR head; mergeable goes UNKNOWN). The authoritative facts are:

- `git ls-remote <remote> refs/heads/<branch> | cut -f1` — the true branch tip.
- `gh api repos/OWNER/REPO/actions/runs?head_sha=<FULL-SHA>&per_page=20` — runs keyed to the exact full sha.

Key every watcher on the **full 40-char sha** just read back from git; a truncated or remembered sha watches the wrong run. Before arming, assert tip == PR head == watcher key and print the booleans.

- **The `checks` sub-resource does NOT exist on the PR endpoint.** `gh api repos/O/R/pulls/<n>/checks` returns 404 — there is no such REST route, so a 404 there means the endpoint is wrong, not that the PR has no checks. Read a PR's check runs with `gh pr checks <n>` (or `.../commits/<sha>/check-runs`).
- **`actions/runs` items expose `.id`, not `.databaseId`.** `gh api .../actions/runs` returns `.id`; `databaseId` only exists in `gh run list --json databaseId` and reads `null` when you jq it off a raw `gh api` payload (the key is absent), so a `.databaseId` accessor off that payload raises `KeyError`. Read `.id` for run ids.

- **Compare shas at ONE truncation length.** A membership test of a hard-coded `sha[:7]` against a read
  that prints 8 or 9 characters fails on a HEAD that is genuinely pushed, and the next turn is spent
  re-pushing work that already landed. Prefer full shas in the comparison; if a prefix is unavoidable,
  truncate BOTH sides to the same length in the same expression (`a[:9] == b[:9]`).
- **Capture a gate's rc AND its output in the same call that runs it.** `make <gate> 2>&1; echo rc=$?`
  (or the subprocess result object) returns both at once. Re-reading a log file you already wrote — once
  per follow-up question — burns a pass without adding a fact; if a persisted log is genuinely needed,
  one read is the budget, and the next step should be an action, not another probe of the same bytes.

- A sha quoted in an incoming message (a coordinator/dispatch note) is **unverified** — re-fetch `origin main` and `git ls-remote <fork> refs/heads/<branch> | cut -f1` every turn and answer with the sha you *measured*, not the one you were told. A coordinating lane re-citing a tip that is two pushes old is routine; correct it in the reply with the measured sha.
- **A phantom stale fork-ref survives every live check; prove convergence non-destructively.** A coordinator can keep ordering a force-push to "converge" a fork ref it claims reads an old sha (e.g. `86a9ec33`) when every live measurement — `git ls-remote fork refs/heads/<b>`, the GitHub API branch endpoint, and the PR `head` — already reads the current sha. The stale sha is usually a superseded PR head still in the commit graph, which is exactly why the API `compare` reports `diverged`. Prove the ref already equals the target by running the ordered command with `--dry-run` and a lease naming the stale sha: `git push --dry-run fork <src>:refs/heads/<b> --force-with-lease=refs/heads/<b>:<stale-sha>` prints **`Everything up-to-date`, exit 0** when there is nothing to converge. THEN refuse the force-push as a no-op — never rewrite a branch already on its target sha to satisfy a phantom. Crucially, the "stale ref" a coordinator dry-runs against is real at that minute — capture it with `git ls-remote` BEFORE the dry-run and quote both so the proof names the exact before-tip the lease was expected to hold. **A coordinator can later deny the order it demonstrably gave**: on #1568 the force-push demand was issued twice (comments 6589670224, 6589728291) and retracted once (6590027061) by the same coordinator, then in a later correction (6590512291) flatly asserted the instruction "never existed" and `86a9ec33` "appears in no planner comment" — despite 33 comments naming it. The PR's own comment receipts are the evidence; NEVER rewrite a verified patrol/skill record to satisfy a corrected claim in either direction, and never let a re-fetched citation be overridden by an assertion that contradicts it.
- **A coordinator's inbox reader can invert the direction of staleness.** A planner's settle-echo may assert the *engine* "runs stale refs (e.g. 621ddda1/52b21a42)" and that gate checks are "still running" while the engine's own measurement is the live pair and every check-run is terminal (`status=completed`). Do NOT treat the coordinator's citation as authoritative and do NOT re-DM the same correction a second time — when the coordinator has declared loop-closure ("nothing to reconcile, no mutation owed") it just echoes your corrected message back as "stale" again (a ping-pong loop). Instead: measure locally (`git rev-parse HEAD`, `git ls-remote <fork> refs/heads/<b>`, `origin/main`), assert every check-run group is `status=completed` (query `.../commits/<sha>/check-runs` and flag any non-completed), then pin ONE on-issue comment carrying the measured triple + the all-terminal set + the classification of each red — that is the record the owner reads at the merge decision. Posting to the issue is not a DM ping-pong; it corrects the durable board record without a reply loop.
- A `ci-verdict` red is usually a DERIVED rollup, not a separate workflow defect: read its check-run `output.summary` (e.g. `/check-runs/<id>` → `NO VERDICT: N job(s) unaccounted for`) — it is red only because its substrate jobs (`linux/unit`, `linux/openspec`) failed on the same openspec gate. Classify it as the same root, never as a new red.
- After a force-push the PR `head` reads `UNKNOWN`/null for a minute while GitHub recomputes — poll until `head` equals your pushed sha AND `mergeable` is non-null before reading check-runs; those check-runs are then re-spawned at the new head (old ids are gone, new run ids arrive with lag).
- `.../actions/jobs/<id>` (job **metadata**) is a different endpoint from `.../actions/jobs/<id>/logs`: the metadata one returns `steps[]` with a per-step `conclusion`, so one GET names the failing step (e.g. `make ci-openspec: failure` while every other step is `success`) without pulling a log. Only the `/logs` endpoint 401s.

## Run a gate script from YOUR branch's own checkout, never another lane's worktree

Every `scripts/check_*.py` resolves `REPO_ROOT = Path(__file__).resolve().parent.parent` and runs
git with `cwd=REPO_ROOT`. A gate script invoked by ABSOLUTE PATH from a *different* lane's worktree
therefore reads THAT worktree's HEAD and commit range, not yours — it will report a closing/mismatch
red (e.g. `closes #1245` vs a body closing `#1634`) that is a pure artifact of the wrong repo. Before
trusting any local gate measurement:

- `cd` into your own worktree and invoke `python3 scripts/check_<gate>.py ...` (RELATIVE path) so
  `REPO_ROOT` is your checkout; assert `git rev-parse --short HEAD` in that same cwd prints your
  branch tip before reading the gate's rc.
- The `check_pr_closing.py` squash half is SET-based: `commit_closed` = every adjacent
  `closes|fixes|resolves #N` across the JOINED messages; it reds when `claimed - commit_closed` is
  non-empty, when `claimed - body_closed` is non-empty, or when `commit_closed != body_closed`. ONE
  adjacent `closes #N` anywhere in the joined text satisfies every `#N` claim — but an EXTRA close
  in the commits that the body lacks (or the reverse) reds it as `squash-mismatch`. Keep the two
  sets identical.

## A cited guard red at a stale head is superseded — re-read check-runs at the LIVE head

Before chasing a coordinator-cited guard failure, compare its sha to the live PR head. If the cited
run's head predates your latest push (routine — the coordinator's snapshot lags), the red is STALE
and the guard re-runs fresh on the newer head. Confirm with
`gh api repos/O/R/commits/<live-sha>/check-runs --jq '[.check_runs[]|{name,status,conclusion}]'`
at the measured live head, and report the live verdict rather than repairing a defect that no longer
exists at the current sha.

## The owner merges THROUGH a pending CI run — report the real head verdict, not the merge event

`state=MERGED` is a fact about the owner's action, NOT a green CI verdict. The owner routinely
squash-merges while the head's `CI` run is still `in_progress`, so `mergedAt` and `conclusion` are
different facts and the run may never report green at that head. Never close a lane on the merge
event alone:

- Read the run keyed to the merged head: `gh api ".../actions/runs?head_sha=<FULL-SHA>" --jq '.workflow_runs[]|[.id,.name,.status,.conclusion]|@tsv'`. A `CI in_progress` run at the merged head is the outstanding item, not a done one.
- `gh run watch <id> --repo OWNER/REPO --exit-status` in the background (notify on complete), then report the **conclusion** the run actually produced. Report `in_progress`/`pending` as in-flight; never as green.
- When the run is stuck pending and cannot be relied on, the honest proof is the **local hermetic gate set run against the merged content**: reset a worktree to `origin/main` at the merge sha, then `make check-trend-list-matrix check-engine-params check-engine-source check-engine-capabilities check-wiring` plus the hermetic pytest subset (`-m "not network"`) must be green. State that this is the local proof and CI was merged-through-pending.

## Prove the merged diff is exactly your change

After a merge, confirm the landed commit carries exactly the intended files: `git diff <merge>^ <merge> --stat` and compare against your expected file list and stat. A squash merge can pick up stray files or reorder; the `--stat` is the cheap byte-level assertion that what shipped is what you built (e.g. the 7-file set with the fixture rewrite). `git show <merge>` (commit message) plus the stat together beat trusting the PR API.

## Engine-bump PRs red on stale-base + check-docs (#1123) — the generator re-roll trap

An engine-bump PR has TWO gates beyond check-pr-closing, and the generator's behaviour makes both look like "the fix is enough":

1. **check-pr-base (#845)** — the generator's bump branch was cut before `main` moved, so a force-pushed head is `diverged, behind N`. Fix = rebase the amended commit onto fresh `origin/main` (keep the rewritten "closes no issue" message). This is a real structural red, NOT a stale snapshot.
2. **check-docs change→note (#1123)** — touching a behavioural surface (`containers/`, `docs/.*\.md`, `Makefile`, etc.) with NO `agent-wiki/<stem>.md` note in the branch's diff reds `make check-docs`. The generator roll updates `docs/changes.d/<stem>.md` + CHANGES.md but can leave the agent-wiki note **stale at a previous PR** (unchanged from main = not in the branch's diff = check-docs can't see it). Fix: re-point the note to the current PR + new pin, add/refresh the fragment row and run `make changes-index`.

**The re-roll trap:** the engine-bump generator force-pushes a NEWER pin onto the same branch mid-work (post-#1592 message, `closes no issue`). Do NOT keep your older-pin amended commit over it — rebase onto the generator's fresh roll and layer the delta additively. A force-pushed older pin that "looks like my fix" is a regression vs the newer upstream.

Preflight that prevents both reds: `git fetch origin main; git rebase origin/main` (merge-base == the fresh tip), confirm the amended TREE still carries no `Issue: #N` claim in commit text AND body, and ensure a behavioural-surface change adds/updates an `agent-wiki/` note + `docs/changes.d/` row + regenerated CHANGES.md. Verify locally with the live gates (`CHECK_DOCS_BASE=origin/main make check-docs`, `scripts/check_pr_closing.py check --body-file ... --base origin/main --rev HEAD`, `scripts/check_pr_base.py check`) before pushing — the untargeted host pytest may be a broken env; the hermetic `llgenie/test` container (`docker run --rm -u root -v "$PWD":/repo:rw -w /repo llgenie/test:latest python -m pytest ...`) is the authoritative unit-test path. A bare `python -m pytest` (no deps) can exit RC=2 with EMPTY output — that is the wrong interpreter, not a test failure; use the repo's own test venv (`make test-env` builds `~/llama-gguf-tools/.venv`, Python 3.11) or the hermetic container, and only then read real pass/fail counts.

# PR-hygiene gates read the COMMITTED diff, not the working tree

The `scripts/check_*.py` gates diff `base..HEAD` of COMMITTED commits. A note/fragment file that
exists only in the working tree (untracked or unstaged) is INVISIBLE to them — `make check-docs` reds
"behavioural change has no note" even though the note is right there on disk. Commit the note +
fragment + regenerated `CHANGES.md` BEFORE re-running the gate; staging alone is not enough. (The same
holds for `check-pr-closing`: the commit message's `closes #N` set must equal the body's.)

- **A new `##`-documented make target must be BOTH documented in `docs/` AND added to the Makefile
  `.PHONY` list.** `check-docs` reds on the missing doc entry; the wiring guard (`check-wiring` /
  `…wired` unit test) reds on the missing `.PHONY`. Add the target name to the nearest `.PHONY`
  sub-list and match the sibling lines' indent exactly (the list uses single-tab continuation lines;
  a fuzzy patch that inserts a leading tab or doubles the trailing backslash breaks the list and the
  target then fails to parse). Re-run both gates after.
- **`check-pr-agents-line` requires the EXACT `AGENTS: <sha> <bytes>b <chars>l` line that
  `make bot-preflight` prints,** plus a `BASE:` line naming the same `origin/main` sha (the sha must be
  reachable from both head and base). The `<bytes>b <chars>l` pair is the fixed AGENTS.md measurement
  (e.g. `91766b 1363l`), NOT a per-PR byte count — do not invent it. Do not regex-rewrite the line to
  change the sha: run `make bot-preflight` at the current head and copy its `AGENTS:`/`BASE:` lines
  verbatim into the body. A hand-edited `AGENTS: <truncated-sha> 0l` reds the gate, and because
  workflows trigger on head pushes (not body edits), the fix needs a `gh run rerun <id> --failed`
  after the body is corrected — re-running is what turns the stale red check green.

# Rebase onto current main — `--onto origin/main <HEAD>` is a silent no-op reset

`git rebase --onto origin/main <PR_BRANCH_HEAD>` takes the commits AFTER <HEAD> up to the branch — but
the branch tip IS <HEAD>, so the range is empty and git silently RESETS the branch to bare `origin/main`
dropping every PR commit (this bit #1568 twice). Signal in reflog: `rebase (start): checkout origin/main`
then a plain main commit as the new tip.

The correct upstream is the PR's CURRENT merge-base (the tip the branch was last built on), NOT the
head:

    git fetch origin main
    git rebase --onto origin/main <OLD_MERGE_BASE_SHA>

<OLD_MERGE_BASE_SHA> = the merge_base of `compare/origin-main...<head>` before rebasing. Recovery after
the no-op reset: the old head still exists (reflog + `git cat-file -t <oldhead>`=commit). Detach first —
a leaf worktree REFUSES `git branch -f` on a branch it owns while checked out — then `git branch -f
llgenie-wt/<b> <oldhead>`, checkout, redo the rebase with the old base.

RE-VERIFY after every rebase: `git merge-base origin/main HEAD` must equal `git rev-parse origin/main`
(check-pr-base #845 PASS) AND `git diff --stat origin/main HEAD` must still list the PR's own files
(vllm.json + openspec/docs trio), never empty. Assert `merge-base == tip`, NOT the immediate parent:
a multi-commit `--onto` replay makes the new HEAD's parent the *previous replayed commit* (e.g.
`e425b8fa`), so `git log -1 --format=%P` legitimately is not `origin/main` — checking that would read
a correct rebase as broken. Then push to the PR's head repo (fork) with an explicit
`--force-with-lease=<ref>:<old-sh-owned-tip>`.

# Transient upstream failures in a host sweep

The smallest-model fetch (`hf_download.py`) can surface a transient Hub 5xx. Two distinct shapes both defeat a naive `except Exception` retry wrapper:

- `SystemExit` — raised when `hf_download.py` runs as a child and exits non-zero on a 5xx. `except Exception` does **not** catch it.
- `urllib.error.HTTPError` — raised in-process when the download path runs in-process.

So a retry must catch **both** `SystemExit` and `urllib.error.HTTPError` (import it explicitly), back off, and re-raise only after the last attempt. A Hub blip must degrade to a retried fetch, never abort an N-engine sweep. Test both shapes: 503 twice then success, and permanent failure → non-zero exit.

# Openspec files created by the container are root-owned

When an openspec/validation step runs inside a container, files it creates under `openspec/` can be owned by root, so a host write fails with permission denied. Fix ownership with `sudo chown -R $(id -u):$(id -g) openspec/` before writing — never write elsewhere to dodge it.

# The `holds` gate: a `do-not-merge` needs a NAMED remedy, and cited proofs must bind to the LIVE head

`scripts/check_holds.py` reds the `holds` check for two independent reasons, and one PR can carry
them together — fix BOTH before re-running or the second one keeps the check red:

- **`gate-red` — a `do-not-merge` label that names no remedy.** The label alone is not a hold; the gate
demands the PR state the concrete thing that makes the tag removable. Post it as a PR **comment**
(`gh pr comment <n> -F body.md` — `-f` treats the argument as a raw string and mangles newlines).
`check_holds` reads the comment thread, not only the PR body.
- **`superseded-proof` — a cited run id whose `head_sha` predates the PR's live head.** The citation can
live in the body OR in any comment; rewriting the body while the old comment still quotes the stale run
id leaves it red. Grep the PR's comments for the run id, then edit/rewrite that comment so it cites no
run at a superseded head. Do NOT `git commit --amend` an ancestor commit to change a citation — that
rewrites every descendant sha and dangles the run for real.

Prove both locally before dispatching anything: `python3 scripts/check_holds.py report` must print
`0 need attention` and list `#<n>: #<blocking-PR>` as the remedy. An expired hold and an abandoned hold
read identically (`mergeable_state=BLOCKED`) on the board, so name the removal condition explicitly —
that is what makes the tag a tracked exit instead of an abandonment.

**A fully-green PR that still reports `mergeable_state=blocked`, or `unstable` with no red checks, is
being held by the LABEL, not by CI.** Read `.labels` first; hunting a phantom failing check on a PR
whose only blocker is `do-not-merge` wastes the whole pass.

# A fix PR's openspec/unit/scope reds are usually ONE unticked-proof-box gate

After rebasing a proof-gated fix PR, `linux / openspec`, `linux / unit`, `linux / scope` and
`ci-verdict` can all read red at once. Before diagnosing a rebase breakage, grep the failing job log
for `openspec-tasks` — if it says `FAIL <change>: unchecked task checkbox(es) at lines [...]`, every
red is that single gate: unit/scope/ci-verdict only propagate it. Those checkboxes are the proof boxes
that stay unticked until a real proof run at the merged head, so the PR is in its intended
acceptance state, not broken. Confirm the concrete gates passed (`312 passed, 0 failed`, install,
lint ✓) and report the unticked boxes as the reason, never as "rebase broke CI".

**Never tick a proof box on demand without a COMPLETED run at the merged head.** A coordinator can
order the boxes ticked "with the run evidence at <sha>" when no such run exists (a fork branch's
engine-build never dispatches — dispatch is asimov-agent-ref-only, and the new-params tag only
computes once the params land on `main`). Ticking against a sha with no COMPLETED engine-build run
fabricates the proof the whole gate exists to verify. Hold the line: keep the boxes unticked, tell
the coordinator the run does not exist at any head, and name the real sequence (owner merges →
`push=false` run at the merged head → `push=true` for the publish box → tick 5/6/9 with the real run
ids + sha → re-read scope green). A repeated order is not evidence; an order with a concrete run id
whose `head_sha` == the merged head is.

**`linux / unit` reaches that gate through `issue-bot-gates`, not `linux / openspec` alone.** The unit
job runs `make ci-unit`, whose tail calls `issue-bot-gates` → `openspec-tasks-check` (Makefile); when the
change has unticked boxes the log ends with `[issue-bot-gates] FAIL \`make openspec-tasks-check\` (exit 2):
the branch is NOT pushed`. That "branch is NOT pushed" clause is a stock diagnostic string, a decoy — the
real `Error 1` is `openspec-tasks-check` at `Makefile:1408` naming the unchecked-box lines. Read the exit
to classify, never the sentence. In `ci-unit` the pytest suite (`[unit-suite]`) runs FIRST: assert its
summary line (`N passed, M deselected`) before calling the unit red a test failure — a passing suite plus
an openspec exit means the code is clean and only the proof boxes remain.

**Fetch the failing job's log with `gh run view`, not the jobs/logs API.**
`gh api repos/O/R/actions/jobs/<job-id>/logs` does not return the log: the body comes back EMPTY and the
stderr names terminal escape sequences ("pass --allow-escape-sequences to output it anyway"). Setting an
env var does not change it, and piping the same URL through a different caller does not either — do not
burn turns on that endpoint. Use `gh run view <run-id> --job <job-id> --log-failed --repo O/R` (strips
ANSI, returns the failed step), and pass the **numeric job id** (`.../actions/jobs/<id>` in the run JSON),
not the job name.

**When no log is reachable at all, classify from check-run metadata — that is enough for this gate.**
`.../commits/<sha>/check-runs` gives per-check `name`, `status`, `conclusion`, `head_sha`,
`completed_at`, and you already know what distinguishes the two shapes: every red belonging to ONE run
directory and the `holds` check green + `mergeable=true` = the intended unticked-proof-boxes gate; a red
that flipped `success`→`failure` across your own push = a candidate regression. Reading those fields is
sufficient to report honestly without ever opening a log.

**Prove it is not a rebase regression before saying so.** Compare the SAME job at the PREVIOUS head's
run: `gh run view <old-run-id> --json jobs --jq '.jobs[]|[.name,.conclusion]|@tsv'`. If `linux / unit`
(or any prop) already read `failure` at the old head, the red is standing intended state that survived
the rebase — report it as re-measured-on-the-fresh-base, NOT as breakage the rebase introduced. Only a
job that flipped `success`→`failure` across the rebase is a candidate regression.

# Refresh a red `holds` leg: remedy + stale-run citation, not just a re-run

`check_holds.py` reds a PR for TWO independent reasons, and fixing one leaves the gate red:

1. **gate-red** — a `do-not-merge` label whose remedy is unnamed. Fix = a PR comment naming the
   blocker explicitly (e.g. `blocked by #1568; remove when #1568 merges`) — the check reads the
   remedy from comments, not only the body.
2. **superseded-proof** — any cited run id (`41498340459`) whose head predates the PR's current
   head. The citation can live in a **comment**, not just the body; a body edit alone leaves it. Patch
   the stale comment in place and drop or rebind the run id.

Verify locally first: `python3 scripts/check_holds.py report` must print `<pr>: <remedy>` with
`0 need attention`. A `workflow_dispatch` of `holds` does NOT attach to the PR's check suite —
green an existing red check-run with `gh run rerun <run-id> --repo OWNER/REPO --failed`, then poll
`.../actions/runs/<id>` for the conclusion.

# Another lane asks permission before rewriting YOUR branch — answer with measured facts, then comment it

A rebase/merge-conflict lane announces before touching a branch you own (per the announce-first rule)
and asks two things: are you mid-edit / is a run live at the head, and what is your conflict
preference. Answer BOTH, but measure first — their cited base and head are routinely a few pushes stale:

1. `gh api repos/O/R/pulls/<n> --jq '{head:.head.sha,base:.base.sha,mergeable}'` — answer from the sha
   you just read, not the one in their message.
2. `.../commits/<live-sha>/check-runs` filtered to `status=in_progress` — an empty result is the only
   thing that licenses "go ahead"; a live run means wait (#1015), even when the edit is tiny.
3. State the conflict preference as a rule, not a vibe: "take the branch's <issue-intent> for any
   overlapping file, use the generator for the index class" — and name the exact file the intent lives
   in so the other lane does not re-derive it.
4. **Explicitly tell them NOT to fix the intended gate.** Fresh failure on `openspec`/`unit`/`scope`/
   `ci-verdict` at your head is the unticked-proof-boxes state (see above), not their rebase's debt; a
   helpful lane that "ticks the boxes" or amends code to greenen them fabricates proof. Say it in the
   reply so it is not a surprise after their push.
5. Bookend: DM the lane AND post the same decision as an issue comment — a decision that exists only in
a DM does not exist for the next reader. Never merge/arm from this exchange; the rebase lane owns the
push.

# A lane's "FINISH" is falsifiable — check the sha identity and the body before accepting it

A rebase/conflict lane reporting "rebased + pushed, FINISH" is a CLAIM with two measurable halves,
and both are one API read each:

- **An unchanged head sha PROVES no rebase happened.** Git is content-addressed: replaying commits
  onto a different base rewrites their parents, so the tip sha MUST change. If the lane's "new head"
  equals a sha you already had (`git cat-file -t <sha>` confirms it exists but it is not the branch
  head), nothing was rebased — the force-push "succeeded" by pushing the same tree. Confirm with
  `gh api repos/O/R/branches/<branch> --jq .commit.sha` and `gh pr view <n> --json headRefOid,baseSha`:
  a `baseSha` that is still N merges behind current main is the same defect, not a stale read.
- **A claimed body refresh MUST be read back.** `gh api repos/O/R/pulls/<n> --jq .body`. A lane can
  report "refreshed BASE/AGENTS to current main" while the body is empty or still cites the old base.
  An EMPTY body is precisely what reds `check-pr-agents-line` (issue #792), so "scope + ci-verdict
  failure" together with an empty body is that gate — never a code defect to debug.

When both checks falsify the claim, take the repair yourself (the branch is yours), then release the
other lane explicitly so nobody re-rewrites it:

1. Rebase onto fresh `origin/main` in your own worktree; verify `git merge-base origin/main HEAD`
   equals the tip and `git diff --stat origin/main HEAD` still lists the PR's own files.
2. Attach the detached rebased head to a branch with `git checkout -B <branch>`, then push with an
   EXPLICIT lease naming the remote sha you just read:
   `git push --force-with-lease=<branch>:<remote-sha> origin <branch>`.
3. Re-edit the body from `make bot-preflight` run at the NEW head (AGENTS sha follows the head; BASE
   is origin/main at open). `bot-preflight` reads the local HEAD, so it emits a wrong AGENTS sha
   whenever HEAD is not genuinely rebased onto origin/main — rebase first, then run it.
4. Post the measured state on the PR (the durable record) and DM the lane "do not re-rebase or
   force-push; head <sha> is live", naming what was falsified. A DM is delivery, the PR comment is
   the record — post both, and never resend a DM that came back durably queued.

# A `fix(engines)` PR must branch on the CANONICAL repo, never the fork

`engine-build-pr-trigger` refuses a foreign (fork) head: a fork-headed engine-change PR can never start
the `push=true` producer that builds and publishes its cells, so it only waits forever and can never
prove or publish its own cells no matter how green its other checks read. Open the branch on the
canonical repo (`asimov-agent/llgenie`, push to `origin`), and read the PR's `head.repo.full_name`
back == `asimov-agent/llgenie` before relying on the trigger. A fork-head engine PR is a dead vehicle —
re-open it in-repo rather than debugging the trigger.

The rule must live in BOTH versioned artifacts under `agents/<profile>/` — the lane `SOUL.md` AND the
tree's `SKILL.md` — not only in the local profile skill: the owner counts a behaviour change as landed
when both repo files carry it. `make sync-agent-profile PROFILE=<p> CHECK=1` compares the live profile
against the repo tree and commonly reports pre-existing drift in unrelated files (a sparse repo
`agents/` subtree vs a full live profile) — read the diff and confirm only YOUR files differ as
intended; that drift is not your change reding.

# A `make ci-unit` red from `issue_bot_gates`: a moved gate leaves a STALE `DEFERRED` entry

`linux / unit` reds `tests/test_issue_bot_gates.py::test_the_real_tree_is_wired` when a gate that
`ci-unit` no longer invokes (`make <gate>`) is still listed in `scripts/issue_bot_gates.py` as
`DEFERRED` with a reason claiming ci-unit runs it. Moving a gate OUT of `ci-unit` (e.g. into its own
`ci.yml` job) requires deleting that `DEFERRED` dict entry — the gate's own message says `- delete the
entry`. Symptom chain: `make ci-unit` exit 2 → the wiring test fails with `DEFERRED['<gate>'] is
stale: ci-unit does not run make <gate>` → delete the entry, re-run. If the gate SHOULD stay in unit
instead, restore the `$(MAKE) <gate>` line; pick per intent and never leave the dict and the Makefile
disagreeing. Verify in the hermetic container
(`docker run --rm -u root -v "$PWD":/repo:rw -w /repo llgenie/test:latest python -m pytest tests/test_issue_bot_gates.py`)
— a bare host pytest is unrepresentative here.

# Squash a PR branch to ONE commit, then force-push it

When the owner asks to collapse a multi-commit PR (plus any uncommitted working-tree fix) into a
single atomic commit, do NOT hand-craft a `rebase -i`/`squash`; the soft-reset is exact and fast:

1. Stage everything, including the uncommitted fix: `git add <files>` (confirm with `git status --short`
   + `git diff --cached --stat` that only the intended paths are staged).
2. `git reset --soft origin/main` — moves HEAD to main while KEEPING the whole branch delta (every
   prior commit's tree + the staged change) in the index. `git rev-list --count origin/main..HEAD`
   then reads `0` and the index holds the full changeset; `git diff --cached --stat` is the proof.
3. Write the message to a file and `git commit -F /tmp/msg.txt`. The message keeps the `closes #N`
   (or `Closes #N.`) claim — the check-pr-closing gate reads it.
4. Push with a lease against the real head: `git push --force-with-lease origin HEAD:refs/heads/<pr-branch>`.
   Engine-build has `cancel-in-progress: false`, so this queues a rebuild rather than cancelling the
   live producer — a squash push during an in-flight build is safe here (unlike a `cancel-in-progress:
   true` workflow).

Verify all four after the push — a moved sha alone proves nothing:
- `gh pr view <n> --json headRefOid` == the new local HEAD.
- `gh pr view <n> --json commits` count == 1 (proves the squash actually collapsed, not just a move).
- The pushed CONTENT carries the fix, not just the sha: `gh api repos/O/R/contents/<path>?ref=<sha>` →
  `base64 -d` → `grep -c '<symbol>'`.
- The author is an allowlisted identity: `git log -1 --format='%an <%ae>'`.

- **Write commit/body/message files under `/tmp`, never inside the checkout.** A path that routes
  through `.git/..` silently normalizes to `.git` and the write fails (`File exists: …/.git`). The
  worktree is not a scratch pad; `/tmp` is.
- **Never dump `git branch -vv` (or `git branch -a`) in this repo — it prints well over 100 KB of
  stale branches and burns the context in one call.** To learn your branch's tracking use
  `git rev-parse --abbrev-ref HEAD` + `git rev-parse @{u}`, or `git status -sb`; target one ref with
  `git rev-parse origin/<branch>`.
- **A force-push that rewrites the head CLEARS a previously armed auto-merge** — the arm binds the old
  head's `enabledAt`. After a squash/force-push, re-read `autoMergeRequest`; if null, re-arm
  (`gh pr merge <n> --squash --auto`) and read it back. Do not assume the arm survived the rewrite.
  The converse holds: a **plain fast-forward push** (adding a commit on top of the current head, no
  rewrite) keeps `autoMergeRequest` armed (same `enabledAt`) — you do NOT need to re-arm, only re-read
  the new head sha. With `cancel-in-progress: false`, that push fires a fresh automatic producer at the
  new head while the old one drains, so the trim/fix gets its own build proof at the exact sha you
  pushed. After any push type, verify `headRefOid` == the sha you pushed and quote the live producer
  run id at that head — never assume "armed" or "triggered" from the exit code.

## Already ONE commit over main: amend, do not re-squash

When asked to "squash and force-push again", count first: `git rev-list --count origin/main..HEAD`.
`1` means there is nothing to squash — `reset --soft origin/main` just rebuilds the same commit and
rewrites every sha for no reason. Fold new work in with
`git add <files> && git commit --amend -F /tmp/msg.txt` (keeping the `closes #N` claim and the author
identity), then `git push --force-with-lease origin HEAD:refs/heads/<branch>`. Report the observed
count (`1 commit over main`) instead of performing a redundant rewrite.

- **An amend message file under `/tmp` is read-before-write guarded.** A message file written in an
  earlier turn cannot be blindly rewritten (`write_file` refuses: "exists but this task has not seen its
  full current content"). `read_file` it, then `patch` the one section to add — that preserves the rest
  of the message and satisfies the guard in one step.
- **After a force-push the PR API's `headRefOid` reads the OLD sha for a few seconds.** A single read can
  look like a failed push. Poll until it equals your local `git rev-parse HEAD` before reporting, and key
  any run watcher on that new full sha (the runs at the old head are superseded, not pending work).
