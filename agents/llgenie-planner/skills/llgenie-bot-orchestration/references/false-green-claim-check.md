# Checking a "fully green" claim (rollup counts, then the named error)

A lane's "fully green at head `<sha>`" is a claim. Settle it in three steps, in this order.

## A degraded lane channel produces phantom conclusions — never relay one you did not read

A lane whose own terminal/read channel is degraded reports `rc=0` with empty output, and then fills the gap
with a conclusion it never measured: "the run concluded green", "the gate flipped", "green-pending". This is
not lying — the command exited 0 and printed nothing, so the lane infers success. Treat any lane message that
admits "my read channel is degraded" / "could not quote the value" as **zero evidence** about the thing it
claims: re-read it yourself (file-backed probe: write the `status`/`conclusion`/`run_attempt` to a file, then
`cat` it) before repeating it. A run is green only when the API returns `status=completed` AND
`conclusion=success` AND every leg is `success`; `in_progress`/`queued`/`None` is a hang, not a win, and a
hang you relay as "concluded" is the exact phantom this rule forbids. Try a second corpus when your own
channel looks empty — a spillover file or a direct API call usually reads fine when the display path does not.

## A `## Not covered` section that cites a FAILED run is dishonesty, not coverage

A test-only PR that does not close its issue may carry a `## Not covered` section pointing at a *live* run as
the evidence that the uncovered ACs are nonetheless proven. Verify that cited run before accepting it:
`gh api repos/<o>/<r>/actions/runs/<id> --jq '{status,conclusion}'`. A run that is `completed/failure` (e.g.
an OOM `Killed`, exit 143, in the cell it claims to prove) is not evidence — the ACs are **unproven**, and the
section must say so and name the tracked issue that will produce a real witness. "Not covered → here is a dead
run" is the #745-class red the gate exists to catch; correct the body, do not route on it.

## 1. Group the check-runs at that exact sha

```bash
gh api --paginate "repos/<owner>/<repo>/commits/<sha>/check-runs?per_page=60" \
  --jq '(.check_runs // .)
        | group_by(if .status=="in_progress" then "IP" else (.conclusion//"none") end)
        | map("\(.[0].conclusion//.[0].status//"x"):\(length)") | .[]'
```

Any non-zero `failure` bucket falsifies "green" regardless of how many `success` cells sit beside it. `skipped` is neither green nor red; a claim of green with `skipped>0` is a claim about a partial matrix, so check whether the skipped cells are ones that used to run.

Also confirm the sha you measured is the LIVE head (`gh api repos/<owner>/<repo>/pulls/<n> --jq .head.sha`) — a lane that pushed again makes the rollup you just read historical.

**A green named job is NOT a green run — quote `completed`+`success` on `gh run view` as the only full-matrix proof.** A workflow's aggregate `guard` (or any single summary job) can conclude SUCCESS while a matrix tail (`linux / unit`, a build cell) is still `in_progress`; reporting "all gates green" off the guard job is a premature-green you then have to correct. Read the run's own verdict — `gh run view <id> --json status,conclusion` — and only call it green when that returns `"status":"completed","conclusion":"success"` AND the jobs list shows every leg `conclusion:success` (a `completed` run with a skipped leg is partial). Quote the run id with the pair; "guard success" / "step 10 success" are per-job states, not the run's.

**A green `review-verdict` run is not a reviewer verdict — the workflow fires on any head change and records nothing.** `review-verdict` runs on the PR's push/review event, maps the review state to a verdict, and when no review exists it logs `review state '<state>' is not a verdict (approved/changes_requested) - nothing to record` with `SKIP=true`. The run then concludes `success` at a head where nothing was recorded, and anyone scanning runs by conclusion reads that as "the reviewer validated". Check the artifact, not the run: `gh api repos/<o>/<r>/pulls/<n>/reviews --jq 'length'` plus `gh pr view <n> --json reviewDecision` — `REVIEW_REQUIRED` with an empty reviews list means the verdict dispatch is still outstanding however green the workflow row is. Never tell a lane or the owner that a PR "got its verdict" on the strength of that run, and never tick an acceptance box because `review-verdict` succeeded.

## 2. Read each failing job's log and name the error line

```bash
gh api --allow-escape-sequences repos/<owner>/<repo>/actions/jobs/<job_id>/logs \
  > /tmp/j.log
tr -d '\r' < /tmp/j.log | sed -E 's/\x1b\[[0-9;]*[a-zA-Z]//g' \
  | grep -iE '##\[error\]|Error [0-9]|Exit code|exit code [1-9]' | tail -10
```

The job NAME is not the diagnosis. Grep for the check's own message around the failing step, not for branch noise — `* [new branch]` lines from a fetch fill the whole log and match almost any broad pattern. Confirm the job belongs to the head you are claiming about (`gh api repos/<owner>/<repo>/actions/runs/<run_id> --jq .head_sha`; a job-id route 404s, the run route does not).

**The named make target is the cause, and it is one line.** A gate job that fails on a Makefile target prints the
whole target name and line number; extract exactly that instead of reading the log top-to-bottom:

```bash
gh run view --repo <o>/<r> --job <job_id> --log 2>/dev/null \
  | grep -oE 'make: \*\*\* \[Makefile:[0-9]+: [a-z-]+\]' | tail -1
# -> make: *** [Makefile:1126: check-pr-agents-line]
```

**Several red PRs do not share one cause just because one summary says so.** A pass that reports "one cause,
N PRs" is a hypothesis; pull each PR's failing target and compare. Measured: of five reds, two failed
`check-pr-agents-line` (a body stamp — bot-fixable metadata), one failed `check-pr-acceptance` (verdict-gated
write-back), and the `check-docs` `scope` reds were a missing change-note, while a sixth PR was `BLOCKED` with
**no failing check at all** (review-only). Routing all of them at the "shared" cause would have sent four lanes
to fix code that was never broken.

## 3. Same rollup, two different causes — distinguish before relaying

One head's rollup can carry both:

- **A real red** that is this PR's own (a lint/scope/unit cell). Owed: a fix on the branch.
- **A pre-push echo** — a run that started before the lane's last force-push, which read the older head body or tree. If the failing run's start time precedes the push, and the live body/tree already differ from what the log complains about, the red is history; the lane owes a fresh run, not a code change.

Compare the failing run's `created_at` with the push time and diff the live body against the log's complaint before you call anything a defect.

## The most common guard red on a doc/SOUL PR: a stale body cite

The `check-pr-agents-line` target runs `check_pr_hygiene.py agents-line` against the LIVE PR body. It reds with

```
[check-pr-hygiene] PR body: the `AGENTS:` line cites <sha>, which is not a commit in this clone
```

when the body's `AGENTS:`/`BASE:` lines still point at the pre-rebase head, or at a base sha the clone no longer has / that no longer matches `origin/main`. A lane that rebased its branch and refreshed the body afterwards wins the race only sometimes — the run that started at push time reads the old body.

Check the body's cite and the PR's base against current main:

```bash
gh api repos/<owner>/<repo>/pulls/<n> --jq '{base:.base.sha, body:.body}' | grep -E 'AGENTS|BASE|base'
git ls-remote origin refs/heads/main
```

A `base.sha` N merges behind `origin/main` with a clean diff reds the base gates regardless of how good the code is. The remedy is **body-refresh (re-cite current main) + rebase onto current main**, not a code edit. Say so explicitly when correcting the lane, and name the sha you measured at.

## A lane asking you to "confirm it as ready" is a ratification request, not evidence

A lane that reports "PR opened, pushed from clean upstream main, tree verified clean, 30/30 tests pass, green-pending on the merge queue — please confirm the PR reads ready on your board" is asking you to ratify its own artifact, not handing you a measured gate state. Its sub-claims can ALL be true (pushed tree clean, suite green in the image, no scratch leaked) and the PR still be red: a clean tree is a claim about file content, and a passing test run is a claim about one suite — neither is `gh pr checks`. The merge queue reads the **gates at the head**, and `mergeStateStatus: DIRTY/BLOCKED` plus a non-zero `failure` bucket means it cannot land however clean the tree is.

So when a "confirm as ready" arrives: run `gh pr checks <n>` and the rollup (§1) yourself, and **record on your board only what those return**. If red, do not write "recorded #<n> as ready" — that would be the stale-read failure the gates exist to catch. Record the PR number, the measured red(s), and route the reconcile to the vehicle's author.

- **A lane anchoring by "branch pushed + tree clean" is anchoring on the wrong object.** The pushed tree being clean proves what was committed; it does not prove the commit message, the PR body, or the head's CI satisfy the gates. Read the PR object (`gh pr checks`, `--json body`) — not the branch.
- **"Green-pending on the merge queue" + `mergeStateStatus: BLOCKED` is a contradiction; the API wins.** BLOCKED with checks green = `REVIEW_REQUIRED`; BLOCKED with a failing check = a real red. Distinguish by the rollup, then route accordingly.

## A new head sha is not a change: prove the re-push by tree identity

When a lane answers a reconcile with "re-pushed, now green at `<new sha>`", the sha having moved proves
only that a ref moved. It is common for the "re-push" to be a re-commit of the **identical tree** (an amend
that touched nothing, a rebase with no tree change, or a force-push of the same object) — the body, the commit
subject and every gate are then unchanged, yet "green" gets re-asserted against a fresh-looking head. Prove the
change before accepting the claim:

```bash
git rev-parse <new>^{tree} <old>^{tree}          # equal trees = no content change at all
git diff --stat <old>..<new>                     # empty output = nothing applied
git log -1 --format='%an %ad %s' <new>          # same author+timestamp+subject = not a new commit
```

If the tree is equal, the lane did not apply your reconcile, whatever it says — re-state the exact remedy
(the body/section edits, the `AGENTS:`/`BASE:` lines, the commit verb) rather than inventing a new one, and
say plainly that the head is byte-identical to the prior one. Also re-read the PR **body** at the new head:
head-move checks (subject verb, body sections, cites) are evaluated against body+commit, so an unchanged body
means those reds are guaranteed to persist no matter how many times the branch is pushed.

## A claimed push that never moved the head — three cheap reads falsify it

The mirror of the identical-tree re-push: a bot's done-comment says "repaired the failure… **Pushed as one
commit**, so CI re-runs on the new head" and `head.sha` is *exactly what it was before*. A push that lands
always moves a ref, so an unchanged head across the claim's timestamp means the push failed (or was
force-pushed back) and nothing new was graded — even though the comment reads as a fix.

```bash
gh api repos/<o>/<r>/pulls/<n> --jq '{head:.head.sha,updated:.updated_at}'
gh api "repos/<o>/<r>/actions/runs?head_sha=<head>&per_page=3" \
  --jq '.workflow_runs[]|"\(.id) \(.event) \(.created_at)"'
gh api "repos/<o>/<r>/commits?sha=<head>&per_page=1" --jq '.[0]|"\(.sha[0:10]) \(.commit.author.date)"'
```

Falsify with three facts, quoted together: (1) the head is byte-identical before and after the claim; (2) the
newest run at that head **predates** the comment, so "CI re-runs on the new head" is false and no fresh verdict
exists; (3) the newest commit on the branch predates the claim. Record "claim unverified — no push, no run" on
the thread and do not let it stand as the reason the red cleared. A CI bot's "GREEN again" line is a claim like
any lane's; a repair comment beside a still-red head is the most common way a red run gets relayed as a fix.

## A reading that was already clean is NOT evidence the work landed

The cheapest false green is a metric that is **true before you act and after you act**. Reporting it as a
delivered outcome turns a no-op into a success and is invisible to everyone who reads only the after-value.
Concretely: a rule was broadcast to twelve lanes; the audit read `grep -c '/home/<user>' <each SOUL> = 0` for
every lane and that was reported as "the rule is delivered". But the SOULs contained **neither the literal nor
its replacement** — `grep -c '\$HOME'` was also 0. Nothing had ever been there, so 0 was the null reading, no
lane had edited anything (the mtimes predated the dispatch), and no lane ever replied. The metric was satisfied
by the starting state.

Two cheap guards, always run together:

```bash
# 1. take the BEFORE value — if you did not record it, you have no delta and no claim
# 2. prove the work is PRESENT, not that a defect is ABSENT
#    absence-of-X is satisfied by "never had X"; presence-of-Y cannot be
```

So when a change is "apply rule R everywhere", assert the **presence** of R (`grep -c '\$HOME'` > 0 in the
files that must carry it) and the **absence of the old form**, plus a file mtime newer than the dispatch. A
dispatch that produced no reply and no touched file is `unconfirmed`, not `delivered` — an exit code of 1 from a
fan-out whose receipts carry delivery ids but no outcome means **exactly that**, and it must not be backfilled
with a count that happened to read zero.

## A whole-directory count inflates: separate instructions from state files

Counting occurrences over a profile directory reports the curator ledger and retired skills as if they were
instructions — measured: one lane's `grep -ro` total was 4,817, of which **2,253 sat in `.curator_ledger.jsonl`**
and most of the rest in `.archive/`. The honest figure was single digits per file. Scope the count before you
quote it, or the number teaches the next reader to ignore your measurements:

```bash
find <profile>/skills -name '*.md' -not -path '*/.archive/*' -exec grep -o '<pat>' {} + | wc -l
```

## The same patch must land at the shared source, not just each copy

Profile skills are **real files, not symlinks** to the global source: the same shared skill exists once at the
source tree and again inside every profile. A shared defect therefore appears in all N lanes at once, and a
per-lane fix is N identical edits while a per-lane `grep` can never reveal the shared cause — six shared skills
explained 70 of 70 across twelve lanes, and four files were the entire genuine lane-specific remainder.
Sweep source **and** every copy together, and say in the report which one the fix landed at.

## When you correct the lane

Post the correction on the PR/issue with (a) the grouped rollup counts, (b) each failing job's named error line and completion time, (c) the live head/base vs current main, and (d) the concrete remedy. Then DM the lane the same facts. Never accept "fully green" as a state; it is a claim that got measured.
