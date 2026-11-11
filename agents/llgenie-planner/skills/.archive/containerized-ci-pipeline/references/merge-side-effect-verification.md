# Verifying a side effect after the fact (post-merge closure check)

## Predict vs prove

A static pre-merge check that PARSES an artifact can only PREDICT an outcome; it cannot prove it. A body parser that applies the platform's own reference-binding semantics tells you what *should* close, not what did. Prove a claimed side effect by READING THE TARGET BACK after the triggering action (the merged PR's `closingIssuesReferences`), not by re-running the predictor. The two checks are complements: the predictor refuses a mismatch before the merge, the verifier fails loudly when the merge left the claim false.

Pattern: read the merged PR's `closingIssuesReferences`; when a reference omits its state, fetch the issue's state individually; fail 1 naming the issue, its state and the rule, on the last retry.

## A remote side effect trails the call

The platform's own operation (GitHub closing an issue) lands a moment AFTER the triggering call (the merge) returns. So the verifier RETRIES a handful of times with a short sleep before declaring a still-open issue a failure. Bound it: attempts and delay must be env-injectable so the test suite can set attempts=1, delay=0 and never sleep for real. Deterministic time in the test, never the wall clock.

## Loud read failure, never a silent pass

If the read back itself fails (the CLI errors, a non-JSON body), that is NOT a pass — an unreadable state must exit non-zero and quote the tool's own message. 'GitHub masked it / it was only my key' is never a pass either. The absence of a claim is different: a PR that closes NOTHING is legal and is not a failure (the predictor refuses a *mismatch*, not an absence).

## The #281 class: `make` needs a checkout, and a merge job has none

Wiring a NEW `make` target into a job that previously never checked the repository out (e.g. an `auto-merge` job that only ran `gh pr merge`) dies before it runs with `make: *** No targets specified and no makefile found`. Fix by adding `actions/checkout` as the FIRST step of that job; the make target then has the Makefile it needs. A guard that scans every workflow for make-calls-before-checkout catches this class — and it is the SAME class you must watch for whenever you add a target to a non-checkout job.

## The full checklist when adding this kind of guard

1. A `make` target that calls the script (host `_`-recipe — the CLI lives on the runner, not in the image) plus a workflow caller; never call `scripts/*.py` from a workflow step (rule 6m).
2. The new target gets an ARCHITECTURE.md row AND the job step is described there (rule 6h).
3. The test runs the REAL script against a stub CLI on PATH (an EXTERNAL system stand-in) — the script's own request building and decision logic still execute; never mock the product symbol.
4. Prove RED on the pre-change tree (`git stash` the wiring/script, run, confirm failures) and GREEN after (rule 6c: a regression fixed without a test that fails on the old code is not fixed).
5. The workflow job gains its own `actions/checkout` if it had none (see above).
