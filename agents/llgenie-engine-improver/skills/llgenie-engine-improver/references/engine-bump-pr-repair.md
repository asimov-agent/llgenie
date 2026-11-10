# Repairing a red engine-bump PR (guards + change-note + unit leg)

An engine-bump PR (the weekly rolling pin) can go red on several independent gates. **The `guard` /
`scope` job is COMPOSED — its checks run in sequence and each failure MASKS the next, so a fix for
the first red simply reveals the second.** Expect to peel several layers in one session; do NOT
report "one gate fixed" as done. Read the guard job's failing STEP name (not the red badge), fix it,
then re-run the guard to reveal the next. Enumerate the whole stack locally before you push so you
add every owed element in one pass (see "Enumerate every hygiene element up front" below).

## The gates

Each is a separate step of the composed `guard`/`scope` job (a bump PR touches product code, so it
owes all of them):

- **check-pr-agents-line** — the body must carry a `BASE: <sha> (== origin/main at open)` line —
  the parenthetical is REQUIRED. A bump body whose BASE line reads `BASE: <sha>` without
  `(== origin/main at open)` reds here even though the sha itself is correct (a sibling PR whose
  body already carries the parenthetical stays green — check every body's BASE line, not just one).
- **check-pr-acceptance-form** — a bot PR body must carry its own `## Acceptance criteria` checklist.
  The bump bot does not emit one; add a compliant section yourself. **The checklist must describe the
  design as it currently is.** After a re-scope (e.g. a source-compile cell re-pointed at a prebuilt
  base with zero install steps), criteria that still name the removed steps (`-e .` overlay, a poetry
  bootstrap) are untickable — no reviewer can honestly tick a step that no longer runs — so rewrite the
  list to the actual implementation in the SAME body edit.
- **check-pr-acceptance** (distinct from `-form`, and COMPOSED after it) — a merged PR must close an
  issue whose OWN acceptance boxes are ticked. This is verdict-gated: only the reviewer/tester lane
  ticks the linked issue's boxes after a green producing run, so a writer lane can NEVER green it from
  its own side. Do not tick another lane's issue boxes to make the row go green — that is a fabricated
  verdict and a worse defect than the red. Fix what is yours (the `-form` checklist, the stamps, the
  note) and name the verdict-gated remainder as the remaining blocker, with the run id whose green
  outcome unlocks it.
- **openspec-change** — a PR that changes product code must name an active openspec change via an
  `OPENSPEC: <change-name>` line in the body (or add a change dir). For the engine-bump cadence the
  active change is `publish-changed-pin-images` — name it. Prove locally by running the gate's
  pairing/validation with and without the line (findings `[]` vs a finding).
- **check-pr-closing** — the "no dangling claim" rule. A *claim* is either an `Issue: #N` line in the
  commit/PR text OR a subject/title ending in `(#N)`. Any claim must be re-served by an adjacent
  `closes|fixes|resolves #N` in BOTH the squash commit text and the PR body. The current engine-bump
  convention is "weekly rolling pin; closes no issue" — no claim at all, so no `closes` line is owed.
  Red here means the commit message or body still carries an `Issue: #N` claim (e.g. a stale template
  line) with no adjacent `closes`. Fix: remove the claim from the commit message (amend or re-roll)
  and align the PR body to the convention. Run `make check-pr-closing` locally to prove it before push.
- **check-pr-base** — the branch must be cut from the current `origin/main`. Red means the base pin is
  stale; `git rebase --onto origin/main <merge-base> <branch>` (or re-cut) fixes it.
- **check-docs** (change-note, behavioural-surface rule) — a bump that touches a behavioural surface
  (e.g. `containers/`, `Dockerfile.*`) must ADD an `agent-wiki/<stem>.md` change note wired into
  *this branch's diff*, plus a `docs/changes.d/<pin-fragment>` entry and a `CHANGES.md` row.
  **A note left unchanged from a previous bump does NOT satisfy it** — check-docs diffs
  `merge-base...HEAD`, so a stale note (still pointing at the prior PR/pin) is invisible to the gate.
  Fix: re-point the note to THIS PR and the NEW pin, update the fragment's `old -> new` pin and PR
  ref, then `make changes-index` to regenerate `CHANGES.md`, and **commit** all three together
  (check-docs reads committed HEAD, not the index — staging alone leaves it red).

## Metadata body edits do NOT retrigger CI — re-run the job at the unchanged head

Editing the PR BODY (adding `OPENSPEC:`, `## Acceptance criteria`, fixing the BASE parenthetical)
changes no commit, so no new CI run starts. But `ci.yml` reads the body AT RUN TIME, so a
**re-run of the existing guard/scope run at the same head** reads the now-complete body. After each
body edit: `gh run rerun <failing-run-id>` (or dispatch the guard/scope workflow at the head), wait
for it to settle, and read the fresh conclusion — do not assume the old red reflects the fixed body
(it evaluated the pre-edit body). The same holds for a fix that landed as a commit: re-read
`pulls/<n>.head.sha` and re-run so CI reads the new head, not the old sha's stale rows.

**A rerun during the in-flight window is refused, not queued.** `gh run rerun` and
`POST /actions/runs/<id>/rerun` return HTTP 403 `This workflow is already running` until the current
run concludes — the exit code is not the fact, and repeating it a dozen times changes nothing. Order
it correctly: finish ALL body/criteria edits first, wait for the in-flight run to reach `completed`,
THEN rerun once. Check-runs are also re-evaluated only on a head move, so a body-only edit never
refreshes the old red rows by itself — either rerun the specific workflow after it settles, or push a
commit and let the head move do it.

**A run stuck `pending` with no jobs is a runner-queue fact, not a defect to chase.** Report it once
("cell queued, no runner assigned, build not started") and stop probing: a bounded poll (a handful of
fetches with backoff) is the whole budget. Re-querying a queued run every few seconds for half an
hour spends the session on `pending → pending` and produces no new evidence; the honest line is
"blocked on a runner", and the PR stays red on the verdict-gated row until that cell actually runs.

## The `trigger` row is a DIFFERENT class — a cancelled producer, not metadata

`guard`+`scope` green on all six does NOT make the PR mergeable: `engine-build-pr-trigger` stays red
with `FAIL engine=<id>: producer cancelled — nothing to wait for (run <run-id>)` when the engine-build
PRODUCER it dispatched was cancelled / never published. That is the publish-pipeline layer (#2259's
collect-and-dispatch domain) plus the reviewer/tester acceptance write-back — **no body / stamp /
note edit can green it.** Classify it from the trigger's OWN log (quote the `producer cancelled`
line + run id), then make the publish-gap MEASURED rather than prose.

**Measure the publish gap with `scripts/check_engine_pins_published.py check --base <merge-base-sha>`
run FROM EACH PR-HEAD WORKTREE — never the primary checkout.** In the primary checkout HEAD == main,
the params match `--base`, so `repinned_engine_ids` finds nothing and it prints "no engine this change
repins; nothing to check" with rc=0 — a FALSE green. From the PR-head worktree the bump is at HEAD,
so it computes each repinned engine×variant's exact tag (`engine_image.resolve().tag`) and probes the
registry: `[pins] NOT PUBLISHED <ref> (HTTP Error 404: Not Found)` + `FAIL N repinned image(s) are
not published`. That measured NOT-PUBLISHED tag set is the concrete evidence to hand the
reviewer/publish lane — a bump may merge only once each tag resolves (issue #1622).

The engine-bump generator can force-update the branch to a NEWER pin while you are working,
overwriting your push. Evidence: the remote head sha changes and the commit message is the
convention wording at a newer pin than your own edit.

- After every push to an engine-bump branch, re-read the remote tip
  (`git ls-remote <remote> refs/heads/<branch>`) before assuming your edit is the head.
- If re-rolled: read the fresh head, adapt your fix to the NEW pin, and commit it **additively on top**
  of the generator's commit (a fast-forward follow-up). Never amend or overwrite the generator's
  commit — it owns the pin message; your docs/guard fix is a separate additive commit.

## Verify the unit leg in the hermetic container, not on the host

The host's python `pytest` fails on repo tests with **empty stdout and rc 2**, even on a plain
collection — the suite is hermetic and `make test-unit` runs it inside a container
(`$(RUNTIME) run $(TEST_OPTS) $(TEST_IMG)`, image `llgenie/test:latest`, `-v "$(ROOT)":/repo:rw -w
/repo -e HOME=/root`). Trivial throwaway tests pass on the host; the repo's `tests/conftest.py` needs
the container env. So do not chase a host pytest failure as a code bug — it is the wrong runner.

Run a targeted test the same way CI does:

```
docker run --rm -u root -v "$PWD":/repo:rw -w /repo -e HOME=/root \
  llgenie/test:latest python -m pytest tests/<file>::<test> -q --no-header -p no:cacheprovider
```

A `2 passed in 1.1s` inside that container at your pushed head is the real verification the two
assertions the gate reds on now hold — cite it instead of a claim that "CI should pass".

## Ordering that avoids rework

1. Confirm the actual red gate from the guard job's step list.
2. Cut a worktree from the CURRENT `origin/main` (fetched now), not a remembered sha.
3. Fix the specific gate; if a stale pin/base is also involved, rebase first so the guard reads the
   right commit set.
4. Verify each gate locally BEFORE pushing: `make check-pr-closing`, `make check-pr-base` (or a
   `merge-base` check), `make check-docs`; plus the targeted unit tests inside the container.
5. Push, then re-read the remote tip to catch a generator re-roll; apply additively if it happened.
6. Wait for the full CI at the final head and report the green run id + head sha, not a promise.
