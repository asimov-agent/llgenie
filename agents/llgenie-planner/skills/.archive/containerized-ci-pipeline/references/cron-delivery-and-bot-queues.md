# Scheduled bots: delivery, queues and verdicts

Depth for repos whose work is driven by hourly/daily `schedule:` workflows (a sweep bot, a
reviewer bot, a refresh bot). Each section is a rule plus the command that proves it.

## 1. Never trust a cron — measure what was DELIVERED

A `cron: "19 * * * *"` in the YAML is an intention. GitHub drops and delays scheduled runs:
repos routinely measured at **3–6 h between deliveries for an hourly cron (~5 of 24 slots a
day)**, with the odd `failure` in the same set. Before believing any "the bot runs hourly" claim,
read the artifact:

```bash
gh run list --workflow=<bot>.yml --event schedule --limit 20 \
  --json createdAt,status,conclusion | jq -r '.[]|"\(.createdAt) \(.status)/\(.conclusion)"'
```

Compute the gaps in code, not by eye. Filter `--event schedule` on purpose: a
`workflow_dispatch` or an `issues:`-event run proves the pipeline can START, not that the cron
was DELIVERED.

## 2. A dropped cron is invisible to a stuck-run alarm

A queued-run alarm lists runs that EXIST (`queued` / `in_progress`). A slot GitHub never created
has no run, so it alarms nothing while the queue drains at a fraction of the intended rate. The
missing-run alarm must read the ARTIFACT (newest delivery of that workflow) and:

- fail (exit 1) when `now - newest.createdAt > MAX_AGE_HOURS` (default ~3 for an hourly bot),
- print the age, how many `:MM` slots were missed since it, the gaps between deliveries it can
  see, and the LAST conclusion (so "red on every run" is not mistaken for health),
- treat "no schedule run at all" as its own verdict, never a pass,
- exit 2 when the API read fails — a monitor that cannot read must never report green,
- stay read-only (no comment, no dispatch) unless the repo's convention says otherwise.

Put the decision in a pure function (`stale(rows, now, max_age) -> dict | None`) so the fixture
is the real recorded sequence, not a hand-wave. Wire it as a `make` target called by a
already-cadenced "something is stuck" workflow, not by a new pipeline.

## 3. Backup slot beats a single cron

Add a SECOND cron off the hour the first uses (`19` + `49`). It is nearly free when the job has
an idempotent no-op path and a per-entity `concurrency:` group (`concurrency: bot-<entity>`), and
it buys coverage against a single drop. Do not add a second slot to a job that takes irreversible
action per run.

## 4. "One item per run" queue semantics

- The head of ONE order is taken (`position=0`); everything else is context. Never let a run
  take "all candidates".
- Multi-label queues: `gh issue list --label a --label b` is an **AND**, so a queue over several
  labels needs one query per label, unioned **by item number** and sorted by `createdAt` — the
  labels then compete on age, and the double-return a stub produces is exactly the dedupe case.
- An item already in flight is dropped from the queue ENTIRELY (not listed as "held"): a branch
  matching the implementer prefix, or an OPEN PR from such a branch, means `has_implementer`.
- The branch prefix is usually label-agnostic (`ci/data-gap-<n>-<slug>` for every issue).
  Detection keeps working, but RENAMING it needs the closure matcher updated in the same change
  (`pr_closure`-style `^ci/data-gap-<n>-`): a renamed branch with no matching matcher makes every
  implementer PR fail the "closes the issue it implements" check.
- Two runs must never work one item: a per-item concurrency group keyed by the item number, on
  every entry path (event AND schedule).
- Leave a separate consumer's default alone: a reviewer bot that rewrites bodies should not
  silently start working the newly added label.

## 5. A bot's verdict needs tree evidence, not prose

When a bot decides implement / refine / close from an issue, make it re-read the item against the
checkout it just fetched, and gate the verdict deterministically: an `EVIDENCE:` block that names
no `path:line`, checkable path, or `make` / `python3` / `gh` command is REFUSED (exit 2), for
**both** close and refine. Otherwise a lazy close buries a live gap and a lazy refine parks work.

## 6. Prove the decision with a mock item through the REAL script

A prompt alone is untested. Build a fixture per verdict and drive the real script with only the
external system stubbed (a `gh` on `PATH`):

- one mock item per outcome (implement → nothing applied; refine → ONE restatement + the
  refine label, never closed; close → closed + the closed label),
- the refusal cases (prose evidence, missing evidence, unknown verdict),
- the queue side (both labels queried, each item once, exactly one head).

Never monkeypatch the decision function itself — that is the contract talking to itself and it
stays green when the function is deleted.

## 7. File the issue BEFORE naming the branch

Numbering is not predictable: `gh issue create` returns a number that is often one off the one
you expected (another create or a PR consumed it). Read the number from the returned URL, THEN
create the branch so it ends `-<that number>`, and only then write/commit. A branch named from a
guess either closes the wrong issue or fails the closure check later, and the rename means fixing
findings/proposal text too.

## 8. Assert the base ONCE, at the start — never again once the tree has work

A job that cuts a branch asserts `HEAD == fetched origin/<base>` before it starts, because a fresh
CI checkout being the tip is an accident of the runner. That assertion is correct **only while the
tree carries no work**. A bot run then spends 20–30 minutes implementing while the merge bot keeps
landing PRs, so a SECOND assertion either

- at **commit time** refuses a finished implementation —
  `REFUSED: STALE: this checkout is NOT the freshly fetched origin/master … make: *** Error 1`
  → no commit, no push, no PR, no artifact: the whole run discarded after the work was done; or
- at a fan-in job's **aggregate step**, discards every green upstream leg.

Three shapes, one target each:

| the tree… | the right target |
|---|---|
| carries no work (the job wrote nothing) | **advance**: fetch + fast-forward a CLEAN checkout instead of refusing |
| carries the work (agent edits in flight) | **adopt** the branch at commit time from the current `HEAD`, report `behind_base=N`, then **rebase** after the commit |
| is a worktree the caller owns | cut from `refs/remotes/origin/<base>`, never the local base branch |

`adopt` attaches an existing branch (a re-run) instead of re-cutting it, and never discards the
uncommitted tree. After the commit, rebase onto the fetched tip: on conflict `git rebase --abort`,
print `rebase=conflict` **plus the conflicted paths**, keep every commit, and exit a DISTINCT code
(e.g. 3) that the caller treats as "push anyway" — the PR carries the conflict and the fix loop
repairs it. Label a non-conflict failure `rebase=failed`, not `conflict`, or the log lies about the
cause.

`git rebase` re-applies commits and therefore needs a committer identity; a bare container has none
(`fatal: unable to auto-detect email address`). Pass `-c user.name=… -c user.email=…` **only when
the repo has no `user.email`**, print `identity=fallback`, and take the pair from the repo's ONE
canonical identity definition rather than inventing one.

## 9. "Nothing was implemented" is not always a failure

A run's most expensive path ends in `verdict=implement` with zero file changes, and that signature
has two meanings with opposite outcomes:

- **the agent failed** (dead key, burned token budget, detached run) → RED, loudly;
- **somebody else already did it** — a PR merged and CLOSED the picked issue while the run was
  working → GREEN, with ONE marker-deduplicated comment on the item.

So the final step asks the item's state FIRST, through one seam with explicit exit codes:
`0 = open` (keep the red), `4 = closed` (green + comment), `2 = unreadable` (**keep the red** — a
state you cannot read is never evidence; never collapse 2 into 4). Read that state with one
`gh issue view <n> --json state` call, never from the run's own verdict file.

## 10. A rejected push must always leave an artifact

Gate the patch-artifact upload on "the push did not succeed", never on one specific rejection
reason (e.g. the workflow-scope refusal): any other rejection — protected branch, token, a race —
then loses tens of minutes of agent work on an ephemeral runner. Write the patch and the
`pushed=false` output on every non-zero push, and upload when `pushed != 'true'`.

## 11. Editing the rulebook is part of the change — attempt it, don't pre-defer

A protected rulebook (`AGENTS.md`) write can be refused by an approval gate (silence is not
consent) — and it can also be granted, sometimes later in the same session. Attempt the rulebook
diff in the same branch; only if it is actually refused, file the owed rows as their own issue
**quoting the exact intended wording**. Do not write "owed" into `findings.md` before trying: the
prose then sits out of date the moment the rows land.

### The owed-row BACKLOG: verify each against the file, land the survivors as ONE change

A repo that refuses unprotected rulebook writes accumulates one issue per refusal, and those issues
rot: measured, eight open owed-row issues with bodies ~70% identical, two of them already satisfied
by later rules that nobody re-read. Treat the backlog as a triage task, not a to-do list:

1. Pull every owed body (`gh issue view <n> --json body`) and extract the EXACT text each wants.
2. Grep the CURRENT rulebook for the substance of each — not its title's phrasing: the rule or row
   is often present under a later rule, and "§8 row for X" may exist while "§2 rule for X" does not
   (close that issue only for the half that landed, or keep it for the half that did not).
3. Land the genuinely missing rows in ONE branch, each with the wording its own issue recorded, and
   bind every issue with its own `Closes #<n>` line. `pr-closure`-style guards accept several
   keywords as long as each binds one reference; a chained `Closes #a and #b` binds only `#a`.
4. Leave open the issue whose own body does not name its target (which §, which row, which test).
   A guessed row is worse than a missing one, and say so in the PR rather than silently skipping.
5. The rule's own id may be the deliverable: adding a new hard rule needs the next free id and a
   test that citations resolve (`rule <id>` cited anywhere must be declared), so re-read the id
   space before choosing one instead of assuming +­1.

## 12. A green bot run that opens no PR is usually a correct NO-OP — read the STEP, not the run

"Why is the architecture/description bot not creating a PR?" almost never means the bot is broken.
A "publish only when the artefact changed" gate (a generated inventory block, an index, a docs
sync) skips its commit/push/PR step whenever the regenerated artefact is byte-identical, and the
run still finishes `completed/success`. Diagnose in this order:

```bash
gh run view <run> --json jobs \
  --jq '.jobs[]|{name,conclusion,steps:[.steps[]|select(.conclusion!="success")|{n:.name,c:.conclusion}]}'
```

- A **`skipped`** commit/push/PR step next to green regenerate+verify steps is the gate working, not
  a failure. A `failure` anywhere above it is the real defect.
- Read the gate's own log line (`already matches the tree - nothing to open`) — it is the bot
  stating its decision, and it is the cheapest evidence you will get.
- Then prove it yourself, do not take the log's word: cut a throwaway worktree from the fetched tip,
  run the generator, and read `git status --porcelain`. A clean tree confirms the no-op; a dirty
  tree means the gate is comparing the wrong thing (a stale checkout, a pre-regeneration `diff`).
- Remove the probe worktree and its throwaway branch when done; it must never reach the remote.
- If the artefact is instead regenerated on every change by the normal pipeline, expect the daily
  bot to be a permanent no-op — that is the design, and "it has never opened a PR" is not evidence
  of a defect. Say which it is (backstop vs broken) rather than reporting "green".
