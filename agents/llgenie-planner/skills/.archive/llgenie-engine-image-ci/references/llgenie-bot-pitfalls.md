# llgenie bot maintenance — recurring failure modes and the gates that bite

Rules learned from fixing the repo's bots (rebase-bot, fix-bot, issue-bot, architecture-bot).
Each is a mechanism, not an incident: apply it before writing the next bot change.

## Clone layout (differs from AGENTS.md's wording)

In `/home/asimov/repository/git/llgenie`, `origin` is the UPSTREAM
(`asimov-agent/llgenie`) and `fork` is the user's fork (`andyholst/llgenie`). AGENTS.md
calls the fork "origin". Always check `git remote -v` before pushing; push the feature
branch to `fork` and open the PR with `--repo asimov-agent/llgenie --base main
--head andyholst:<branch>`.

## A decision must never be made from a lazy GitHub field

`gh pr list --json mergeStateStatus` returns `UNKNOWN` whenever GitHub has not finished
computing mergeability (very common right after a push or a comment). `UNKNOWN` is not
"nothing to do": re-query the single PR with `gh pr view <n> --json mergeStateStatus`,
bounded (a few attempts with a short delay, overridable per run), and if it still does not
resolve, report it as DEFERRED BY NAME so the next run retries. A sweep that files
`UNKNOWN` under "does not need anything" silently starves the work forever.

## A bot's own record is its DONE marker, never "any comment"

A claim comment already contains the bot's name followed by a timestamp, so a
`re.search(r"<bot>[^0-9]{0,40}<date>")` over the thread matches the CLAIM. Read the thread
with `bot_claims.DONE_RE`, require the marker's bot, its date == today, and the kind that
means success (`rebased`, `repaired`, …). Failures must record a releasing/neutral kind
(`gave-up`), or one failed attempt burns the rest of the UTC day. Test fixtures must use
the real `<!-- bot-done: … -->` shape — a fixture that writes a bespoke shape hides exactly
this bug.

## Never let a mid-run `make` parse a tree that is mid-rebase

A conflict can BE in `Makefile`, and GNU make parses before running any target:
`Makefile:<n>: *** missing separator. Stop.` stops an agent leg before the model is called.
Snapshot the Makefile BEFORE the checkout and reach the agent through it
(`make -f "$MK_SNAPSHOT" <agent-target>`), and make the in-container command call `hermes`
directly instead of `make <internal-target>`, which would re-read the conflicted file.

## Every `hermes -z` line derives its model from `$(nous-alias)`

`tests/test_issue_implementer.py` scans the Makefile for `hermes -z` lines and fails any that
spell the model out. Writing `hermes -z "$(cat)" $(nous-alias) --reasoning medium --yolo`
inside a `bash -lc '…'` container command works: make expands the variable before the
container command is built, and the pin keeps one source.

## A new agent leg must stay inside the credential and redaction seams

- Forward only names in `AGENT_SHELL_KEYS` with `-e`; anything else (a doc path, a brief
  path) trips `tests/test_agent_shell_keys.py` ("agent leg forwards a credential the agent's
  shell is not proven to see"). Pass such values as make variables on the container command
  line instead.
- Run the leg through `$(call scrubbed_run,…)` and keep the internal `_…` target if the leg
  needs one: `tests/test_scrub_log.py` keeps a roster of internal targets that call `hermes`
  and asserts each is reached by a redacting public leg. If a leg calls `hermes` inline, update
  that roster and assert the inline call.

## Producer hygiene gates read the source text, not the runtime value

- Open issues/PRs with `--body <variable>`, never `--body-file -`: `check_pr_hygiene` treats
  `-` as a placeholder body.
- Pin the commit identity as `git config user.name "Asimov Agent"` / `git config user.email
  support@docondee.com`. An inline `-c user.name=Asimov Agent` is truncated to `Asimov` by
  `check_pr_authors` and fails the allowlist.
- `check_docs` requires every `##` make target in README; `check_dispatch_forms` requires the
  generated README table to be regenerated (`make check-dispatch-forms report`, paste between
  the markers); `check_wiring` requires every script/test to be reachable from a target CI runs.

## Verification loop that actually proves a bot fix

1. `~/llama-gguf-tools/.venv/bin/python -m pytest tests/<target>.py -q` while iterating —
   `make test-unit` runs the same pytest but takes 11–13 minutes.
2. Run `make test-unit` against the FINAL tree (edits during the run invalidate its result).
3. Prove the behaviour end to end, not just in unit tests: run the fixed decision function
   read-only against the live repo, or reproduce the failure shape in a scratch dir (e.g. a
   `Makefile` full of conflict markers) and show the old command failing while the new one
   succeeds. Quote the measured output in the PR body.
4. Judge gates: `check-wiring`, `check-docs`, `check-workflows`, `check-dispatch-forms`,
   `check-pr-hygiene`, `check-pr-authors`, `lint`, `openspec-validate`, `openspec-tasks-check`.

## A bot run that looks stuck: read its steps, not its log

`gh run view <id> --log` returns **nothing** until the run completes, so silence is not a hang. The
per-job steps API answers while it runs:

```bash
gh run view <id> --json jobs -q '.jobs[] | "\(.name) \(.databaseId)"'
gh api repos/<owner>/<repo>/actions/jobs/<job_id> \
  -q '.steps[] | "\(.number). \(.name) -> \(.status)"'
```

Calibrate before calling it stuck: one Hermes pass that reads AGENTS.md, edits and runs the repo's gates
is 55-65 minutes, so a job sitting in the implement step at 60 of 120 minutes is normal. What is not
normal is that nothing leaves the runner until that step ends — the branch, the commit and the PR all
come after it, so a run killed at the ceiling loses the entire agent pass and reads as an infrastructure
cancellation rather than a budget failure. When reporting status, quote `N of M minutes in step <k>`;
when a run must be restarted, cancel it and re-dispatch rather than letting the timeout be the signal.

## A bot PR whose whole diff is a scratch file means the work went outside the mount

The agent leg runs in a `--rm` container with exactly one writable mount (`-v "$(CURDIR):/repo"`). Any
path the agent is told to use outside it (`../<repo>-wt/<name>`, `/tmp/...`) is deleted with the
container, while the agent reports success — the tell is a PR whose entire diff is a run input
(`triage.md`, `comment.md`) or a line of bookkeeping, with `closes #n` on it. Diagnose in this order:

1. the redacted transcript's closing summary names the path the agent wrote (and the commit it made);
2. confirm the geometry with a probe: a write to `../outside/f` exists inside the container and is
   absent on the host, while a write into `/repo` lands;
3. the leg's prompt must state "edit `/repo` in place, do NOT create a git worktree" — AGENTS.md's
   worktree rule is for a host agent, not for a one-mount `--rm` container;
4. the exit code is not evidence: a tree-derived check (`git status --porcelain` minus the run inputs)
   is what turns the next silent no-op into a loud, named failure.

## Dispatching, claiming and cancelling the issue-bot

- Labelling an issue `agent:implement` **is** a dispatch (`issues: labeled`). Filing issues with that
  label starts a run — check for one before dispatching by hand.
- Do not guess the pick: `make issue-bot-dispatch REPO=asimov-agent/llgenie DRY=1` prints `issue=` and
  `branch=` from the same code path the bot uses.
- A dead or cancelled run's claim keeps occupying its issue until the marker's `ttl=` expires (180m), so
  the next run skips it by name ("commented on … without a done comment"). Wait the TTL out, or pin a
  different issue.
- `concurrency: group: issue-bot, cancel-in-progress: false` **queues** a second dispatch behind the live
  one. A pinned dispatch of the issue the live run already picked will implement it twice — cancel the
  redundant one with `gh run cancel <id>` and confirm `completed cancelled`.
