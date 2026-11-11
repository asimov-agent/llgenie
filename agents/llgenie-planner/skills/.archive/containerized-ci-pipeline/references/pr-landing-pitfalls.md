# Landing a change in a bot-owned repo: the pitfalls that cost time

For a repo where every change arrives as a PR that an auto-merge job lands once the
gates are green, a closure guard binds the PR to an issue, and several generated
files (a root index, a README, a data store) are checked against the tree.

## The head branch name decides which issue your PR closes

A closure guard (`scripts/pr_closure.py`) derives the implemented issue from the
branch name: `ci/data-gap-<n>-<slug>` gives the FIRST number, anything else gives the
LAST number. A topic branch that carries a version instead (`pin-flash-1017`) is read
as *"implements #1017"*, and the PR goes red:

```
[pr-closure] REFUSED: pin-flash-1017 implements #1017 — 1 problem(s):
  - the branch implements #1017, but no closing keyword binds to it (found: #447)
```

So: end every branch with `-<issue>` (`fix/<topic>-<n>`) and put exactly ONE
`Closes #<n>` in the body. A second reference after the keyword does not bind —
GitHub links only the first, and the guard refuses the shape.

A branch that is **purely descriptive — no trailing number at all** (`trending-for-your-card`)
implements NOTHING as far as the guard is concerned, so a closing keyword is refused:

```
[pr-closure] REFUSED: trending-for-your-card implements no issue — this PR implements no
  issue, so it must not close one — it closes #349; reference the tracking issue instead
```

Decide the branch name BEFORE cutting the worktree, from the issue you intend to close:
`ci/data-gap-<n>-<slug>` (the implementer convention) or `<type>/<topic>-<n>`. Recovering
afterwards costs a whole PR: rename the branch (`git branch -m`), push it under the new
name, open a second PR, close the first as superseded, delete the old remote branch. Check
it locally in one second before opening anything:

```bash
make pr-closure BRANCH=<branch> BODY_FILE=<body>
```

The inverse bites on a repair PR: if the branch encodes no issue, a body that merely
MENTIONS `close #<n>` in prose counts as a closing claim and is refused. Write
"mark #<n> done" / "refs #<n>" instead, and check the real thing before pushing:

```bash
python3 scripts/pr_closure.py --branch <branch> --body-file <body>
```

Renaming the branch afterwards does **not** work through the API (`PATCH /pulls/<n>`
returned the old `head.ref` twice, accepted, unchanged). Close the PR, push the
correctly named branch, open a new one — the closed PR costs nothing.

## The pre-PR gate set is more than `make test`

Run these in this order and fix what each reports:

1. `make findings-check` — the analysis file (one `## <title>` per finding with
   **Evidence** / **Why** / **Done when**, or the single line `- none`). Each field must
   START a bullet (`- **Evidence:** …`); a bold paragraph is read as a missing field and
   refused, and `- none` is a valid "found nothing".
2. `make openspec-index` then `make openspec-check` — the change must be a tracked
   directory with proposal + capability spec + a fully ticked `tasks.md`, and the
   root index must be regenerated. **Tick the boxes as you verify, then re-run
   `make openspec-index`** — the suite itself fails on any ACTIVE change with an
   unticked box, so a half-ticked change turns `make test` red before your code is
   ever examined (and the case goes green again after the final tick + index).
3. `make lint` — trailing newlines and Python `SyntaxWarning`s.
4. `make architecture-check` — every public make target, workflow and script must be
   DESCRIBED in `ARCHITECTURE.md`.
5. `make secret-scan` — gitleaks over the tree, and it blocks the push.
6. `make test` — the whole deterministic suite, in the test container.

A new `make` target ripples to three places at once: the Makefile, the
`ARCHITECTURE.md` tables, and a seam test that proves the target calls the script.
Miss the doc and `architecture-check` is red; miss the test and the target can be
renamed away silently.

## A workflow test asserts the exact `make` target its step runs

Swapping `make base-check` for `make base-advance` inside a job turned a named
`tests/test_workflows.py` check red. That is the guard doing its job — update the
assertion in the same change, and make the new assertion fail on the OLD workflow
(swap in `git show origin/master:.github/workflows/<f>.yml` and re-run) so the guard
is proved rather than assumed.

## Proving a guard is RED on the old code, cheaply

The repo requires a regression test that fails on the pre-change code. Without a
second checkout:

```bash
cp scripts/x.py /tmp/new.py
git show origin/master:scripts/x.py > scripts/x.py
<run the test module>            # must FAIL, and say why
cp /tmp/new.py scripts/x.py
```

## Environment: a directory named `~/.gitconfig`

If `~/.gitconfig` is a directory (root-owned, an overlay artifact), EVERY git call
dies with `fatal: unknown error occurred while reading the configuration files` —
and `gh` shells out to git, so `gh issue list` fails too, with the message buried
under the git warnings. Workaround without root:

```bash
printf '[user]\n\tname = …\n\temail = …\n[credential "https://github.com"]\n\thelper = "!f() { echo username=x-access-token; echo password=$GH_TOKEN; }; f"\n' \
  > ~/.gitconfig-file
export GIT_CONFIG_GLOBAL=$HOME/.gitconfig-file
export GH_TOKEN="$(gh auth token)"
```

The credential helper reads the token from the ENVIRONMENT, never from a command
line (a token in argv is a leak the repo's own secret-output guard refuses).

## A generated index is NOT merge-safe across same-hour merges

A root index generated from the tree (a change list with a count line) is only ever
verified on a PR's OWN tree. Two PRs that each regenerate it from the same base write
the SAME count line; git merges the table ROWS (different lines) and takes the count
line once — so the base branch ends up with the right rows under a stale count, and
its push CI goes red AFTER both PRs passed their own checks.

- Expected symptom: `index is stale (N on disk)` while every changed row is present
  and the whole diff is the count.
- Repair: run the generator on the freshly merged base (one line), PR it as a repair
  with NO closing keyword — the underlying issue is a guard, not this drift.
- Prevention that actually holds: give every generated artifact a **scheduled keeper** — one job
  that regenerates + verifies + opens a PR ONLY when a file changed, on an HOURLY slot (the slot is
  the convergence time; daily leaves the base red for a day), gating on the diff of EVERY file it
  owns and staging them together, never pushing the base branch. Manual sequencing of merges is not
  a policy a fleet can follow; a keeper needs no human.
- The red lands on the `push` run of the base branch, where the PR repair paths (dispatch-fixbot,
  fix-bot, pr-health) cannot reach — so an unrepaired red push is a *standing* state, not a blip.

## Verify the BASE BRANCH after the merge, not just your PR's checks

An auto-merge gate proves the PR's tree; the merged result can still be red. After
every merge:

```bash
gh run list --workflow=<ci>.yml --limit 3 --json event,headBranch,status,conclusion
```

Wait for the `push` run on the default branch to be `completed/success` before
dispatching anything else (a refresh, another PR) — a red base poisons every PR cut
from it.

## A scheduled run can arrive HOURS late — judge staleness by the artifact

A cron that has not fired yet is not a dropped cron: one was observed arriving ~5
hours after its slot. An alarm that reads `queued`/`in_progress` runs cannot see
either shape (a run that never started has no row; a delayed one looks normal once it
starts). Alarm on the ARTIFACT instead — "the newest committed output is older than N
hours" or "today's slot produced no run by T+H" — and report the measured artifact
timestamp in any staleness claim, not the absence of a run row.

## A long-running job that asserts its base will refuse — and lose the run

A job that checks out the head SHA at trigger time and then runs ~40 minutes is
behind by construction when it finally asserts its base. A strict "refuse unless this
checkout IS the fetched tip" check throws the whole run away AFTER the expensive steps
succeeded.

The shapes to keep apart:

- a job with work **in the tree** (`implement`, `repair`) at the moment it asserts — refusing a
  stale base is correct and must stay strict;
- a job whose tree CARRIES that work and is about to COMMIT — strict refusal is the bug: the base
  it asserted at the start legitimately moved while it worked. It must ADOPT and REBASE: cut or
  attach the branch from the current `HEAD` (reported as `behind_base=N`, refusing nothing), commit,
  then rebase onto the fetched tip, and on conflict ABORT (every commit intact), push anyway and let
  the PR's fix loop repair it. A second `HEAD == tip` assertion here discards the whole run — no
  commit, no push, no PR;
- a job that has **written nothing yet** (its inputs arrive later as artifacts) — it
  must ADVANCE to the fetched tip, and refuse only a dirty tree or a HEAD carrying
  commits the base does not have.

One implementation, two modes (`check`, `advance`), both reached through the Makefile,
with the advance mode proved against real git repositories (behind → moves; fresh →
no-op; dirty → refused and the file survives; diverged → refused).

## Diagnosing "the bots are not doing the work"

A green run is not evidence of work. Check in this order and quote the numbers:

1. **Does the queue hand out work?** Run the shared queue command and read every row:
   `position=-1` with `reason=<a label>` means the item is HELD, not picked. A sweep
   that prints "backlog empty" over N candidates is the alarm, not a clean run.
2. **Can a held item release itself?** If the hold key is a LABEL with no timestamp
   and no ceiling, only a human can clear it — so the bot can park its entire queue
   and keep reporting success. That needs a rule change and a sign-off, not a code
   patch; say so plainly instead of quietly working around it.
3. **Do the open-issue labels match what any bot will take?** Count by label and
   compare with each bot's trigger filter. A backlog that is mostly one label no bot
   accepts grows forever while every run is green.
4. **Did the hand-off run finish its close-out step?** A failing `always()`
   window-close leaves the coordination marker behind, so the next run defers to a
   run that is already dead.
5. **Is the output fresh?** The artifact's own timestamp, not the last run's status.

## A triage bot's verdict needs evidence FROM THE TREE

When a bot may decide `implement` / `refine` / `close` on an issue, two rules keep that
power from becoming a silencer:

- **Judge against the fetched base, not the issue text.** The checkout the bot decided on
  is the base it must re-read (the same `base-check` assertion the implementer already runs):
  grep the file the issue names, run the command it quotes. An issue already fixed upstream
  is CLOSED with that proof, never implemented again.
- **Refuse prose-only evidence.** `close` (and `refine`, which parks an issue just as
  effectively) must carry an `EVIDENCE:` block naming a `path:line`, a checkable path, or a
  `make`/`python3`/`gh` command. Without that gate a lazy close buries a live gap and a lazy
  refine parks one — both reported as a clean run.

And when a queue is filtered to ONE label, count the backlog per label against each bot's
filter: a repo whose analysis files one label and whose findings-file files another starves
whichever label no bot accepts, while the sweep prints "backlog empty" every hour. Reading
several labels as ONE oldest-first queue keeps "one item per run" while letting them compete
on age.

## One writer per branch: do not race a repair bot

A red bot PR may already be owned by an auto-repair run. Pushing to the same branch
while that loop is mid-flight gives two writers, a rejected push, or a fix that silently
loses the other's edits. Before touching a bot PR's branch:

```bash
gh run list --workflow=fix-bot.yml --limit 3 --json databaseId,status,conclusion,createdAt
```

`in_progress` means hands off — let it push, then re-read the PR. If its result is red
twice on the same field, stop expecting the loop to fix it: that is the signal the fix
belongs upstream (in the writer or the ingest gate), filed as its own issue.

If a second run has opened a COMPETING PR on the same generated files, do not try to keep
both: let whichever the pipeline drains first land, then close the other as superseded
with one line saying so. Two open PRs touching one generated store conflict on every
push (already-tracked as its own class) and neither is reviewable.

## An optional make variable forwarded empty kills the target

A public target that forwards an optional setting to its internal recipe as
`VAR="$(VAR)"` passes an EMPTY STRING when the caller did not set it. A script that
does `int(os.environ.get("VAR", "2"))` then raises `invalid literal for int()` on
`""` — and because the failure is in the sweep's entry point, every scheduled run is
red while the workflow looks wired correctly.

Forward only when set:

```make
inner:
	python3 scripts/x.py $(if $(VAR),--var "$(VAR)",)
```

…and give the script a default for the unset case. Treat "empty" as "missing" (`or`
fallbacks, `if not value`), never as a value.

## A protected rulebook file: file the owed wording, never route around the guard

A write to a protected file (the repo's `AGENTS.md`-style rulebook) can be refused by
the environment's approval guard. The refusal is **not** a hint to use another path:
retrying through `terminal`/`execute_code`, or dropping the rule into a code comment
instead, breaks the same contract the guard protects.

The correct move in a repo whose rules make the rulebook part of every change:

1. leave the rulebook untouched;
2. file ONE issue titled `tech-debt: the <section> wording for <behaviour> is owed
   (protected file, approval did not return)` whose body carries the EXACT paragraph to
   paste and the `- **Test:**` names the guard row will cite;
3. say in the PR body which rows are owed and that the change is review-required.

This repo already accumulates such issues — that pattern is the precedent, and a
change that quietly skips the rulebook diff is the drift those issues exist to track.

Two corrections learned later, both cheap to apply:

- **Try the write first.** The approval guard may well return (it did, later in the same repo). An
  owed issue is the fallback for a REFUSED write, not a habit — and a rulebook edit that lands is
  worth more than an issue that says it should.
- **Close the ledger, don't grow it.** These issues are ~70% identical and several are already
  answered by later rules, so triage them against the rulebook before writing anything new: for each,
  grep the section it names, then CLOSE the covered ones quoting the line that covers them and land
  the rest in ONE change. Eight issues describing a rulebook that is *almost* right is worse than the
  missing rows.

## Never invoke the merge yourself — but say what will land
This user's standing rule is that every merge needs their approval, and the agent
never squash-merges, enables auto-merge, or pushes the default branch. In a repo whose
CI has an `auto-merge` job that lands a PR once its gates are green, those two facts
collide: the PR WILL merge without anyone asking. Do not double up on it — never call
`gh pr merge`, never `--admin` — and state plainly in the report that the pipeline's
own gate will land the change on green, so the user can close the PR if they want to
review first. Deliver the reviewable PR plus the run URL; the merge is theirs.

## When the pipeline must be exercised, not just fixed

Fixing the code does not refresh the data. Dispatching the scheduled job is what
proves the fix end to end, but it spends real API credits and can open a PR that
merges — so do it deliberately: dispatch ONCE and let the run's `concurrency` group
queue a second run behind the first (never launch a parallel one), then report the run
URL so the user can watch it.
