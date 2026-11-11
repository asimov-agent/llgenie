# Deferrals: why they never retry themselves, and how to sweep them

A deferral is exit 0 by design (a policy decision, not a broken gate) with one marker-deduped comment per head
SHA. The gate fires only on a completed CI run, so a blocker that clears **without a push** — a secret added, a
review posted later, `do-not-merge` removed, a pending check that finished — leaves a green PR unmerged until a
human re-runs the job. Close it with a second trigger over the SAME decision, never a second merge path.

## Shape of the sweep

- Keep the deferral marker addressable (`<!-- auto-merge: deferred <head> -->`, already written one per head
  SHA) and add a `recheck` that lists the open PRs and, for each whose marker names its **current**
  `headRefOid`, runs the ordinary `run(pr, head)` — approve as the other identity, merge, verify closure.
- Skip a marker for an older head (that verdict described another tree) and skip a PR with no marker: the sweep
  retries its OWN deferrals, not every open PR. `do-not-merge` still wins.
- Bound it (`--max-prs`, 5) and print one line per PR (`retrying`, `not a retry`, `cap reached`), so a sweep log
  answers "why is #N still open" without a second tool.
- Schedule it (`schedule: "*/30 * * * *"`) with the owner PAT and the approver token, and guard the existing
  `merge` job with `github.event_name == 'workflow_run'` so the schedule does not try to resolve a run that does
  not exist. The sweep stays runnable by hand through the make target or a re-run of the last sweep.
- **Do NOT also add `workflow_dispatch` to that file.** A dispatchable workflow is a different contract in most
  hardened repos: the suite requires it to carry the repo's byte-identical owner/collaborator guard job
  (`github.actor` AND `github.triggering_actor`, `admin|maintain|write` only, before any secret) and to state
  its contract in the README. A file that never had a dispatch trigger has none of that, so the "harmless"
  extra trigger reds the whole unit suite on the workflow-guard and dispatch-form tests while the feature is
  correct. Before adding a trigger, `grep -rl "<file>.yml" tests/` and read what those tests demand of it.
- The scheduled sweep has no triggering actor: pass the token's own account (`actor=token_login(gh)`) rather
  than leaving the author gate to refuse a bot-opened PR for "not saying who triggered it".

## Testing it with a fake `gh`

- The fake must answer `pr list` AND per-PR `pr view <n>` for several numbers, or a sweep that touches the
  wrong PR looks identical to one that works. Assert on the recorded argv that the retried PR merged and that a
  stale/absent marker produced no `pr review` and no `pr merge`.
- Embed the data so it is JSON again: `DATASET = {json.dumps(rows)!r}` inside the generated fake is a Python
  *string*, so re-`json.dumps`ing it encodes the string and the consumer iterates characters. Use
  `DATASET = json.loads({json.dumps(rows)!r})`.
- A fake PR keeping its default `headRepository` (a placeholder like `o/r`) is a third-party fork, so the case
  defers as a stranger instead of exercising the retry — set `headRepository.nameWithOwner` to the trusted repo
  in the fixture.
- A fake `gh` with no `pr list` branch exits 1 with EMPTY stderr, which reads like a crash in the code under
  test rather than a missing handler.

## A `workflow_run` gate can arrive after the PR is already merged

The run that triggers the gate is queued before the merge, but the gate starts only after every `needs:` job
finishes — minutes to an hour later. A human (or a second run) can merge the PR in that window, and the
resolution step then finds no open pull request and fails with "no open pull request for run <id> … a green PR
must never be silently dropped".

- Treat `state != OPEN` as a **successful no-op** (print `PR #N is MERGED — nothing to merge`, exit 0) and keep
  the loud failure for a run whose PR cannot be found at all. Otherwise every human merge paints a red run over
  a correct merge and trains the reader to ignore the gate.
- The same applies to a re-run after the merge: `gh run rerun <id>` is safe (the original `event`/`conclusion`
  conditions still hold and the job re-reads the current PR state), but its log will say the PR is MERGED —
  the expected answer, not a regression.
- Choosing WHICH run to re-run matters: a rerun of another PR's gate (the PR merged minutes earlier) fails with
exactly that "no open pull request" message. Match the run to the PR by the deferral comment's timestamp, not
by "the newest auto-merge run".
