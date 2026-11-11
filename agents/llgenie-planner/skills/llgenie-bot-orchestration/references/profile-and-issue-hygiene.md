# Profile integrity and issue-filing hygiene (planner's own housekeeping)

Two housekeeping duties that cost real cycles when skipped: keeping the planner profile patchable and
versioned, and filing an issue that is new, well-formed and correctly routed.

## Profile boundary — whose files are yours

You own **`llgenie-planner`** and nothing else. Resuming/pausing cron jobs, editing skills, or rewriting
memory in another lane's profile is out of bounds unless the owner explicitly says so — even when the
change looks like an obvious fix for a stalled lane.

Why: those profiles carry another lane's standing rules, and a well-meant edit silently changes the
behaviour a credential-holding bot runs under. The symptom is not an error; it is a lane that starts
behaving differently with no trail.

What to do instead: dispatch the lane (`message_agent` + durable on-issue anchor), and if its *own*
scheduler is broken, say so on-record with the evidence and let its owner fix it. Report, do not touch.

## Skill size: the 100,000-character write limit

`skill_manage` refuses any `SKILL.md` at or over 100,000 chars, and the refusal **rolls back the whole
batch** — so one oversized body silently blocks every pointer, patch and lesson you try to add.

Symptoms that mean "the body is too big", not "the tool is broken":

```
SKILL.md content is 103,547 characters (limit: 100,000) — batch aborted, all touched skills rolled back
```

Fix, in this order:

1. Measure before patching: `wc -c SKILL.md`, and note the headroom.
2. Find the largest sections and move the biggest purely-topical one into `references/<topic>.md`.
3. Replace it inline with a short summary **plus a pointer** to the new file, so nothing is orphaned.
4. Re-measure. Confirm each new `references/` file is both present on disk and linked from the body.

A `references/` file nothing links to is indistinguishable from one never written — always wire the
pointer in the same operation.

## Tree vs live: which copy is authoritative

A profile's skills exist twice: the **live** copy that actually runs
(`~/.hermes/profiles/<p>/skills/...`) and the **tree** copy under `agents/<p>/` that is versioned and
reviewable. They drift.

Rules:

- **Measure drift read-only first.** `make sync-agent-profile PROFILE=<p> CHECK=1` (and
  `make tester-fold-live PROFILE=<p>` with **no COPY**) print per-file diffs, byte counts and the
direction of each difference. Never `COPY=1` or `FORCE=1` on a profile you have not read.
- **Sync is one-way, tree → live.** It can therefore *overwrite live behaviour with a stale tree copy*.
  When the tree copy is the truncated one (normal drift), a sync destroys the live version. Read the
  direction in `CHECK=1`'s output before syncing anything.
- **A tree copy larger than live is a genuine fresh-work candidate; a tree copy smaller than live is a
  truncation trap.** Never blanket-sync a profile whose files differ in both directions.
- **Only sync a file whose live lines are a subset of the tree's.** Prove it: compare the non-blank line
  sets and confirm every live line appears in the tree (reflowed paragraphs fail a literal line check, so
  also probe the rule as keywords — the sentence can be re-wrapped without the rule being lost).
- Keep a timestamped backup of any file you replace, and record the sha256 of both sides afterwards.
- **Never edit your own SOUL/skills privately.** A behaviour change arrives as an issue + PR under
  `agents/<profile>/`; then you sync from the repository. The tree copy being over-limit or stale is
  itself an issue to file — not a licence for a private edit.

## Do not run a destructive sync to "fix" drift

The tempting move when live and tree disagree is `make sync-agent-profile` (or a `COPY=1` fold). Both
overwrite. Before either: measure direction, prove the subset, and check whether a *different* lane's
files are in the same diff — those are never yours to overwrite.

## Filing a new issue: check, validate, then create

1. **Search for an existing tracker before writing a new one.** A red gate is usually already filed, or
already has an open fix PR. `gh issue list --search "<class keywords>"` and
   `gh pr list --all --search "<n>"`. Filings for one class multiply (near-identical reactor issues for
a single broken gate). If a tracker exists, comment the root cause onto it instead of opening a sibling.
2. **Check whether the fix already exists and is merely blocked.** Before filing "X is broken", confirm
   `state`, `mergeStateStatus` and `autoMergeRequest` of a suspected fix PR. A red failure whose fix is
   already open, armed and proven needs a push, not a new issue.
3. **Write the six sections in order**: Problem, Why it matters, How we fix it, Benefit, Acceptance
   criteria, and — when present — Not covered, with **Technical strictly last**. Getting the order wrong
   is rejected by the repo's own checker.
4. **Validate locally before `gh issue create`.** Load the repo's `scripts/issue_body.py` and call
   `missing(body)`, `headings(body)` and count the `- [ ]` boxes in the Acceptance criteria section. An
   empty `missing` list plus Technical last is the gate's own test; do not eyeball it.
5. **Count boxes with `grep -cE '^- \[ \]'`, not `jq scan`.** A multiline regex probe silently returns 0
   and will make a perfectly good body look empty. When a count disagrees with the file, trust the
   line-oriented grep.
6. **Each acceptance criterion must be provable at a head.** State the measurement, not an intention —
   and where a criterion is circular (a PR cannot be green until its own issue is ticked), say so in the
   body and name the out-of-scope path rather than pretending it is checkable.
7. **Route it to the owning lane's label**, and name that lane in the body. A pipeline/gate/script defect
   belongs to the ci-pipelines lane; product code to the implementer; docs to documentation-maintainer.
