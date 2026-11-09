# Triaging a llgenie red, and the pre-push gates that stop one

## Read the LOG, not the badge

A status rollup is a conclusion; the fix is in the job log. Resolve the run from
the branch + workflow filename, then the failing job, then the log:

```bash
gh run list -R asimov-agent/llgenie --branch <branch> --workflow scope.yml \
  --limit 5 --json databaseId,headSha,conclusion,status \
  --jq '.[] | "run="+(.databaseId|tostring)+" "+.headSha[0:7]+" "+.status+" "+(.conclusion//"-")'
gh run view <run> -R asimov-agent/llgenie --json jobs \
  --jq '.jobs[] | "job="+(.databaseId|tostring)+" "+.name+" "+.conclusion'
gh run view --log --job <jobId> -R asimov-agent/llgenie 2>&1 | grep -iE 'error|fail|assert|LINT|missing' | head -30
```

Never report from `statusCheckRollup` alone: a cancelled run reads `fail`, a job
that cannot load has zero jobs so every rollup reads clean, and an
owner-disabled producer reds its dependents' gates. The log line is the claim.

## Pre-push local gates (a red you can see before CI does)

`write_file` strips the trailing blank line on markdown. A `docs/changes.d/*.md`
fragment, an `agent-wiki/` entry, or any note written by `write_file` will very
often end without a final `\n`, and `make ci-lint` (the linefeed/editorconfig
gate, `scripts/lint_linefeeds.py`) reds on exactly that with
`LINT FAIL — files missing a trailing newline:` and the file path. The scope job
runs `make ci-lint` first, so a one-byte defect reds the whole `scope` leg.

Before every push that touches markdown, run the local gates:

```bash
python3 scripts/lint_linefeeds.py            # LINT OK / LINT FAIL + offending paths
python3 scripts/check_docs.py check --base upstream/main
```

Fix: ensure **exactly one** trailing newline. `printf '\n' >> f.md` is only safe
when the file truly lacks one — check first (`tail -c 8 f.md | od -c`) or a file
that already ended in `\n` gains a blank line and can red a blank-line gate.

## Correcting a red that is yours, on your own PR

When the red is a deterministic defect in files this lane authored, fix at the
source rather than arguing the badge:

1. Edit in the PR's own worktree; rerun the local gate until green.
2. `git add` the fix and `git commit --amend --no-edit` — keep the one atomic
   commit; do not stack a second 'fix lint' commit.
3. `git fetch origin <branch>` first, confirm the remote head equals your
   pre-amend head, then `git push --force-if-includes --force-with-lease`.
4. Confirm the new head landed and a **fresh** run of the failing workflow is
   queued on it (the old failed run sits on the dead sha and does not clear).

Pushing a one-line correction to a head whose `scope` leg is already red
supercedes a dead sha — the in-flight heavy legs on it could not have merged
(scope-red blocks merge), so nothing mergeable is destroyed. The "do not push
while a run is in progress" fleet rule guards *another lane's* live matrix, not
your own already-unmergeable head.

## Never weaken the gate to go green

If the red is `make check-security-scan`, `enforce_events` routing, or any
security gate, the fix is never to move the gate to `push`/`pull_request`, never
to exempt the file, and never to cite a by-design red in a roster to make it look
watched. Fix the producer, or file the issue that names the root cause.

## Main-only live-step reds with opaque exit-2 usually resolve to persistent conditions — the annotation, not the gate, is the defect (#1714 audit)

Three main-only live steps red with the identical generic `Node.js 20` warning +
`exit code 2` and no target stderr, on unrelated heads in one day (2026-11-04:
`test-unit-network` @ `9ca3a5f4`, `check-quant-catalog` @ `90bab322`,
`ci-top-tier` @ `90bab322` — runs 41859064370, 41898591433, 41898591469). Triage as
ONE class, but pull each failing job's LOG before calling it a flake:
- The job log carries the real cause even when the annotation truncates it.
  `check-quant-catalog` job 126814723146's log read `the committed plan
  https://huggingface.co/.../resolve/... is gone` → `make: *** [Makefile:318:
  check-quant-catalog] Error 1` — that is the dead-link DRIFT (#1712), a
  deterministic condition. `ci-top-tier` run 41898591469 reached attempt 2 and
  stayed failure — a persistent top-tier DEFECT (#1713/#1723), not a
  self-healing flake (a retry that self-heals would have gone green on attempt 2;
  it did not). Only `test-unit-network` (no follow-up success on its head) was an
  unconfirmed single transient.
- Verdict: a "three flakes" claim overstates the case without the log pull; the
  actual defect is that the check-run annotation drops the target's log tail
  (generic Node20/exit-2), so flake-vs-drift is not decidable from the check run.
- Fix direction: expose the real exit-2 stderr (target log tail) in the failure
  annotation — then flake-vs-drift is decided from the check run without a log
  fetch. Do NOT add a blanket auto-retry/debounce on a failed-with-cause run: a
  blind retry re-times the deterministic drift and re-opens the separator-issue
  churn (#1250) it claims to stop. A debounce keyed to step+sha may skip only when
  the last SAME-STEP success is on the current main sha. Refute a "flake" with the
  log line; never with the badge colour.
