# A bot/workflow change is gated by CONTRACT suites, not by its own tests

A hardened repo pins its automation's shape with type-checked contract tests. They are cheap (seconds) and they
fail on a change that is behaviourally correct, which reads like a mysterious red in a module you never touched.
Run them BEFORE pushing; discovering them on a 12-minute pipeline wastes a cycle and the fix is always in the
workflow/Makefile, never in the test.

## Five-second pre-flight

```bash
docker run --rm -v "$PWD":/repo:rw -w /repo <test-image> python -m pytest \
  tests/test_workflow_guards.py tests/test_dispatch_forms.py tests/test_workflow_valid.py \
  tests/test_agent_shell_keys.py tests/test_bot_time_budget.py -q
```

Add the module that pins whatever the change touches (a fix-bot's own suites, the issue-bot's header
contract, the secret-output scanner). Rebase onto the current base first: a branch several commits behind
fails contracts the base has since tightened, and diagnosing those as the branch's own defect is wasted work.

## The contracts and their symptoms

| contract | symptom | fix |
|---|---|---|
| **Credentials only in `-e NAME`** | `an agent leg forwards a credential the agent's shell is not proven to see: ['X']` | `-e` carries credentials, nothing else. A path, a mode or a check name is set INSIDE the container: `bash -lc '… FIX_REPORT_FILE="$(REPORT_FILE)" scripts/loop.sh'` — make expands the variable before the shell sees the quoted command |
| **Wall-clock fits the rounds** | `the fix job allows 180 min but 5 rounds x (20 min check + 30 min repair) = 250 min` | `timeout-minutes >= rounds x (check + repair)`. Raising the attempt count without raising the cap cancels the run mid-round — the feature literally cannot finish. Keep the arithmetic in the test |
| **Dispatch table is generated** | `the README.md dispatch table is stale — regenerate it with …` and a red in an unrelated module (one that pins the same table's wording) | regenerate with the repo's own report command (`python scripts/check_dispatch_forms.py report`) and paste the whole table block; a changed input default or description is enough to make it stale |
| **A dispatchable workflow carries the guard** | `neither a guard job nor a guarded step`, `assert 13 == (13 + 1)` | prefer `schedule` alone when a periodic sweep is all you need; otherwise copy the repo's byte-identical owner/collaborator guard job (both actors, `admin|maintain|write`, before any secret) |
| **A header clock matches a LITERAL cron field** | `the header claims 18:37 UTC but no cron in the file starts then (37 */6 * * *)` | the checker compares the claimed hour against the cron's own field, and a step cron has no `18` field to compare — state the cadence in words (`every six hours at :37`) rather than naming a clock time, or write the hours out explicitly when the prose really does name one |
| **Every text file ends with a newline** | `LINT FAIL — files missing a trailing newline` before the unit stage even runs | `make lint-fix` (or the repo's equivalent) as the last step before `git add`; hand-written OpenSpec/proposal/spec/tasks files are the usual offenders |

## Rules

- **The test is the contract, not an obstacle.** Every failure above names the workflow or the variable it
  wants; edit the artefact. Loosening the assertion turns a real boundary into a comment.
- **A behavioural change touches more than the code path.** A new attempt count, a new trigger, a new
  forwarded variable and a new dispatch input each have a document or a table that must move with them, in the
  same commit.
- **Read the red in the module that fails, not in the one you edited.** The dispatch-table and guard contracts
  are asserted from modules named after other features, so "issue-bot manual pick" going red after an edit to
  the fix-bot is the table contract, not a regression in the issue bot.
- **Reproduce inside the CI image.** These are deterministic and run in seconds there; a host run can SKIP the
  module and print a green that means nothing.
