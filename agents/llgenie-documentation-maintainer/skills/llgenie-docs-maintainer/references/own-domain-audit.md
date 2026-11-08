# Own-domain audit — the empty-queue bounded sweep

Versioned behaviour (owner #1245 contract). When the reactive queue is empty for **N=2 consecutive
passes** and no in-flight gate is owned, run ONE bounded own-domain audit. Never overrides reactive
work. One pass, no loop. Clean → record `re-audited at <sha>, no findings`; finding → a refined
six-section issue tagged `agent:implement`, routed through the queue, **never implemented by the same
pass**.

My three checks: main-vs-docs alignment, skill freshness, change-note coverage (#1123).

## Measure in a pure-tip worktree, never your own branch checkout

**Every measurement runs in a scratch worktree cut at the freshly fetched tip sha, not in the branch
worktree you are already sitting in.** A branch worktree's `HEAD` is your PR's base commit; its
`docs/changes.d/`, `CHANGES.md` and file counts belong to that branch, not to `main`. Measuring them
there gives a confident, wrong census. Fix:

    git worktree add --detach /tmp/adm-audit <tip-sha>
    cd /tmp/adm-audit && <run the checks below>
    cd - && git worktree remove /tmp/adm-audit

Remove the scratch worktree when done (it is yours, not a fleet vehicle); never remove another lane's.

**Removing a worktree your shell was `cd`'d into bricks the shell's persisted cwd.** The next
`terminal` call starts in the deleted path and dies with `cd: /tmp/<wt>: No such file or directory`
before any command runs — it looks like the command failed, not the cwd. Either leave the scratch
worktree until the session ends (cheap), or, after removing it, pass an explicit `workdir` on every
later `terminal` call and use `git -C <repo> …` instead of a `cd` prefix. Never rely on the
auto-persisted cwd surviving a worktree removal.

## Check 1 — main vs docs alignment

Pick the sentence the dispatch names and **read the code path it describes, not just a grep of the
doc.** A doc sentence "X is a later change" is true iff the code does **not** do X: a picker that
*consumes* pre-measured `engines[].tps` from the registry is not a picker that *measures* t/s, so
"measuring in the picker is a later change" still holds. Check each concrete claim against the tree:
where a decision lives (`detect_server.py` tree/backend vs `model_engine_pick.py` gates), the
ordering rule ("measured on this card, else not a claim"), and any threshold constant. Aligned = cite
the file:line that keeps the sentence true; drifted = issue naming the drift sha and what the doc
should say.

## Check 2 — skill freshness

Enumerate every skill, then read `version:` frontmatter against the release ledger. **The glob
trap:** `git ls-tree -r --name-only <tip> | grep 'skills/SKILL.md'` returns nothing — real paths are
`agents/<profile>/skills/<name>/SKILL.md`, `.hermes/skills/<name>/SKILL.md`, and
`skills/engines/<ns>/SKILL.md`. Match `SKILL\.md$` (and `SOUL\.md$`) instead. A flat `v1.0.0` is
normal for most lanes; "2+ releases stale" is a behavioural reading — read the one skill in the
domain of the newest behavioural merge (e.g. the Prism skill after a Prism-only gate lands) to judge
drift, not the version number alone.

## Check 3 — change-note coverage (#1123)

For each recent merge that touched a notified surface (`docs/**`, `scripts/`, workflows, Makefile
targets, `agents/**`), confirm its full trio exists **at the tip**. **Enumerate the real fragment
names — do not guess the slug from the PR title.** Fragment filenames are `<date>-<their-slug>-<issue>.md`
and the slug is authored, not derived from the title, so `grep '<title-derived-stem>'` returns nothing
for a fragment that exists and you read a false MISSING:

    git ls-tree -r --name-only <tip> docs/changes.d/ | grep -- '-<issue>\.md$'   # locate by IS issue number
    git ls-tree -r --name-only <tip> agent-wiki/          | grep -- '-<issue>\b'   # note
    git show <tip>:CHANGES.md                              | grep -- '-<issue>'      # indexed row

Matching on the trailing issue number is stable across slug renames; matching on a remembered stem is
not. **The gate is the source of truth, a guessed stem is not:** run `python3 scripts/check_docs.py
check` at the tip and expect rc=0 with a `fragments == notes` count in its summary (`[changes-index]
ok: <N> fragment(s) index every agent-wiki/ note`). If your per-merge grep says MISSING but the gate
is green, the **grep was wrong** — you guessed a slug, you did not find a gap. Never file a
change-note finding off a stem you invented; a real gap makes the gate itself red.

## Deliverable and the missing tracker

**The six-section gate wants exactly its six headings — a seventh `##` reds it.** A body with the
required sections plus an extra `## Root cause` / `## Why this recurs` reports missing sections and you
lose a round-trip guessing. Fold supporting argument into the allowed section as a **bold lead-in** on a
paragraph instead:

    ## Problem
    …statement…
    **Root cause.** …paragraph…          # not: ## Root cause

Verify before filing with the repo's own parser, on the body you are about to send:

    python3 -c "import sys; sys.path.insert(0,'scripts'); import issue_body; \
      print(issue_body.missing(open('<bodyfile>').read()) or 'none')"

The clean-audit record needs a durable home. **If an open docs-lane tracking issue exists, post the
record there as a comment** — measured-at sha, each check's gate rc, and the four-AC-box read. If no
**open** docs-lane tracking issue exists (past audit issues are often already CLOSED), say so in the
report and send the `re-audited at <sha> no findings` to `@llgenie-planner` rather than fabricating a
tracker. If the planner DM is refused (`queue_full`, `do not resend`), do **not** resend — the
durable on-issue comment is the fleet's source of truth; a transport refusal is not a missing report.

**A clean audit owes no PR — even when the dispatch body carries PR-template boilerplate.** A
dispatch may spell out branch names, `AGENTS:`/`BASE:` lines and "ready-for-review PR, never draft";
that template is for audits that surface a fixable finding. When all three checks are green and no
`scripts/`/`tests/`/workflows change arose, opening a PR with no diff is inventing work — the clean
result is the record (above), not a vehicle. Say `no PR owed: a clean audit records rather than
invents tree work` and arm nothing (`auto=none`, #1088).

## Posting the record: exit code is not proof, and the sha must be greppable

Two write-side traps cost a duplicate record and a false "missing" read this class:

- **`gh issue comment` can exit nonzero AND still have posted.** The exit code is not the fact; a
  retry after a nonzero exit produces a **duplicate** record on the tracker. Before re-posting, read
  the wire back and only post if the record is absent:

      gh api repos/<owner>/<repo>/issues/<n>/comments \
        --jq '[.[] | select(.body|contains("re-audited at <sha>"))] | length'   # 0 -> safe to post

  If you did create a duplicate, delete the extra one with the comments API — **`gh api` uses
  `-X DELETE --silent` (and `-i` for the status line), NOT curl's `-w`**, which gh rejects as an
  unknown flag:

      gh api repos/<owner>/<repo>/issues/comments/<id> -X DELETE --silent -i   # expect HTTP/2 204

- **Keep the canonical clean line literal so a grep matches it.** Write the line as
  `re-audited at <bare-sha>, no findings` with the sha **bare** — do **not** backtick or bold-wrap the
  sha inside that token. A verification `grep 're-audited at <sha>'` (or an API `contains(...)`
  check) matches the literal string; `re-audited at \`<sha>\`` silently does not, and your own
  read-back then reports the record "missing" while it sits visibly on the wire. Verify with a
  backtick-tolerant pattern if the sha is already wrapped, but prefer writing it bare.

A clean audit's only required mutation is the durable on-wire record. **Verify it landed by reading
it back, then stop** — do not re-post, open an empty PR, or invent a finding to satisfy a completion
guard; a fabricated issue to clear a guard is worse than a guard left unanswered.

## Skill-freshness is not an invented per-skill release count

`CHANGES.md` keeps no per-skill release sequence — versions appear sporadically and most skills sit
at a freshly-folded `1.0.0` — so a `version:` frontmatter cannot be "2+ releases behind" anything, and
digging for a release ledger that does not exist wastes the pass. Measure the dimension the only way
it is real: `cmp` each lane skill's tree copy against its live `~/.hermes/profiles/<p>/skills/**` (the
standing live-vs-tree drift class, #791), and treat a live-ahead file — live newer/larger than the
tree, e.g. the lane's own `SKILL.md` one version past the tree — as the finding, routed under that
standing drift umbrella rather than filed as a new one-off. A skill with no live counterpart and no
tree change since its last note is fresh; say so and move on.

## A SKIPPED comparison is not a clean result

Two readings look identical to "no findings" and are neither. Check both before writing a count.

- **The live-vs-tree comparison can silently skip.** `check_agent_profiles.py` prints an explicit
  `SKIPPED … the LIVE RULEBOOKS were NOT compared` line when it cannot resolve a live profile home —
  the runner has none, so **CI is structurally blind to this dimension** and a bare `make
  check-agent-profiles` on a host without the env var can report zero findings while hundreds exist.
  Measure with the home named explicitly and read the class names, not just the exit code:

      HERMES_PROFILES_HOME="$HOME/.hermes/profiles" python3 scripts/check_agent_profiles.py check
      # count live-longer / live-lines-missing / live-edited-not-tree / absent-from-tree separately

  Never quote "N findings" from a run whose output contains `SKIPPED` or `NOT compared`.

- **An audit run against a RED gate cannot report clean.** If the gate that would catch the finding is
  itself failing on `main`, "green in CI" and "0 gaps" both describe an instrument that was off. Reproduce
  the docs gate on a clean detached base worktree FIRST; if it reds there, the audit's headline is that
  fact (with the issue filed), not a clean pass — see `references/gate-red-triage.md`.

A count stated without the command that produced it and the sha it was measured at is not a measurement,
and a second wrong count on the same tracker costs more trust than the finding was worth. Correct an
earlier record with an explicit supersede comment naming what the earlier measure got wrong.

## Fleet-wide drift snapshot: ONE routed issue, not one per file

When the live-vs-tree dimension surfaces many lanes' files at one sha (the `live-longer` /
`live-lines-missing` / `live-edited-not-tree` set under #791) and no existing issue names *that
measured snapshot*, the deliverable is a single six-section issue carrying a per-file table (tree
bytes, live bytes, live mtime, class) that routes each file to its owning lane — never one issue per
file (a dozen queue entries nobody can close together) and never a fold performed here (this lane does
not implement; each lane owns its #791/#1060 vehicle). For a *single* already-tracked file, comment on
the umbrella instead of opening a new one-off. Name the smallest in-queue unit in the body so the
issue has an entry point.

## A CLOSED issue + a MERGED fix is not an OpenSpec-green change

The change-object can survive both with unchecked task boxes, redding `openspec-tasks-check` on every
PR. Re-measure `make ci-openspec` at the true tip and read the change's OWN `tasks.md`, not the
issue's closure or the fix PR's file list. A triage relay can report "#N CLOSED COMPLETED, its fix #M
MERGED" while `openspec/changes/<name>/tasks.md` still carries `- [ ]` boxes — the fix PR touched
only classification gates and docs/tests, never the change's acceptance list, so `make ci-openspec`
exits rc=2 (`openspec-tasks FAIL <name>: unchecked task checkbox(es) at lines […]`) on every balanced
PR, and the residual has NO live owner issue. File it as its own six-section issue with the
current-head measurement and two allowed resolutions: complete the named tasks + archive out of the
ACTIVE set, or record an explicit supersession-by-<fix-PR> + archive — either must make `ci-openspec`
rc=0 at its merged head. This lane reports and routes; it does not implement the code task.

## A fold that just closed is not proof drift reached zero

Re-measure the fold's own target file against the current live mtime, and check whether the closing
issue even named it. A lane can merge a fold for `file A` and close its tracker while `A` was edited
again in the live profile *after* the fold's snapshot. The gate's `live-edited-not-tree` line carries
both timestamps (live edit vs tree commit): compare `git show <fold-merge-sha>:<A> | wc -c` with the
live file's size and mtime — if live post-dates the fold, the fold is stale by its own acceptance;
and if the closed issue never named `A`, "closed" reads as tracked-to-zero while the file still
drifts. Report it as continuing drift since the fold sha, with fresh live size and mtime.
