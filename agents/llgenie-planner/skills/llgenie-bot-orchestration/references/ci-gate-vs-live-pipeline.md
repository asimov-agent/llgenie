# Verifying whether a test class is in the PR gate or a separate pipeline

Owner question shape: "are the live/network tests still inside `<gate pipeline>`, or refactored
out to a separate pipeline?" — usually asked *because* a PR job just timed out. Answer from the
**tree at the latest main sha**, never from memory and never from the linked run alone.

## Procedure

1. **Pin the sha and read workflows at THAT sha.** `git rev-parse --short origin/main` (or the PR
   head), then fetch each workflow from `raw.githubusercontent.com/<owner>/<repo>/<sha>/.github/workflows/<wf>.yml`.
   The working tree can be stale; the pinned sha is the fact.
2. **Read trigger surfaces to classify the pipeline.** `on: push: branches: [main]` + `schedule`
   + `workflow_dispatch` with **no** `pull_request:` = a separate live pipeline. A job inside the
   PR-triggered matrix (`ci.yml` on `pull_request`) = the gate.
3. **Read the exclusion list** (`tests/fixtures/unit-suite.json` in llgenie): network/live-marked
   tests excluded from the hermetic gate each carry a reason naming the pipeline that runs them
   instead (`test-unit-network`, `test-hub-live`, `test-strata-live`, `test-engine-bump-live`,
   `test-engine-install`, …). Those routing reasons ARE the proof of separation.
4. **Prove the separate pipeline is LIVE, not just configured.**
   `gh run list --workflow <wf>.yml --limit 5 --json status,conclusion,headBranch,event` — recent
   success on the right event (merge-to-main push) is the evidence; a configured-but-never-run
   workflow proves nothing.
5. **Reconcile against the linked run.** Identify PR + head + the exact job id, then read
   `started_at -> completed_at` and conclusion from `gh api .../actions/jobs/<id>`.

## Rule: a ~3600s cancelled gate job is a ceiling casualty, not "live tests leaked into the gate"

When the linked symptom is the unit row `cancelled` at ~1h, check whether every peer job on that
run succeeded (guard, lint, scanners, agents-read, health). If they did and only the unit job died
at ~60m (`duration ≈ 3600s`), the cause is the gate's own duration hitting its budget — not live
network tests inside the gate. Run steps 2–3 first so "the tests are refactored out" is measured,
not asserted; the cancel and the separation can both be true at once.

## Rule: a pin/test that scans a selection cannot flag a file that is not in it — check the roster

Before saying "this file violates <repo-wide pin>", confirm the file is in the set the pin
actually iterates. Most repo-wide pins in llgenie scan `ut.select(REPO)` — every `tests/test_*.py`
**minus** the exclusion roster in `tests/fixtures/unit-suite.json` — so a file routed to a live
pipeline (`test-strata-live`, `test-install-trend`, `test-unit-network`, …) is never read by the pin
and cannot be an offender, however many unmarked Hub-reaching calls it contains. Measuring "zero
network marks in file X, therefore the pin has a hole" is invalid until you have read X's exclusion
status. Settle it in one call before dispatching anyone:

```bash
python3 - <<'PY'
import json
r = json.load(open('tests/fixtures/unit-suite.json'))
for f in ['tests/test_strata_download.py', 'tests/test_install_trend.py']:
    ex = r.get('excluded', {}).get(f)
    print(('EXCLUDED -> ' + ex['target']) if ex else 'in-unit (pin scans it)')
PY
```

Consequence for dispatch: a premise that rests on a file's absence from a marker/pin is only real
if the file is in the pin's selection. Retracting a wrong premise after it produced a dispatch costs
two corrected lanes; confirming the roster first costs one command. Same discipline as verifying a
lane's claim — a report is a claim, and so is your own "the gate is broken" diagnosis.

## Rule: a failed run stamped with main's head sha is not proof main is red

A red run whose `head_sha` equals the current `origin/main` tip does **not** mean the tree's gates
went red — a `workflow_run`-triggered workflow (auto-merge, registry-sync, run-failure-reactor)
checks out the base repo at that sha but executes an unrelated job, and its own guards can fail. The
auto-merge lane did exactly this: a stale `workflow_run` event delivered `PR=""` plus an orphaned
branch sha (a just-closed PR's head), and `make auto-merge PR=""` exited with a Usage error (exit 2)
while two other auto-merge runs at the same head concluded `success`. Nothing about the commit was red.

So before filing a `main is red` incident:

1. **Name the failing JOB and read its log**, not just `run list`'s `conclusion`. `gh run view
   <id> --log-failed | head` — a Usage/argument error, an empty env var (`PR:` blank), or an
   invocation referencing a sha that is not main's tip are all *the workflow's own misfire*.
2. **Split the run set by workflow name.** `gh api ".../actions/runs?head_sha=<tip>"` and filter
   out the meta workflows (`auto-merge`, etc.); the actual gate workflows (`ci`, `unit`, `guard`,
   `scope`) are the ones whose red would mean the tree. If none of those ran red at the tip, main
   is not red.
3. **Confirm the head sha in a failing run is really the tip**, and whether it belongs to an
   orphan/closed PR. A `HEAD_SHA` on a `workflow_run` job is the triggering run's head, not
   necessarily `main` — quote the sha you measured, not the one the job inherited.

A self-refusing guard that stopped a wrong merge is the guard working, not a defect — report it as
an auto-merge lane misfire to route, never as a tree regression that blocks the board.

## Rule: a lane's local `make <target>` rc0 is not the CI gate — read the run at the head

A lane reporting "check-docs exit 0, census ok, lint ok" has run *some local targets*; the CI job
can still be red at the same head because it runs a different set. Real instance: a docs PR head
`de8559ed` was reported green on local `check-docs`, while ci-scope run was FAILURE — `ci-lint`
(Makefile:1652 `make lint`) runs `scripts/lint_linefeeds.py`, which fails with "markdown headings
not preceded by a blank line: agents/<lane>/references/<file>.md: lines N" (exit 2). The local
targets the lane listed never included the linefeed gate.

So: before routing any PR to review, quote the **CI run conclusion at the head**
(`gh api .../actions/runs/<id>` → `status`/`conclusion`) and the **failing job+step**
(`gh api .../runs/<id>/jobs` → the step whose `conclusion` is failure), then pull the log with
`gh api --allow-escape-sequences .../actions/jobs/<id>/logs | grep -ai` (plain `gh api` on logs
aborts with "response contains terminal escape sequences" and returns ~99 bytes). Route a red
head back to the PR's own author lane as a one-line fix — never to review, and never re-open a
second vehicle for it.

## Rule: a merged PR can leave a repo-wide gate red on main — a PR's red step may predate its branch

A PR whose gate fails is not automatically the PR's own diff. When the failing step is a **repo-wide**
check (wiring / roster / lint / census), test whether the SAME step fails on `main` at the merge tip
before the PR branched — a merged PR can land a file that violates the gate for every future PR. Real
instance: a fold merged a new `scripts/*.py` into the tree wired to nothing (no make target, no
workflow, no importer), so `make check-wiring` reds on main and every subsequent PR's `scope` job
fails on that exact step regardless of its own content.

```bash
# the failing job+step, structurally
gh api repos/<o>/<r>/actions/runs/<red-run>/jobs \
  --jq '.jobs[]|select(.conclusion=="failure")|.name+" :: "+([.steps[]|select(.conclusion=="failure")|.name]|join(","))'
# does that step's cause predate the branch? read the gating rule on main itself
git fetch origin main
git show origin/main:Makefile | grep -nE '<the-gate-target-or-marker>'
```

When the step fails on main for a reason the PR did not introduce, the PR's own diff is not the
defect: file the merged-PR regression as its own issue (route to the lane that merged the offending
file — it owns the file), and tell the PR owner its red is a **pre-existing tree red, not its content**
— do NOT ask it to edit unrelated files to clear a gate it does not own, and do NOT let two PRs each
try to "fix" the shared red in their own branch (that manufactures two conflicting vehicles for one
defect). One vehicle on the owning lane, mirrored from `agent_profile_sync.py`/`check_agent_profiles.py`
style, never by deleting the gate.

**A CLOSED issue is not the owner of the red — it is usually the guard that caught it.** When a lane
attributes a gate red to an issue number, read that issue's `state` before repeating it: in llgenie a
CLOSED issue is commonly the *guard* whose shipped test now flags the violation (a report-hygiene/
wiring/census rule), not an open defect owner. `gh issue view <n> --json state,closedAt` — if CLOSED,
the residual is a NEW issue to file against the offending file's owning lane, never a re-point of the
closed one. When the reddener is a peer lane's tool/script, route the fix to THAT lane and tell the
blocked PR owner its red is pre-existing, not its content — the exact lane-boundary rule above, now
with the closed-issue trap that makes it look already-tracked when it is not.

## Rule: a PR can MERGE while its deciding leg is `in_progress` or even `failure`

An owner merge does not prove the deciding gate was green. Verify the deciding leg's conclusion at
the **merge head**, never "green locally" nor "checks passed" from a report:

```bash
gh pr view <n> -R <o>/<r> --json state,mergedAt,mergeCommit,headRefOid \
  --jq '{state,mergedAt,mc:.mergeCommit.oid[0:8],head:.headRefOid[0:8]}'
gh api "repos/<o>/<r>/actions/runs?head_sha=<merge-head>" \
  --jq '.workflow_runs[]|select(.name=="CI")|{id:.id,status:.status,conclusion:.conclusion}'
gh api repos/<o>/<r>/actions/runs/<deciding-run>/jobs \
  --jq '.jobs[]|select(.name|test("unit"))|"\(.name) \(.status)/\(.conclusion)"'
```

If the deciding leg at the merge head is `in_progress`/`conclusion:null` or `failure`, the merge went
through a gate that never concluded green — record it as measured fact ("merged `<sha>` at `<time>`
with `<leg>` `<status>`, never completed green"), and never repeat a lane's "the leg was green at the
merge." The owner's merge latitude is the owner's call (#1088); what the planner must not do is
**certify** a merge as gate-green when the deciding leg never concluded — that false certification is
worse than no claim, because the owner reads it as verified.

## Rule: answer both halves of the owner's question separately

"Are the live tests refactored out?" and "why did it time out?" are two facts. Report them as two:
separation verified (workflow trigger + exclusion routing + a live successful run on the separate
pipeline) AND timeout attributed to gate duration / the shared ceiling with the job's timestamps.
Collapsing them into one "yes it's fixed" hides whichever half is still broken.

## Quantifying a gate's live-Hub cost against documented rate limits

When the symptom is 429s or stalling Hub calls in a hermetic gate, don't stop at "it's live in
the gate" — measure whether the call volume crosses Hugging Face's documented limits, so the
issue carries a number, not a vibe. HF enforces **three buckets over 5-minute fixed windows**
(anonymous / free-user per window): **API 500 / 1,000**, **Resolvers 3,000 / 5,000**, **Pages
100 / 200**. Which bucket a call hits decides everything:

- `huggingface.co/api/models/...` — including `/api/models/<repo>/tree/...?recursive=true` and
  `/api/models?search=...&filter=...` — is the **API bucket** (the stingiest one).
- `huggingface.co/<repo>/resolve/...` is the **Resolvers bucket** (the roomy one).
- a plain HTML page GET is the **Pages bucket**.

So a run that only lists repo trees and runs `?search=` queries is pure API-bucket pressure and
cannot lean on the resolver headroom, even though the resolver limit is 3-6x larger.

**Counting procedure (from the tree at the pinned sha, never from memory):**

1. Read `main()` of the generator/checker. **`--check` is not automatically a replay.** In llgenie
   `scripts/gen_trending_quant_catalog.py`, `--check` still rebuilds `_model_catalog()` for every
   model from the LIVE hub and only skips the post-build link-validation block — it never loads the
   committed fixture. Confirm what `--check` short-circuits before assuming it is hermetic.
2. Enumerate the calls one run makes: dedupe README/link sets (a 600-link README often collapses to
   tens of unique `/api/models` calls); count distinct repos in the committed artifact (each repo = a
   tree call) plus one search call per model.
3. Compare per-run volume to the **per-window** limit, then state the concurrency multiplier. A single
   run at ~450 API calls is *under* a solo free-user 1,000 but *over* the anonymous 500, and any second
   job sharing a GitHub-hosted runner's egress IP pushes the shared window over.

**Rule: escalating 429 waits are aggregate co-residency, not one run crossing the line.** The
retry policy (`hf_auth.hub_open` waiting out `RateLimit ...t=`) is correct — it never reds, it waits
its window. When stall times climb across jobs (e.g. 31s then ~290s), the cause is many jobs on
shared runner IPs summing into one 5-minute window, not a single caller exceeding its own budget.
The defect is the caller's seat (live call inside the hermetic gate), not the retry logic; the fix
is vendored-replay / a separate live pipeline, never tightening or removing the wait.

## Filing the resulting issue from latest main

- Pin the body to the current `main` sha and say so in the body.
- Cite exact run id, job id, and `started_at -> completed_at` duration; quote peer jobs' success.
- Cross-link existing ceiling / precedent issues instead of declaring a new phenomenon.
- Put the reversal in **Out of scope** explicitly (e.g. "do not move live-network tests back into
  the gate") so a later lane cannot satisfy the issue by reverting the separation.
