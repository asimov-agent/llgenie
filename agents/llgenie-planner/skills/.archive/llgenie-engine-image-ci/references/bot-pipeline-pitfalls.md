# Bot pipelines: the pitfalls that make a bot look green while doing nothing

Load this before changing a bot workflow (rebase/issue/fix/refine/architecture),
its decision script, or the make legs it calls. Everything here is enforced by
`make test-unit` or was measured on a real run.

## 1. A decision must be derived from real state, never from a stale field

- **`mergeStateStatus` is computed lazily.** A `gh pr list` right after a push,
  comment or merge returns `UNKNOWN` for every PR, and `UNKNOWN` is not an
  answer: re-ask that one PR with
  `gh pr view <n> --repo <r> --json mergeStateStatus`, bounded (a few
  re-queries with a short delay). A state that never resolves must be reported
  as **deferred to the next run**, never folded into "nothing to do".
- **Eligibility is the current state, not a daily marker.** A PR rebased this
  morning is stale again the moment `main` moves; an "already did X today"
  record bounds a cap, it must not bar real work. After a successful rebase the
  PR reads CLEAN, so nothing loops.
- **Never loop in one run on the same subject.** Pass the identifiers already
  handled in this run into the next decision (`--skip a,b`); append a subject
  on **failure** too — a failed attempt leaves it eligible, and re-picking it
  burns one model call per iteration up to the loop bound.

## 2. Markers: read the structured one, from the success kind only

- The claim protocol is `scripts/bot_claims.py`. A **claim** is posted before
  work; a **`bot-done:`** marker with a kind is posted after. `DONE_RE` parses
  it; `DONE_RELEASES` are the kinds that free the subject.
- A sweep that counts "already done" must parse `DONE_RE` and require
  `bot == <this bot>`, today's date, and the **success kind** (`rebased`,
  `fixed`, …). A regex like `<bot-name>.*<date>` over a whole comment body also
  matches the bot's own claim and any prose mention, so the bot skips work it
  never did. Failures must record a failure kind (`gave-up`), not the success
  kind, or one bad attempt marks the subject done for the rest of the day.

## 3. A loop's bound belongs inside the step

`tests/test_bot_decision_loudness.py` runs each decision step **alone** with a
`make` that exits non-zero, and requires a non-zero step exit. A bound that
lives only in the job's `env:` is unset in that harness, the loop body never
runs, and the step exits 0 while its decision crashed. Default it at the top of
`run:` (`MAX_PR="${MAX_PR:-10}"`).

## 4. Never invoke `make` while the tree is mid-rebase

`make` parses `Makefile` before any target. A conflict can BE in `Makefile`, so
`make rebase-bot-agent` (or any nested `make target` in a container) dies with
`Makefile:N: *** missing separator` and the agent never starts.

- Snapshot `Makefile` **before** the conflicted checkout and invoke through the
  snapshot: `MK=$(mktemp); cp Makefile "$MK"; make -f "$MK" <target>`.
- Run the model call **inline** in the container
  (`bash -lc 'hermes -z "$(cat)" $(nous-alias) --reasoning medium --yolo'`),
  never `bash -lc 'make _internal-target'`, whose make would re-read the
  conflicted file. Delete the now-dead internal target.
- On every failure path abort the rebase the actor started (`git rebase
  --abort`, no-op when idle) so the caller's next `make` still parses.

## 5. Invariants the unit suite enforces on agent legs

Check these before `make test-unit`, not after:

| Test | Rule |
|---|---|
| `test_agent_shell_keys` | every `-e NAME` forwarded to the agent image must be an `AGENT_SHELL_KEYS` credential (or a documented non-credential). Pass paths/settings as make variables on the container command, not `-e`. |
| `test_issue_implementer` | every Makefile line with `hermes -z` must use `$(nous-alias)` — the model id lives once. `--alias`, `--max-steps` and `-m <sentence>` are wrong. |
| `test_scrub_log` | every public leg that starts the agent image goes through `$(call scrubbed_run,…)`; the internal-hermes roster is pinned, so removing an internal target means updating the roster and asserting the inline call instead. |
| `test_rename_llgenie_serve` | no live file may mention the retired `llama_serve` module — not even in docs. |
| `test_bot_decision_loudness` | every decision step exits non-zero when its decision command crashes (see §3). |
| `test_bot_pipeline_isolation` | each scheduled workflow owns a unique `(minute, weekday)` slot and its own `concurrency:` group with `cancel-in-progress: false`. Pick an unused minute, not just an unused hour. |

## 6. Producer shapes (`make check-pr-hygiene`, `make check-pr-authors`)

- Both gates parse the **source text** of the producer, not its runtime value.
  - `gh … --body-file -` with stdin reads as a placeholder body → pass
    `--body "$variable"` instead.
  - An inline `user.name=<Name With Space>` in a Python argv is truncated to its
    first token → pin the identity with `git config user.name "Asimov Agent"`
    and `git config user.email support@docondee.com` before `git commit`.
- Commit subject: typed Conventional Commit. Body: `Issue:` / `Fix:` /
  `Benefit:` / `Technical:` — the same for bot-authored commits and PR bodies.

## 7. OpenSpec is the gate that fails last

- `make ci-openspec` runs `openspec-validate` **and** `openspec-tasks-check`,
  and the latter fails on **any** unchecked `- [ ]` in `tasks.md`. A PR whose
  code, tests and gates are fine can be red only because its final "Verified"
  task is unticked — tick it after running the commands, and record the
  measured numbers in it.
- Every `#### Scenario:` needs `- **Test:** file::test_case`; every test body
  needs `# Given / # When / # Then` markers separated by blank lines.
- The change dir is created first, then code; `make openspec-new NAME=…` and
  `make openspec-validate NAME=…` are the only sanctioned route.

## 8. Verification that does not lie

- Run the real gate: `make test-unit` (host venv `~/llama-gguf-tools/.venv`
  when present, else the test image). It is 10–15 minutes — start it in the
  background to a log file (`… > "$TMP/unit.log" 2>&1; echo EXIT=$? >> …`) and
  read the summary when it finishes.
- **Never pipe the suite through `tail`/`head`**: the pipeline exit code is the
  tail's, so a red run reports 0. Read `EXIT=` from the log or the raw run.
- A first red run is normal for a bot change: fix the real regression (the suite
  pins many leg shapes above) and re-run the **whole** suite; never claim green
  from a focused subset.
- For a "does it actually work" claim, drive the real thing once: run the fixed
  decision function against the live repo (read-only) and put the measured line
  in the work record / PR body.

## 9. PR timing in a fast-moving repo

- Squash merges land while you are still working: **re-check the PR's `state`
  before pushing a post-review docs commit.** A commit pushed after the merge is
  not on `main` — it needs its own issue + PR (branch fresh off `origin/main`,
  cherry-pick the lost commit, keep the same three-part message).
- A fork PR has no `gh pr checks` rollup; read
  `gh run list --branch <head>` and `gh run view <id> --json jobs` instead.
- Never merge. Stop at the reviewable PR and report the URL, what is green and
  what still waits for a reviewer.
