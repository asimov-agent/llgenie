# Releasing a designed acceptance hold after a verdict-gated write-back

The pattern when a review verdict ticks the linked issue's criteria and the PR must then go green.

## Once acceptance clears, check-pr-base can UNMASK under it — that is a second lane's cut, route it

A write-back that clears `check-pr-acceptance` can expose the NEXT gate in the same guard job:
measured on #1816 (rerun of both holding runs at the same head `a9b7634d9e`), the guard log
flipped from `[check-pr-acceptance] 4 violation(s)` to `[check-pr-acceptance] OK` — then
`[check-pr-base] FAILED: <head> is NOT cut from origin/main — merge-base is <older sha>, foreign
commits (N)` — the #845 stale-base hold (base 2-behind current main). That red is the REBASE lane's
cut (#1015/#845), not a reviewer verdict item; scope's rerun can already be SUCCESS while the
guard's own remaining red is only check-pr-base. Do NOT chase it — message the rebase lane directly
with the PR, head, merge-base-and-foreign-commit detail, and the base-behind count, and say the
reviewer side is done. A rerun that re-invokes only `--failed` after write-back is the right probe —
it re-reads the live bodies AND reveals the unmasked base gate in minutes, cheaper than guessing
which steps clear.

## Prove the fixture in the CI image, not only the venv, when the dispatch cites `llgenie/test:latest`

A dispatch saying "N/N tests pass in `llgenie/test:latest`" quotes the implementer's container read;
the reviewer's own proof must be reproducible in that same image. Use the Makefile helper — a raw
`docker pull llgenie/test:latest` fails because the published tag is hash-based:

```
make test-image      # scripts/ci_images.py ensure test -> pulls ghcr.io/asimov-agent/llgenie/test:<hash> and tags llgenie/test:latest
docker run --rm -v "$PWD":/repo -w /repo llgenie/test:latest \
  python -m pytest tests/test_check_pr_acceptance.py -q
```

Run it from a worktree at the head under review, and post the container output as its own record
comment so the wire carries CI-image evidence, not just the venv run.

## The proof is the LIVE-body re-read, not a CI rerun

After `acceptance_writeback writeback --issue <n> --proven <subset>`, the authoritative proof the
hold clears is the LOCAL re-read of the gate against a **freshly fetched PR body**:

```
gh api repos/<o>/<r>/pulls/<n> --jq .body > /tmp/prbody.md
python3 scripts/check_pr_acceptance.py check --body-file /tmp/prbody.md
```

For a full tick this must fall to `[check-pr-acceptance] OK — every closed issue's
## Acceptance criteria is checked or named out of scope` with **rc 0**. Two zero-checks bound the
claim: **zero `tick-unprovable`** findings AND **zero `acceptance-unchecked`** on the written-back
body. The only legal remaining row is a deliberately-held out-of-scope criterion — and then the
gate reads rc 1 naming ONLY that held item, never the criterion you ticked.

The rendered-body class check (`acceptance_verdict(body, pr)`) and the live-body gate re-read
together are the drop proof; a CI-side rerun is optional evidence, not a requirement.

## Group stale CI reruns by run id

A designed hold can pin MORE than one workflow run red at the same head — the design acceptance
`guard`/`check-pr-acceptance` run AND a separate `ci-scope` workflow run, each with its own
`check-pr-acceptance` job. Enumerate the whole board before calling reruns done:

```
gh pr checks <n> -R <o>/<r>      # each row's detailsUrl -> run id
```

Group the red rows by run id and `gh run rerun <id> --failed` **once per distinct run id** — a
single rerun that clears the guard leaves the scope row red, and half-cleared gates are reported as
half-cleared, never as green.

## The CI red at a ticked head is a stale read, not a build break

The acceptance guard run executed BEFORE the tick, so its live-body read saw the unticked
criteria; that red is the run's snapshot of a superseded body, and is the expected state right
after a write-back. Never report it as a defect of the PR. Before posting final state, re-read
`state`/`mergedAt` — another lane may merge while you poll.

## A body edit auto-reinvokes the run; poll jobs, do not re-rerun

Editing the PR/issue body to tick criteria can AUTO-trigger a fresh run at the same head, so a
follow-up `gh run rerun <id> --failed` returns `cannot be rerun — already running`. Do not treat
that error as a failed rerun and do not force a third: the auto-invoked run already re-reads the
ticked live body and clears the hold on its own. Poll the run's jobs and trust their own
`status`/`conclusion` instead of the rerun command's exit:

```
gh api repos/<o>/<r>/actions/runs/<run>/jobs?per_page=100 --jq '.jobs[]|{name,status,conclusion}'
```

A run's `conclusion` is `null` while ANY job is still `in_progress`; loop until it is non-null
before calling the run green or red. The acceptance-clear line to grep from the guard job log is
`[check-pr-acceptance] OK`.

## Releasing ONE held AC when its blocking run finally concludes — tick only that one, prune the `- unproven:` bullet

A hold was placed because a run was `in_progress`; the release trigger is that the **run**s re-read now
shows `status=completed` AND the *named job* `conclusion=success` at the judged head. Re-poll the run id
before writing any further verdict comment: `gh api …/actions/runs/<id> --jq '{status,conclusion}'` plus
`…/runs/<id>/jobs --jq '[.jobs[]|{n:.name,c:.conclusion}]'`. Confirm the JOB name maps to the criterion
(e.g. `engine-build-vllm-rocm` with `push=false` for a "vllm arch=rocm push=false green" AC) — a green run
whose job list lacks that cell proves nothing.

Do NOT then run `acceptance_writeback --proven <that one>`: `--proven` is the complete set and un-ticks the
already-ticked siblings (writeback-subset-citation-traps §1). Rebuild the body line by line instead:

- replace only the matching `- [ ] <criterion>` line with `- [x] <criterion>  (proven: reviewer <lane>
  run=<id> head=<sha> <job> success …)`, provable-shaped (`run=` present);
- keep every other `- [x]`/`- [ ]` AC line byte-identical;
- **prune the now-proven item out of the `- unproven:` bullet** — leaving it there makes the body assert
  both "ticked" and "unproven" at once.

PATCH the full body, then verify: re-read live, `[x]` count up by one, `_is_provable_tick` all-True, and
the gate now reads **rc=1 naming ONLY the still-held criterion** — that residual red is the designed hold,
not a defect. A half-released issue (some ACs ticked, one still `- [ ]` + `- unproven:`) is the correct
honest state; do not force the remaining box and do not re-open a tick from a `failure` run.

## Never leave a mid-flight snapshot as the final record

A record posted while a leg is `in_progress` is a snapshot, and a lower bound on the board — the
remaining job can still red. When the run later converges, post a SUPERSEDING comment (mark it
`supersedes <id>` and state the concluded status per leg) rather than letting the mid-flight
statement stand as the last word. Quote only concluded runs at the head; an unconcluded run has no
verdict, and `cancelled` is neither green nor red.