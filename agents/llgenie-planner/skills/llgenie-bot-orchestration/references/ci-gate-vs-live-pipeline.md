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
