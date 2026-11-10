# Running and verifying the local gate battery

Depth for the moment between "the change works" and "the PR is green": which gates to
run on the branch, how to read their output, and the traps that make a gate look green
when it is not. SKILL.md is at its character ceiling — additions belong here.

## The trailing-newline gate (the most common self-inflicted red)

Every text file a commit adds or edits must end with exactly one `\n`. `make lint`
(== `lint_linefeeds.py`) is a hard failure and runs in the `ci-lint` stage of every CI
run. A file written by `write_file` or a heredoc ends at its last byte with no newline,
so the PR reds on `ci-lint` even when every local test and every other gate is green.

The failure line in the log reads:

    LINT FAIL — files missing a trailing newline:
    make[1]: *** [Makefile:1693: lint] Error 1

Check every changed and untracked file before committing:

```sh
{ git diff --name-only HEAD; git ls-files -o --exclude-standard; } | sort -u |
while read -r f; do
  [ ! -f "$f" ] || [ "$(tail -c 1 "$f" | od -An -c | tr -d ' ')" = '\n' ] || echo "NO NEWLINE: $f"
done
```

Fix is mechanical — `printf '\n' >> "$f"` — and the rule is per-file, not per-type: a
new `.yml` workflow, a markdown change fragment, a Python script all need it.

## The false green: `lint_linefeeds.py` inside the container

Run inside the test container against a worktree it prints
`LINT OK — all tracked text files end with a newline` **after** logging
`[lint] could not list tracked files: ['git', 'ls-files'] returned non-zero exit status 128`.
A worktree's `.git` is a file, not a directory, so `git ls-files` cannot run; the script
treats an empty listing as a pass. A guard that names no violations because it saw no
files is the exact class this lane exists to catch — do not trust it. Run the lint on
the host from the worktree directory, or use the per-file loop above.

Same shape, same handling: any gate whose output is satisfied by "zero inputs" must be
re-run where it can actually enumerate, and its input count read, before it is believed.

## Stale `check-pr-acceptance` reds: a no-code rerun, and how to sweep the board

A `check-pr-acceptance` job that reds on a run executed BEFORE a reviewer acceptance
tick is a **stale pre-tick artifact**, not a gate bug — `check-pr-acceptance` succeeds
only when the LIVE issue shows the boxes ticked. Signature: `mergeStateStatus=BLOCKED`;
statusCheckRollup all SUCCESS except ONE switch-style context (`guard` or `scope`) whose
**sole** failing step is `make check-pr-acceptance` (read `.steps[]` — every other gate
step passes). Fix is a re-runable no-code refresh: `gh run rerun <run_id> --failed`
(rc=0), then confirm `run_attempt` advanced and the run is `in_progress` BEFORE claiming
green; the rerun re-reads the now-ticked live issue and flips green. Re-verify by reading
the run's `.conclusion`=success AND the PR rollup = all SUCCESS.

**Sweep the WHOLE open board, never trust `gh pr view --json statusCheckRollup`:** its
`.state` comes back `null` for these runs (filtering on `.state` scores them red when they
are fine) and its `detailsUrl` points at the OLD run, not the head. Take each PR's
`headRefOid` and query `gh api repos/<o>/<r>/commits/<head>/check-runs`, filtering on
`.conclusion` — that is the authoritative per-head state. A red whose failing guard step is
a gate OTHER than `check-pr-acceptance` (e.g. `check-pr-openspec-change`,
`check-pr-authors`) is NOT this rescuable class — it is a genuine red owned by that PR's
lane; leave it to its owner and never rerun it into a false green. Never edit the gate.

A `check-pr-acceptance` red is rescuable by rerun ONLY when the issue's boxes are ALREADY
ticked (stale pre-tick artifact). When the boxes are still unticked because no reviewer has
verdict-ticked them yet, the rerun cannot help — that is the designed `#1644` hold; route the
verdict to the reviewing lane instead of rerunning (see the body-content gate ladder below).

## Stale-tick rerun class: what a rerun does and does NOT prove

- **A rerun is not green until you read the NEW failing step.** After
  `gh run rerun --failed`, read the rerun's OWN `.steps[]` where `conclusion!=success` —
  not just the run's `.conclusion`. A stale rerun can PASS its original gate and land on a
  DIFFERENT genuine red (a claimed-issue not adjacent-closed, `check-pr-closing`), which a
  rerun cannot clear. Posting "expected green" before that attempt-2 step read is a
  fabrication; the wire record must quote the attempt-2 failing step name.
- **CI and ci-scope are SEPARATE runs**, each holding its own guard copy and running
  `check-pr-acceptance`/`check-pr-closing` independently — a body fix owes BOTH `--failed`
  reruns, and each re-read must be checked individually.
- **"Guard job SUCCESS" is NOT "run green".** A guard-green run can still sit
  `in_progress` on an UNRELATED job. When a per-job read shows only ONE job still running,
  name that job and check it is a **design-wait** (e.g. `engine-pins` on "Wait until every
  repinned engine image is published", gated on another lane's fix) — never a job to rerun
  or cancel. A frozen `updated_at` with one in-progress job is this shape; read the job's
  current step, not the run's badge.
- **A body-edit re-validation ask is often ALREADY DONE — measure before rerunning.**
  When another lane asks you to re-run a guard after a body/§1589 edit, first read the
  run's CURRENT `run_attempt` and whether that attempt STARTED after the body-edit comment's
  `created_at`. If the attempt post-dates the edit, its guard job already re-read the
  corrected body — read that guard's `.steps[]` (the `check-pr-closing`/`check-pr-acceptance`
  step) instead of issuing another `--failed` rerun into a destructive no-op on an
  in-progress run. (Lesson: #1696 — rebase-lane negation note `6679918626` at 07:45:27Z was
  validated by my attempt-3 guard at ~07:48Z; reproduced `check_pr_closing.py` rc=0 against
  the live body/head myself; replied "no rerun owed", record `6680500626`.)

## Ordered dispatch-premise check: measure before opening a "hardening" PR

A dispatch that says "N waits are unbounded, open a PR that bounds them" must be measured against the shipped tree before any edit, on two axes:

1. **Is the wait actually unbounded?** The GitHub Jobs API exposes **no timeout field** — `.timeout` reads `null` for EVERY job regardless of the yml's `timeout-minutes` (a job with `timeout-minutes:10` in yaml still reads None), so "timeout None" is NOT "unbounded". And "in_progress since X" is a claim against the deadline MATH, not the API: a wait that passes `WAIT=N` / a `wait_min` into a loop computing `deadline = start + wait_min*60` and which FAILS ITSELF at the deadline is BOUNDED — it is only a hang if `X + wait_min` has already passed AND the job is still running. Read the yml and the script's deadline — the job's start time from `gh api repos/<o>/<r>/actions/runs/<id>/jobs --jq '.jobs[]|select(.name=="<job>")|.started_at'`, and the wait value the workflow passes (`grep -n 'WAIT=\|wait_min\|wait-minutes'` in the yml + the invoked script). A `WAIT=290` job that terminates itself with `[pins] FAIL … are not published` at start+290 min is not "hangs forever" — though ~5h of invisible in_progress is still the "hangs for hours" class worth hardening.
2. **Does the fix have a file on main?** A wait that lives only inside another lane's unmerged PR diff (grep the target: 0 hits on main, >0 on the PR head) cannot be "fixed on main" — that fix belongs in that PR and is that lane's. Open the PR only when the measured MAIN tree confirms a real gap.

Otherwise report the measurement on-wire and route the one genuine anomaly a real main tree DOES show — a script deadline that is checked only between polls can be held open by a blocking subprocess call, so cap `_gh`/`_sh` with a subprocess timeout (`subprocess.run(..., timeout=…)`) that a poll cannot exceed. Root never-publishes belongs to the producer lane, not this one.

**And the owed task-relative change may be an on-wire correction, not a code edit.** When a reviewer/dispatch asserts a conclusion of yours is FALSE and the guard keeps demanding "a required task-relative change", do not get defensive and do not fabricate a file edit to silence it — re-measure live, restate plainly ("NOT concluded / NOT green", with the current `status`+`conclusion`), give the exact bound math, and post the corrected record on the same issue/PR thread (verify by direct comment id). That reconciliation IS the mutation owed; a guard that cannot observe `gh` wire state is answered by wire truth, never by a manufactured edit.

When the claim is "the guard job is green" (or a planner trusts a local snapshot), do not
trust a run's `.conclusion` or someone else's `/tmp` copy — run the gates yourself against
the LIVE PR body. The scripts import a `scripts` package, so pull the whole package at
`main` or you hit `ModuleNotFoundError` (acceptance needs `check_pr_closing`, `issue_body`,
`proc`, `acceptance_writeback`; closing needs `check_pr_authors`, `base_ref`):

```sh
for s in check_pr_acceptance check_pr_closing check_pr_authors issue_body proc \
         acceptance_writeback base_ref; do
  gh api "repos/<o>/<r>/contents/scripts/$s.py?ref=main" --jq .content | base64 -d > scripts/$s.py
done
gh api repos/<o>/<r>/issues/<pr> --jq .body > /tmp/pr_live.md
PYTHONPATH=$PWD python3 scripts/check_pr_acceptance.py check --body-file /tmp/pr_live.md --repo <o>/<r>
# expect: OK — every closed issue's `## Acceptance criteria` is checked or named out of scope   rc=0
mb=$(git merge-base origin/main <head-sha>)
PYTHONPATH=$PWD python3 scripts/check_pr_closing.py check --body-file /tmp/pr_live.md \
    --head <branch> --base "$mb" --rev <head-sha> --cwd <checkout>
# expect: OK — an agent PR body carries an adjacent closing keyword ...   rc=0
```

Both `OK`/rc=0 = a real pass; either red = a genuine gate failure the rerun cannot clear —
diagnose and route it, do not rerun it green.

### False resolving-ref body trap (`check_pr_closing`)

A body bullet like "...`completed` success is tracked by #NNN" puts a resolved-state verb
within the `RESOLVING` regex's ~24-char window of an UNCLOSED issue id, so the gate reads it
as a resolving reference and reds. Reword to drop the state verb next to the id ("the green
run is tracked by #NNN") and re-verify resolving-refs are empty before rerunning.

## Superseded records and where the report goes

A dispatch that enumerates fields — *"Report: branch, PR number, run id"* — wants those
fields **on the issue/PR thread on-wire**, not only in a DM to the lane. A fire-and-forget
`message_agent` is invisible to the next reader; post the completion record on the issue the
fix implements (or the PR), then read it back by direct comment id (`gh api
repos/<o>/<r>/issues/comments/<id> --jq '{author:.user.login,issue:.issue_url,img:...}'`).

And when a LATER action supersedes an EARLIER measurement record on the wire, reconcile it:
a record that says "no PR opened" becomes a lie the moment you ship the PR. Post a short
follow-up on that same thread (naming the new PR/branch/head) so a reader of the old thread
is not misled — never leave a stale "nothing changed" record standing beside the real fix.
The two records must read consistently together.

## The body-content gate ladder (each fix surfaces the next one)

A PR that closes an issue runs a CHAIN of body-content gates inside the `guard` job. Fixing
one line does not make the guard green — it lets the job reach the NEXT gate, which reds on
different rules. Expect to iterate closing → agents-line → openspec-change → acceptance, and
fix-and-verify EACH one locally (rc=0) before re-running the guard, rather than pushing a
body edit and re-running blind each time. The gates, in the order they bite:

- **`check-pr-closing`** — the body must carry an ADJACENT closing keyword next to the issue
  id (literal `closes #NNN`). A bold `**Issue:** #NNN` line is NOT a resolving reference: the
  checker wants the keyword form spelled out. (See also the false-resolving-ref trap below.)
- **`check-pr-agents-line` (issue #792)** — the body's `AGENTS:` line must be the
  **`make bot-preflight` form**: `AGENTS: <sha> <bytes>b <lines>l`, where `<sha>` is a commit
  that is an ancestor of BOTH head and base, and `<bytes>`/`<lines>` are `AGENTS.md`'s size at
  that commit; plus a companion `BASE: <sha> (== origin/main at open)`. A bare
  `AGENTS: <author-name>` reds. Get the exact numbers by running `bot_preflight.py` on the
  host (the worktree has no `.git` for the container), and pick a sha that exists in both
  trees (`git merge-base` / a base commit).
- **`check-pr-openspec-change`** — a diff touching PRODUCT code (e.g. `scripts/engine_build_*.py`)
  must either add a file under `openspec/changes/<name>/` OR name an ACTIVE change in the body
  via a plain `OPENSPEC: <name>` line (the documented escape hatch). Read the active changes
  (`openspec/changes/*/`) to find the one this work extends; do not invent a name. `openspec-new`
  needs the openspec image; the `OPENSPEC:` body line avoids that.
- **`check-pr-acceptance` (#1644)** — the LAST gate, and verdict-gated: it passes only when
  every closed issue's `## Acceptance criteria` box is ticked, and `acceptance_writeback` ticks
  nothing without a REVIEWER verdict. This lane never self-ticks (#948/#1792) and must not
  declare met criteria `## Not covered` to dodge the red. The correct terminal state for a
  fresh implementing PR is: guard green except acceptance, PR ready-for-review, verdict routed
  to the reviewing lane. That is the designed hold, not a defect — do not rerun it green.

**Read back a PR comment by direct id, remembering `issue_url` lies for PRs:** a comment posted
on a PR returns `issue_url = .../issues/<n>` (NOT `.../pull/<n>`), so a readback test using
`contains("pull/")` reads `false` on a perfectly-correct PR comment. Check the numeric id
matches the PR and read `.issue_url` directly; do not assert on the `pull/` substring.

## Reading a red: log, not colour

- `gh api "repos/<owner>/llgenie/actions/runs?head_sha=$SHA"` needs the **full 40-char
  oid**. A 12-char prefix returns an empty list and reads as "no CI ran". Get it with
  `gh pr view <n> --json headRefOid --jq .headRefOid`.
- Identify the failing job and step, then quote the failure line:
  `gh api repos/<o>/llgenie/actions/runs/<id>/jobs --jq '.jobs[]|{name,conclusion,steps:[.steps[]|select(.conclusion=="failure")|.name]}'`
  then `gh run view <id> --log | grep -iE 'error|fail|violation'`.
- A cancelled run and a run whose jobs never start both roll up as failure or blank;
  the log is the only place that distinguishes them.

## Repairing the PR's own red

A red on this lane's own PR branch is repaired by a follow-up commit pushed to that
same branch — `make lint` green on the branch first, then push. It is not a new PR and
not a rebase. Only push when no run at that head is still in flight (`cancel-in-progress`
would make the push destructive); a head whose run has already concluded is safe.

## Order that works

1. Run the full changed-file newline loop.
2. Run the repo gates the diff touches: `check-workflows`, `check-wiring`,
   `check-dispatch-forms`, `check-docs`, `changes-index`, and the domain test file.
3. Regenerate anything a gate says is stale (`make dispatch-forms-report` spliced
   between its markers, `make changes-index`) and re-run the gate, not just the target.
4. Commit one atomic commit with `Issue:` / `Fix:` / `Benefit:` / `Technical:` /
   `AGENTS:`, then read back `git show --stat` before pushing.

## Gates that red for reasons unrelated to your logic

- **`check-pr-base` (issue #845): the branch's merge-base must EQUAL the live `origin/main`.**
  It is not "is-a-descendant-of" — a branch cut even one merge ago has a merge-base that is not
  the tip, and the gate rejects it with "foreign commits" (main's own commits fall inside your
  range and read as your claims). Main on this repo advances **several merges per hour**, and the
  CI step re-fetches `origin/main` fresh (`git fetch --no-tags --prune origin main`) so a stale
  local ref cannot hide it. Rebase onto the live tip (`git fetch upstream main` then `rebase --onto
  upstream/main <old-base>`) **immediately before the push**, and expect to repeat — a clean local
  run does not predict the CI verdict, because main moved again in between. Resolve repeated
  conflicts on the regenerated docs files by taking main's version and re-applying the one-line edit,
  then regenerate.
- **`check-docs` change-note diffs `base...HEAD` — a STAGED note does not satisfy it.** The gate
  diffs the committed range, so a `docs/changes.d/` note that is only `git add`-ed still reads "this
  branch changes <file> but adds no agent-wiki note". Add the note and **amend the commit** to include
  it, then re-run `check-docs` against the amended head (base = the live `upstream/main`), not against
  the working tree.
- **A new secret env name must be added to `scripts/check_secret_output.py` `SECRET_VARS`.**
  `tests/test_secret_output.py` asserts every secret-carrying env var the repo uses is in that
  allowlist, so introducing an alias (a token re-export, a new credential var) reds
  `test_the_secret_list_matches_the_repo_secrets` — and only that one — until the name is added. Do
  not weaken the assertion; add the name to the tuple in the same atomic commit.
- **`linux/unit` is a long suite; do not call green before it concludes at the head.** The other
  13 checks can all be SUCCESS with `unit` still `in_progress`. `mergeable_state=blocked` while a
  check is in progress is normal, not a defect. Poll the head's `check-runs` for the unit conclusion
  (a background waiter that notifies on exit beats a foreground poll that times out) and only then
  report the verdict with its run id.
