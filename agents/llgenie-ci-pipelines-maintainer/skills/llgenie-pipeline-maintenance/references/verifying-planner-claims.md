# Verifying a planner claim against canonical git

Planner reports arrive as DMs from `@llgenie-planner`. They are measurements made in
*their* environment, and that environment can differ from yours. Before acting on a
claim that a branch is missing, a run never happened, or a PR is unmerged, **re-measure
against the canonical repo yourself**. Two failure modes are common and both cost a
wrong action if taken on trust.

## 1. `origin` may not be canonical

The canonical remote is `asimov-agent/llgenie`. A fork named `origin` is **not** upstream.
A planner `git ls-remote origin refs/heads/<branch>` returning EMPTY can simply mean their
`origin` points at a fork, or their snapshot predates the push. Verify with an explicitly
canonical query:

    git ls-remote https://github.com/asimov-agent/llgenie refs/heads/<branch>
    gh api repos/asimov-agent/llgenie/git/ref/heads/<branch> --jq .object.sha

If that returns a sha, the heads-ref exists and there is nothing to "restore".

## 2. A stale head is not the vehicle head

GitHub stores the PR's *current* head in `headRefOid`; an older sha (often the first red
push) still resolves via `refs/pull/<n>/head` only while it is the head. If the planner
measures `actions/runs?head_sha=<old>` and reports `total=0`, first check whether that sha
is the superseded v1 commit. Measure the real vehicle head:

    gh pr view <n> --repo asimov-agent/llgenie \
      --json state,mergedAt,mergeCommit,mergedBy,headRefOid \
      --jq '{state,merged_at:.mergedAt,merge_sha:.mergeCommit.oid,merged_by:.mergedBy.login,head:.headRefOid}'
    gh api "repos/asimov-agent/llgenie/actions/runs?head_sha=<headRefOid>" --jq '.total_count, (.workflow_runs[]|{id,name,status,conclusion})'

A red run on the dead v1 sha is historical and irrelevant once the head moved and merged.

**A cited head may belong to NO PR at all — a claim of "PR X is not green at head H" is settled by proving H is X's head before you concede it.** A stale-dated DM can attach a run/head measured in a totally different context to the PR it names: measured here, a message said "#1742 is not green, head `d5625689`, run `<id>` (event=pull_request)" while #1742 had MERGED under a *different* head `8482c24b` (branch deleted), and `d5625689` appeared as the head of no PR in `gh pr list --state all` through the current frontier. The named PR's `headRefOid` (`gh pr view <n> --json headRefOid`) not matching the cited H, plus a `gh pr list --state all --json number,headRefOid` sweep that finds H on no PR, means the claim is misattributed, not a live red. Do NOT reconcile (rebase/amend/re-push) against a head that is not the PR's head — on a merged PR there is no branch and #824 forbids a re-cut. Reply with the mapping (`#n` head vs cited H, the cited run's `head_sha`/`event`, and what the trunk tip is now), and ask which PR the finding actually belongs to if it is real. If it must be re-checked for hygiene (a body-shape re-read), say so and do it as a read, never as a queue-blocking reconcile instruction you cannot execute.

## 3. Merged is the state that ends the question

Before re-pushing, re-arming, or "restoring" anything, read `state`. If `state:MERGED`,
the work is landed: a re-push resurrects a dead commit or races the merge, and arming is
moot. The repo's own auto-merge (actor `asimov-agent`) lands approved green PRs — that is
not a lane self-merge. Record the proving facts, not the badge: `state`, `mergeCommit.oid`,
`mergedBy.login`, `mergedAt`, the green run id at `headRefOid`, and
`git cat-file -e upstream/main:<path>` for the file that was supposed to land.

## 4. "Unclaimed / no branch / no PR / assignees ()" is not proof of no vehicle

A planner board that keeps re-forcing an issue as "unclaimed, branchless, no PR" may key
on `assignees`, which stays empty for a lane whose bot id is **not a GitHub login**.
`llgenie-ci-pipelines-maintainer` (the bot's id) is not an assignable user — a
`POST /issues/<n>/assignees -f assignees=llgenie-ci-pipelines-maintainer` returns 200 but
leaves `assignees:[]`. Do not "prove" the claim by assigning a human; prove it by the
vehicle link GitHub already synced:

    gh issue view <n> --repo asimov-agent/llgenie --json closedByPullRequestsReferences \
      --jq '{closingPRs:[.closedByPullRequestsReferences[]|{num:.number}],assignees:(.assignees|length)}'

a `closingPRs:[{num:<pr>}]` entry means the PR cross-links the issue as its closer — a
single, authoritative vehicle, regardless of `assignees:0`. (`closingIssuesReferences` is
not a valid `gh issue view` field; use `closedByPullRequestsReferences`.) Post one
API-quoted comment on the issue naming the PR + the measured head, then **stop** — do not
DM-argue the same stale read past ~3 corrections (no-ping-pong / max-3 discipline). The
issue comment plus the synced closer-link is the durable record; a looping planner board
does not change it.

## 5. "The single open vehicle" may be a CLOSED PR — list ALL PRs before you force-push

A planner force-push directive can name the wrong vehicle. It may call a **closed** PR
"the single existing open vehicle" (and even cite a head sha that does not match that
branch's live tip), while the branch it names was pushed under a *different* closed PR and
the actual open implementation is a separate PR entirely. Conflated issue/PR numbers and a
closed-PR branch are both real. Before any force-push, enumerate every PR touching the
issue and read each `state`:

    gh pr list --repo asimov-agent/llgenie --state all --search "<issue#> in:body,title" \
      --json number,state,headRefName,headRefOid,title \
      --jq '.[]|"PR#\(.number) \(.state) \(.headRefName) @\(.headRefOid[0:8]) \(.title)"'
    gh issue view <issue#> --repo asimov-agent/llgenie --json state,labels --jq '{state,labels:[.labels[].name]}'

A force-push onto a CLOSED PR's branch does **not** reopen the PR and cannot "keep it as
the one vehicle" — it is a dead branch. If exactly one PR is OPEN, that one is the vehicle
and there is nothing to force-push; state the measured contradiction to the planner (PR#,
state, head, branch-tip-vs-stored-head mismatch) and hold. Never force-push on a premise
`state:CLOSED` disproves.

**A dispatched ISSUE can already be CLOSED/completed — read the issue's own `state` before you build anything.** A planner dispatch that hands you "new refined issue #N for your lane" may be a stale re-narration: another lane's PR already implemented #N and its merge auto-closed the issue (`state_reason:completed`). Building a vehicle then is the duplicate-vehicle failure at the *issue* level, not the PR level. Before the first branch, measure the issue itself and the PRs that closed it:

    gh api repos/asimov-agent/llgenie/issues/<N> --jq '{state,state_reason,closed_at,created_at}'
    gh api "search/issues?q=repo:asimov-agent/llgenie+<N>+is:pr" --jq '.items[]|{number,title,state,merged_at}'
    gh api "repos/asimov-agent/llgenie/issues/<N>/timeline" \
      --jq '.[]|select(.event=="closed")|{event,created_at,commit_id}'
    gh pr view <pr> --repo asimov-agent/llgenie --json state,mergedAt,mergeCommit --jq '{state,mergedAt,merge:.mergeCommit.oid}'

If `state:closed` + `state_reason:completed` and that merge commit is on canonical main (`git -C <repo> log --oneline -3 <merge_sha>` shows the `(#<N>)` closure), the acceptance criteria are already met — prove they are by naming the shipped make target / guard function on main (`git show <merge_sha>:Makefile | grep -n <target>`, `git show <merge_sha>:scripts/<file>` for the gate). Then post the measured finding on the issue (closed state, closing PR, merge sha = current tip, the gate file:line) and tell the planner you built **no** second vehicle. Only if the planner names a specific acceptance clause that genuinely is NOT on main do you take it — ask for that clause plus the failing command.

**Your OWN vehicle can be closed unmerged while the issue still ships through a broader vehicle — verify the live one rather than reopening yours.** An owner consolidating, or a wider PR superseding your narrow one, leaves your `state:CLOSED` + `mergedAt:null` yet the issue delivered. Confirm the LIVE vehicle carries your fix: `gh pr diff <live> | grep '^diff --git'` for the file you fixed, read the trigger/guard at its head (`git show m<live>:<path>`), and run ITS guard tests on ITS tree (see `verification.md` §8). Report the measured board (live vehicle + head sha + passing guard + any residual red, which may be a shared tracked defect). Do NOT reopen your closed PR beside an open one (duplicate vehicle), edit the owner's branch, or invent a commit/change-note to look delivered.

## 6. A held "aligned / nothing owed" state EXPIRES the moment a merge lands — re-measure the tip every time

The most expensive error is not a wrong measurement, it is a **stale one that felt settled**. A
multi-turn "aligned, serene, nothing owed" hold is only true at the sha it was measured at: a
merge on trunk (a census/scope/unblock fix landing, any PR the fleet was waiting on) moves
`origin/main` past the base of every open PR, so a PR that read `MERGEABLE` an hour ago now reads
`CONFLICTING`/`DIRTY` with green head checks. Never re-assert alignment from memory, a prior
comment, or a chat-quoted sha. Before any "still aligned" reply, re-measure the moving parts:

    git ls-remote <canonical> refs/heads/main        # canonical tip RIGHT NOW (no local-ref ambiguity)
    gh pr view <n> --repo asimov-agent/llgenie --json mergeable,mergeStateStatus,headRefOid,baseRefName

The tell that a hold has silently expired: the PR's own head check-runs are all green yet GitHub
says `mergeable:CONFLICTING` — that is never a failing test, it is a rebase-against-new-trunk
conflict. Confirm the intersect and route it:

    git diff --name-only <old-base> <head> | sort > /tmp/h
    git diff --name-only <old-base> <new-tip> | sort > /tmp/m
    comm -12 /tmp/h /tmp/m                          # the exact conflicting path(s)

Report the finding on the PR (head + intersect + canonical tip), then hand the rebase to the
rebase lane and tell the planner — do NOT rebase it yourself (rebase is another lane's job).

## 7. Ambiguous local refs poison merge-base and rev-list — measure with explicit SHAs

A local ref name can resolve to two different objects (`refs/heads/prNNN` vs
`refs/remotes/prNNN`), and git prints `warning: refname 'prNNN' is ambiguous` yet still returns
*an* answer — often a contradictory one: `merge-base` and `rev-list --count` against the same
symbolic name disagree because each subcommand resolves it in a different namespace. Two rules:

- For the trunk tip, use `git ls-remote <canonical> refs/heads/main` (a sha, never a local ref).
- For the PR head, take `headRefOid` from `gh pr view`, then compute divergence on the **full
  SHAs** the API and ls-remote returned, not on branch names: `git merge-base <headSha> <mainSha>`
  and `git rev-list --count <mainSha>..<headSha>`. `git merge-base --is-ancestor <mainSha> <headSha>`
  is the one-bit answer to "behind vs on-top".

Also: `origin` on this host is the **fork** (`andyholst/llgenie`); canonical is `upstream`
(`asimov-agent/llgenie`). Fetch/resolve the canonical tip from `upstream`, never `origin`.

## 8. A DM stream can be BACKDATED — and a settled close earns zero further replies

Planner DMs are not delivered in the order they were composed. A message that reads "PR #N is
OPEN at the old head, scope is RED, here is the failing step" can be **older than the board you
already measured** — it was composed before your push and delivered after your merge. Delivery
time is not evidence of message age; only the content is, and stale content is indistinguishable
from fresh content in the render.

The handling is fixed and short:

1. Verify ONCE per loop, not per message: `gh pr view <n> --json state,mergedAt,mergeCommit`
   and `git ls-remote <canonical> refs/heads/main`. If `state:MERGED`, the DM's premise is dead
   regardless of its framing.
2. Reply ONCE with the sha-bound board fact (state, merge commit, closing issue state, the green
   run id at the merged head). That reply is the durable answer for every replay of the same loop.
3. Then go silent. Not an ack, not a re-verify, not a "confirmed, standing by" — a settled close
   that gets echoed five times is answered once. Repeated acks are indistinguishable from ping-pong
   and they cost tool loops on a question the board closed.
4. When the planner states its own settled close ("loop closed", "no reply owed", "I will not repeat
   this"), that is a terminal state: no reply at all, and no tool call unless a NEW id or sha appears
   in the message.

The same applies to gatebook-adjacent traffic you do not otherwise see: **replayed background-process
completion notifications are not new work.** A `proc_*` completion for a run you already consumed
(a gate loop, a `make` target) replays verbatim; consuming it a second time means re-running gates on
a landed tree. Recognise it by the command matching a run already judged, and drop it silently.

## 9. A relayed drift claim arrives over-broad — measure the artefact PER CELL, post-merge

"The change note's site table line numbers drifted after the merge" is a claim about a SET, and relays
routinely report it as uniform ("across the board", "all of them"). Measure every cell against the
MERGED tree before acting — most are usually already correct, and the fix is the one that moved:

```bash
git fetch upstream main && git -C <repo> show upstream/main:<note-path> | grep -nE '^\|'   # the documented rows
grep -n '<marker>' .github/workflows/*.yml                                                 # the truth in the tree
```

A fix PR that ADDS lines near a documented site (suppression comments, extra steps) shifts exactly the
numbers at and after it, so expect an off-by-one in one cell, not a rewrite. Report the measured truth
("seven of eight match; `security-scan.yml:144` is now `145`") rather than repeating the relay's framing.

**When the fixing PR is already merged, folding is impossible — the honest vehicle is a tiny docs-only
follow-up PR**, three files (`agent-wiki/<stem>.md`, its `docs/changes.d/` row, regenerated
`CHANGES.md`), no workflow YAML touched. `closes #<n>` in both commit and body when the issue is already
closed is a no-op and safe; validate before push with
`python3 scripts/check_pr_closing.py check --base <merged-merge-sha> --rev HEAD`, plus
`lint_linefeeds` and `check_docs`. Then open it ready-for-review (never draft) and tell the planner the
PR, head sha, and which single number actually moved.

## 10. A red run cited as "POST-MERGE at main" can have executed a PRE-FIX tree — prove ancestry before you acknowledge a regression

A `workflow_run` workflow checks out whatever `main`'s head was when the triggering event
fired, so a red `ci-verdict`/`scope` job on a busy branch pins an OLD head that can
PREDATE the very fix the issue claims is missing. The scheduler may quote run id + job id +
log line and call it "reproduced POST-MERGE at main" — a smoke-tested framing that is true
about the run and false about the tree it ran on.

Decisive probes (do all three before acknowledging or cutting anything):

    git fetch upstream main                    # canonical tip right now
    git merge-base --is-ancestor <the-fix-commit> <run-head-sha>
    # NO  → the run executed the OLD tree; the red proves the old bug, not a current regression
    # YES → the fix is in that tree; now actually reproduce before believing

    git -C <repo> show <run-head-sha>:scripts/<file>   # the guard CODE the run really ran

And prove the CURRENT head does not red, live:

    python3 - <<'PY'
    import importlib.util
    spec = importlib.util.spec_from_file_location('cv','scripts/ci_verdict.py')
    cv = importlib.util.module_from_spec(spec); spec.loader.exec_module(cv)
    rows = cv.branch_runs('asimov-agent/llgenie','main',per_page=100)
    print('returned', len(rows), 'rows WITHOUT raising')
    PY

a guard that returns rows without raising on a >2500-run listing is silent on a healthy
listing — the smoking gun that the red came from pre-fix code, not a current defect.
Report both halves: (1) `merge-base --is-ancestor <fix> <run-head>` = NO, so the run's tree
predates the fix (list the commits between them), and (2) the live no-red of the current
head's own function. Same discipline as verifying a merge: cite the run's `head_sha` and the
checked-out guard code, never the run's verdict line alone.

## 11. A `CI` run red in ~15s with only `guard` failing and every build job `skipped` is a pre-flight REFUSAL, not a test red

The `CI` workflow's first job is `guard`, whose cheap `make check-pr-base` runs before the
matrix. When it refuses, every downstream job (`linux`, `ci-images`, `scanner-images`) is
`skipped` and the run's final `conclusion` still reads `failure` — so the PR badge says red
while no test ever ran. Never read that as a code failure and never re-run the matrix; read
the `guard` job log:

    gh api repos/asimov-agent/llgenie/actions/runs/<id>/jobs --jq '.jobs[]|{name,conclusion,id}'
    gh api repos/asimov-agent/llgenie/actions/jobs/<guard-job-id>/logs --allow-escape-sequences 2>/dev/null \
      | grep -E 'check-pr-base|Error 1|##\[error\]'

The common refusal is `check-pr-base` telling you to "rebase onto a fresh `origin/main` before
pushing": your branch's merge-base with canonical main is BEHIND the current `main` tip (a
merge landed after you cut the branch), so the diff the PR would close leaks unrelated commits.
The fix is a rebase onto the LIVE tip, not a re-run:

    git fetch upstream main && git rebase upstream/main
    python3 scripts/check_docs.py check                       # CHANGES.md may need regen if main touched it
    python3 scripts/<your-gate>.py check                       # re-verify your own gate on the rebased tree
    git push --force-with-lease origin <branch>                # never --force without the lease

Then confirm `guard` AND `holds` go green at the new `headRefOid` — a stale-base guard and a
held PR are the two fast-fails that keep every real job `skipped`. (If the PR is another
lane's ongoing work, hand the rebase to the rebase lane per the lane rule; when it is your own
pipeline-file fix vehicle, the rebase is part of keeping that vehicle current.)

## 12. A planner-named run id can 404 on canonical — corroborate the CLAIM through the workflow's own job durations, never through the cited id

A planner dispatch that routes a real finding often carries a run id measured in *their* environment; that id can `404` on `asimov-agent/llgenie` (a fork's run, a pruned run, or a number they typed). The 404 is **not** the finding being false — it only means the cited handle is unusable. Do not reply "run not found" and do not accept the claim on trust: re-derive the substantive claim from runs that DO resolve. For a "this job overruns / was cancelled at its cap" class, measure per-JOB durations across the workflow's own history:

    gh run list --repo asimov-agent/llgenie --workflow <wf>.yml --limit 40 --json databaseId --jq '.[].databaseId' \
      | while read rid; do gh run view $rid --repo asimov-agent/llgenie --json jobs \
          --jq '.jobs[]|select(.name|test("<cell>"))|"\(.databaseId) \(.conclusion) \(.startedAt)->\(.completedAt)"'; done

A `cancelled` job whose `started->completed` equals the workflow's `timeout-minutes` is a kill at the wall (UNTESTED, never green); a `success` band in the same cell (min/p50/max) tells you whether an overrun is real and how big the headroom must be. Report the measured band and the cancelled-at-wall jobs as the proof, and say plainly the cited id 404'd — the correlation is proven by the cell's own history, not by the handle the planner guessed.

## 13. "test X FAILS at head H — fix the fixture and push" is settled by RUNNING that test at MERGED main, not by regenerating at H

A peer/planner can escalate a stale-head dispute into a concrete, plausible failure claim:
"`tests/test_x.py::<named test>` reds at head `<H>` (assert rc==0 got 1==0), you carried a
broken fixture — regenerate `<fixture>` and push to the same branch `<H>`/`<base>`." The
specificity makes it feel authoritative, but it inherits the same pre-merge snapshot: **a
sha that EXISTS as a commit is not a head that exists.** Prove the head live first —

    gh api repos/asimov-agent/llgenie/git/ref/heads/<branch> --jq '.object.sha'   # 404 = branch deleted
    gh api repos/asimov-agent/llgenie/git/matching-refs/heads/<branchprefix> --jq '.[].ref'  # [] = no such branch
    gh api pulls?state=open --jq '.[]|select(.head.sha|startswith("<H[0:8]>") or .base.sha=="<base>")'  # none = dangling

A commit reachable by sha but referenced by **no open PR and no branch** is a pre-merge
snapshot (the head the peer measured ~1.5h before the squash landed) — treat it as stale,
never as a push target (pushing there is the duplicate-vehicle error and cannot change a
merged PR).

Then settle the SUBSTANTIVE claim on the tree that actually counts — current MERGED main —
by running the EXACT test the peer named in a fresh detached worktree:

    git -C <repo> fetch upstream main && UP=$(git -C <repo> rev-parse --short upstream/main)
    git -C <repo> worktree add --detach /tmp/wt-verify upstream/main
    docker run --rm -u root -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONPATH=/repo/scripts \
      -v /tmp/wt-verify:/repo:rw -e HOME=/root -w /repo llgenie/test:latest \
      python -m pytest "tests/test_x.py::<named test>" -q 2>&1 | tail -3

If it passes at merged main (`1 passed`), the peer's failure is phantom: report the measured
green (test id + count + main sha) plus the wire facts (PR state/merge sha, branch 404,
dangling head), and do NOT regenerate a fixture for a branch that no longer exists. If it
actually reds at current main, THAT is a real post-merge defect — surface it as its own
finding (with the run/test clip), never as a push to the dead head.

`docker run` as root leaves `.pytest_cache/` and `__pycache__/` **root-owned**, so
`git worktree remove /tmp/wt-verify` and `rm -rf` then fail `Permission denied` (and sudo
needs a tty you may not have). Pre-empt with `-e PYTHONDONTWRITEBYTECODE=1 -p no:cacheprovider`;
if residue is already there, `sudo chown -R $USER:$USER /tmp/wt-verify` first. Even when the
remove fails, `git worktree list --porcelain` drops the registration (`registered: 0`), so the
dir does not clutter git — clean-as-far-as-possible on YOUR OWN temp worktree and note it;
never touch another lane's registered worktree.

## 14. A peer's cited EVIDENCE MARKER FILES may not exist — re-run the gate, never quote the cited RC

A peer lane (planner, rebase-lane handoff) can report "the proof is on disk in your worktree — `PZ.txt` = the pre-fix red, `SUITE.txt`/`G_DOCS.txt`/`G_LINT.txt`/`G_WF.txt`/`G_WIRING.txt` = the green RCs; just name them in your report." Those files are frequently a **phantom of the peer's own read channel** — measured here, all were absent from the worktree, `/tmp`, home and the repo root while only an empty `HEADD.txt` was there. The peer is not lying about the *fact* (the suite WAS green); it is citing an artefact that never landed.

The failure this invites is fabricating the values — writing "SUITE RC=0, G_DOCS RC=0 …" from the peer's memory of a run. Do **not**. When asked to "name the RC" of markers you cannot find, produce the number by running the gate yourself right then; that is fast, real, and what the PR body must assert:

```bash
cd <worktree>
make check-workflows    # G_WF
make check-wiring       # G_WIRING
make check-docs         # G_DOCS
make lint               # G_LINT
# the unit proof runs in the CONTAINER, not the host venv (the host venv has no pytest):
docker run --rm -u root -e PYTHONPATH=/repo/scripts -v "$PWD":/repo:rw -w /repo -e HOME=/root \
  llgenie/test:latest python -m pytest tests/<the_test>.py -q -p no:cacheprovider
```

Report those measured RCs and say plainly the named files do not exist (a read-channel artefact), rather than inventing their contents or accepting the peer's premise wholesale. A number is only a number you measured at a named sha.

## Rule

Never act (push, arm, delete, restore) on a planner anomaly you have not reproduced
against `asimov-agent/llgenie`. Reply with the sha-bound measurement — PR state, real head,
the green run id, and the merge sha — and let the planner correct their board. A planner
model that loops or a fork-`origin` snapshot does not change canonical truth.

## Examples / addenda

**A merge-squash can drop a doc clause that stays TRUE in the code — assert doc against code before deciding it was a deliberate trim.** When a reviewer/rebase lane flags "your merge dropped sentence X", verify X is still true at the merged commit (e.g. job-level `env:` exists, zero workflow-level `env:` blocks) BEFORE calling it a trim. A true clause removed is an under-description and deserves its own small doc PR; a false clause removed is correct. #1618: README lost the job-level-env clause + #1594 cite + `**explicit**` bold during the 3fffbf7a->dc23de8 squash; all stayed true in the merged tree and merited restore.

**Never amend a MERGED PR's stale fork head; the legitimate vehicle is a fresh PR on current main.** If a planner instruction says "amend head X and re-read CI at that head" but the PR is merged, amend+CI is a false premise — build the fix on live upstream/main (fetch `upstream/main` first, branch from `upstream/main` in that moment, never from a chat-quoted base). #1618: "amend dc23de88" was impossible; the restore shipped as a new branch on 69b86b3.

**A NEW test file that imports a `scripts/` module must use the namespaced `import scripts.<mod>` form — never a per-file `sys.path.insert` or a bare `import <mod>`.**
The suite's ONE-import-root invariant (issue #796) is enforced by `check_import_roots.py`
ratchet (a `ci-unit` gate): a module-level `sys.path.insert` (sys-path rule) and a bare
`import check_x` of a scripts/ module (bare rule) are both refused, naming the exact
`file:line` (issue #1101). The conftest (tests/conftest.py) is the only allowed root;
siblings reach scripts via `import scripts.<mod> as <alias>` (test_ci_publish_order.py).
A test that works locally can still red CI: the truncation presents as `linux / unit` exit
code 2 deep in the suite AFTER tests pass. Verify `python3 scripts/check_import_roots.py ratchet` == 0 before pushing; if your branch ADDS sites beyond the recorded baseline, fix the import lineage (never `--update` a bootstrap you introduced).

**Terminal/execute_code channel may return NOTHING (not even `echo date`) AND may not execute side-effects.** If `date`/`echo` come back empty, stop trusting terminal actions — verify via `write_file` + `read_file` (file tools render) or `message_agent`, and do NOT claim a push/PR landed on silent output. execute_code's file writes go to a sandbox invisible to `read_file`: cross-check via a file created by `write_file`.

**A `# proc-allow:` comment must sit on the SAME line as the `subprocess.*` call** —
`scripts/check_proc_gate.py` (a `ci-unit` gate) matches the call's own line, so a
reason wrapped onto the continuation line (`subprocess.run(...,` newline `... )  # proc-allow`)
still reds the gate (`[proc-gate] 1 bare subprocess call site`). Keep the reason on the
`subprocess.run(..., .args,  # proc-allow: <reason>` line, matching every sibling.

Another shape-seam for a NEW make target in `ci-unit`: `scripts/issue_bot_gates.py`
`DEFERRED`/`FAST_GATES` must classify it or `test_issue_bot_gates::
test_the_real_tree_is_wired` reds (a gate `ci-unit` runs with no classification is a
finding, issue #475). A brand-new `ci-unit` gate therefore needs: the target + recipe
in Makefile, `.PHONY`, a `docs/` + `docs/changes.d/` + `CHANGES.md` note if user-facing,
AND either a `FAST_GATES`/`DEFERRED` entry. All four are asserted by separate tests;
land on red and CI names them one at a time.


**Measurement hygiene:** the shell's persisted cwd can point at a temp worktree you (or a
prior run) already removed, so every command dies at `cd` with exit 126 before any git runs.
Pass an explicit `workdir` (e.g. `/tmp`) and drive git with `git -C <absolute-repo-path>`, so a
poisoned `$PWD` never masks a real measurement as a failure.
