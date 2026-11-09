# A verdict-gated tick's `(proven: …)` must name a CI run or a command+rc+sha — the gate rejects a bare review line

## Failure (learned on #1880/#1881, 2026-11-06)

Ticking #1880 AC1 with `(proven: reviewer verdict #1881 @ b48bf9fc)` — a bare review citation with no `run=`
and no `proven: <command> rc=<n> <sha>` — POSTS and reads back as a tick, but the next `check-pr-acceptance`
pass on the PR fails with `ci: a ticked acceptance criterion names no replayable run id or reproducible
command+rc+sha` (guard job red, issue #745). A tick is only as honest as a one-command re-measure: a review
name + sha is not re-measurable from the issue thread alone.

## Command

`scripts/check_pr_acceptance.py` is SUBCOMMAND-driven: `check` or `report`. A bare
`check_pr_acceptance.py --issue N …` exits with `argument cmd: invalid choice` (and, if the shell captured the
prior rc, a false `rc=0`). Run the real gate as:
`check_pr_acceptance check --cwd /tmp/wt<NNNN> --body-file <FRESHLY fetched PR body> [--gh gh --rev <sha>]` —
rc=0 prints `OK — every closed issue's … is checked or named out of scope`. It reads the closed issue's
`## Acceptance criteria` LIVE, so a freshly PATCHed tick is graded without re-pushing the branch.

When you verdict-gate tick a closed issue's criterion, build `--verdict-ref` so `_is_provable_tick` in
`scripts/check_pr_acceptance.py` returns True:

- name a CI `run=<id>` (the strongest, #1858), and/or
- `proven: <command> rc=<n> <sha>` (a reproducible command + its exit code + a tree sha, ANY 7-40 hex),
  e.g. `gh api actions/jobs/<job>/logs | grep -c '<needle>' rc=0 run=<run> head=<sha>`.

For a test-proven criterion, cite the actual grading command:
`proven: pytest tests/test_check_pr_acceptance.py tests/test_acceptance_writeback.py -q rc=0 head=<sha>`.
Run pytest under `$HOME/llama-gguf-tools/.venv/bin/python3` — the default `python3` lacks pytest
(returns module-not-found). VERIFY rc=0 yourself before naming it, on the exact head archive, not from memory.
#1811 correction (2026-11-06) replaced 5 bare refs with this command+rc+sha form in one write-back;
`acceptance_verdict` then returned 0 findings and all 5 items `_is_provable_tick`=True.

Verified as the fix: re-render + re-PATCH #1880 with the ref naming `run=42280478755` + `rc=0`; the module's
own `acceptance_verdict(body, pr_body, 1880)` then returns `[]` (0 findings) — the gate is satisfied from the
issue thread alone. A bare `reviewer verdict #<n> @ <sha>` is NOT enough; it reds again.

## Each criterion's marker must cite the command that grades THAT criterion

A ticked box is only evidence of its own criterion when its `(proven: …)` names the command that
actually exercises that criterion. Reusing one green command across several boxes passes
`_is_provable_tick` (it carries `rc=0` + a sha) so nothing reds, but the marker then misattributes
proof: a hermetic regression AC is ticked with a live-network run, or vice-versa, and the issue
thread carries a citation proving a different contract than the box it sits on. The gate cannot
detect this — it checks the ref is replayable, not that it exercises the criterion.

When one write-back ticks several ACs, pair each `--proven <n>` marker with the command you ran FOR
criterion n — the hermetic regression AC cites its hermetic test file, the live-Hub AC cites its
live run, each with its own totals. Do not drag the first passing command into every box. Fix a
cross-cited marker by re-PATCHing the body with the criterion's own command (literal `.replace`
surgery, `writeback-stale-pin-surgical-patch.md`), not by re-running `writeback`.

## Never

- Never settle for a bare review-name `(proven:)` when the criterion is verdict-gated: the gate red will
  unmask your tick as non-replayable and the PR stays blocked on your own evidence.
- Never assume a posted+read-back tick cleared the gate — re-run `acceptance_verdict` locally (or wait for
  the guard pass) before reporting green.
- Never tick a sweep-evidence AC (e.g. an engine-build success "with run id recorded") from a run where
  the heavy job was SKIPPED by the guard short-circuit. If the CI at head fails check-pr-acceptance only
  and `linux`/the sweep shows `skipped`, NO sweep has run — hold that AC unticked until a fresh guard pass
  runs it to success. The code-side AC you CAN prove (with a command+rc+sha) is what unblocks the guard;
  tick only that one and leave the sweep AC `- [ ]`. A partial tick (some `[x]`, some `[ ]`) is the honest
  state, not an error — the gate's `acceptance-unchecked` finding for the held AC is expected and correct.
- When a PR's diff vs the API `base_sha` "deletes" a rule/pin (standing-rules, test_agent_profiles), VERIFY
  the merge-base before crying regression (#1895/#1896 both looked to delete the #1889 fleet-rule pin but did
  not): the PRs fork from a pre-merge base, their own diff (`gh pr files`) touches nothing there, and main
  keeps them on merge. `git diff <api_base>..<head>` over an advanced main is a false alarm; diff vs the real
  merge-base.
- Re-anchor, don't re-judge, after a forced head push — but PROVE the re-anchor by execution, not byte-identity
  inference. Materialize the new head and re-run the same grading command there:
  `git archive refs/remotes/live/pr<NNNN> | tar -x -C /tmp/wt<NNNN>b` then the same `pytest …`/`make <gate>`
  that produced the tick. Byte-identical graded files make a re-judge unnecessary, but a stale SHA must never be
  reported green from an inference — say what the command returned at the sha now live. A written-back
  `head=<sha>` may keep the measured sha even as the PR head advances — name both (measured + re-anchored).
- Ticking an issue body does NOT re-trigger the PR's CI. After you PATCH the closed issue's criteria, the
  PR head keeps the same (old, red) run — no fresh guard/sweep run appears from your write-back. So do not
  wait on, or expect, a new run after a body PATCH; a fresh sweep run needs a push or a dispatch by the
  lane that owns the branch. Say "held pending a fresh run" and hand it back, do not spin.
- A PR body `## Not covered` must satisfy the gate contract (#1792 `_declared_out_of_scope`): it matches each
  UNTICKED criterion's LEADING 3 WORDS beside a `#<n>`. An abstract line like "AC-2/AC-3 → #1899" earns
  False — the body must echo the criterion's actual first words ("the cold cache … #n", "no regression the …
  #n"). Learned on #1905 (AC1 ticked clean, but AC2/3 stayed red until the section was fixed). Always run
  `check_pr_acceptance check --cwd <head> --body-file <prbody>` (rc1 names the offending criteria) rather
  than trusting a maintainer's "Not covered is in the body" claim.
