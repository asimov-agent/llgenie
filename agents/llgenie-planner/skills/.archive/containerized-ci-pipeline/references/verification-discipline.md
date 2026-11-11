# Verifying a bot/pipeline fix — green CI proves nothing

## A check that SKIPS is a defect even when every run is green

A check gated on a credential the run rarely has is SKIPPED silently: e.g. a secret
check that calls `gh secret list` needs repo ADMIN, the default/`github.token` gets
403 on every run, so the check prints a skip/WARNING and never executes — while all
runs stay green. A green pipeline that never runs a check is unverified, not
validated.

- Reproduce it by actually dispatching the bot and reading the run LOG for the
  skip line: `gh workflow run <wf> [-f dry=true]`, then `gh run view <id> --log |
  grep -iE 'secret|skip|warn|info'`. The 403 appears there, not in job status.
- Fix it by driving the check from an IN-REPO declared contract (the real
  secret/env set committed to the repo as the referenced names) instead of the
  admin-gated live read — so the check always runs, whatever token the run has.
  The live admin read can stay as an optional stricter path behind the contract.
- Verify the fix in TWO steps: (1) merge the fix; (2) re-dispatch the bot and
  confirm the NEW log now shows the check RAN against the contract (the same 403
  on the live read is still refused, but the no-longer-skipped message is the
  win). Merger green and fix-work-in-production are different facts.

## A fix can make a refusal message LIE — name the cost, never carry a fixed consequence

When a merged fix changes WHAT a refusal costs (e.g. a check that used to be skipped by a refused
read now runs off an in-repo contract), the message-emitting helper can still carry the OLD
consequence — appending ">>> that check is SKIPPED this run<<<" to an arbitrary refusal. Re-dispatching
then plays green while the log contradicts itself one line apart: a WARNING asserting a skip the
fix removed, above an INFO saying the check ran. A green verified log can still be a WRONG
message — the same causal-lie class as a check that blamed the wrong resource.

- After re-dispatching a merged fix, read the refusal-cost lines for TRUTH, not just that the
expected message appears: does the "skipped" claim still match what the fix made true?
- Fix the class, not the line: a helper that appends a fixed consequence to an arbitrary refusal
takes the consequence IN (`skips: str | None`) — a genuinely skipped check still names it, and a
no-cost refusal states that it costs nothing.
- Test BOTH directions so a later "quiet it down" edit cannot remove the signal: a refused read
whose refusal now skips nothing must NOT claim a check was skipped, and one that still skips a
check must still name that consequence (the guard against silencing the signal everywhere).

## Verify the fix holds after merge — re-dispatch, one bot at a time

Squash-merge green is not the same as fixed. After the fix PR auto-merges, re-run
the bot through its own `workflow_dispatch` (dry/read-only form where one exists)
and read the log for the CONCRETE behavior change. Do exactly one bot per pass;
verify each merged bot's fix live before starting the next.

## A pre-flight probe must not red on a flake — the distinction has to be VISIBLE

A scheduled pre-flight probe (reachability/health check) that counts EVERY miss as a failure and
outs on the first one is self-defeating: one slow query flags the run exactly like a dead source,
so whoever reads the alert stops trusting it — they either chase a phantom or ignore the one red
signal that would actually catch an outage. It is worse when a downstream stage (the real
data-aggregate job) runs and SUCCEEDS while the pre-flight is red: the run is a failure for work
that completed, and the red is indistinguishable from the source being down or the probe broken.

- The probe is pre-flight REACHABILITY, not completeness — it samples, so a MINORITY miss must
  not block. Decide per leg: a MAJORITY missing blocks (an unreachable source misses all of them,
  so it still fails loudly); a minority does not, and an exact half is not a majority.
- Carry the distinction in the OUTPUT, not by erasing the miss — a red run is the ONLY alarm a
dead source gets, so the signal must stay readably alive: a sampled leg names the ratio and
 "sampled slower, the rest answered, so the source is reachable" and exits 0; a genuinely dead
leg says a MAJORITY missed and is "not a flake". A blanket "all backends OK" line must NOT print
for a leg that sampled slow — that line would be false.
- Keep the whole per-leg verdict under ONE decision function (`leg_verdict(total, missed)`)
behind a seam (`main(probe_fn=None)`) so the REAL `main()` — verdict, summary lines and exit
code — runs offline in the test; the probe stays the single implementation, no second copy.
- Prove the decision real in BOTH directions offline, not against the live network: one slow of N
→ pass with the visible ratio note and no "all OK" claim; ALL slow → non-zero naming "not a
flake". Lock the seam's existence with a named RED test (run the suite against
`git show origin/master:<probe>`), so the reported summary line is tested production code.

## Reading a bot's `make test` background log

`grep -c FAIL` over a whole test log massively overcounts: negative-case tests
expect `FAIL:` lines. Trust the trailing `exit=<N>` and the `FAILED [1-9]` pytest
failure marker, never a raw `grep -c FAIL`.

## The suite is SCRIPT-based, not pytest — the runner is the honest gate

In this repo the `tests/test_*.py` modules are NOT pytest tests: each is a script
whose `check()` prints `ok/FAIL` lines and whose `main()` returns a status, and
`make test` runs them through ONE runner (`scripts/run_tests.sh`) that stops at the
first red. Two consequences:

- **Do NOT "modernize" the suite to pytest.** Running these script-modules under
  pytest makes the suite green regardless of `_FAIL` — pytest collects them as
  passing modules and never sees the script's own exit status, so a broken check
  sails through. The one-runner is the honest gate; a pytest migration would
  silently disable every guard. (The test image deliberately has no pytest.)
- **The runner's own output line is the proof it ran.** `make test` prints
  `[test] N module(s) passed` — N is the runner's DISCOVERY count, not a
  hand-written list. To verify a PR's CI actually executed the suite, pull the
  run log and grep for that line, then cross-check N against the real file count:
  `git ls-tree --name-only origin/master:tests | grep -c '^test_.*\.py$'`. Equal
  counts = every module ran; a count that can't match the tree means the runner
  was bypassed or a file is unlisted.

## Rule-file row obligations when the rule file is approval-gated

A repo rule may demand every change grow a row in a protected table (e.g. a
regression-guards §8 row) whose writes are approval-gated and can time out. Do not
tick the task falsely and do not bypass the gate. Land the change with that
specific obligation deferred as a filed finding on the change, and file the owed
row as its own dedicated issue — a backlog of owed rows is visible debt, a fake
tick is a lie.
