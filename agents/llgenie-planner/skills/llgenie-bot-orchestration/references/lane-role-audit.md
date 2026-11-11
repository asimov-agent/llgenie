# Lane-role audit: verify each bot's SOUL/skill actually encodes its role behavior

## When to run
An explicitly requested fleet-integrity check ("are there gaps between the lanes? make sure each bot's role behavior is in place"), a periodic maintenance pass, or before dispatching a burst of unrelated issues (a lane with no encoded audit/role duties cannot be trusted to self-maintain).

## Measure BOTH: the tree is the versioned truth, the live profile is what the lane obeys

Two axes, both required, not either-or:

- **The tree** (`origin/main` → `agents/<lane>/`) is the reviewable source of truth (#791, #919). Audit what ships there.
- **The live profile** (`$HOME/.hermes/profiles/<lane>/`) is the copy the lane *actually runs*: a lane can match the tree byte-for-byte and still be missing a materialised skill to load, or carry a drifted SOUL. The owner's directive is explicit — verify the live `$HOME` SOUL **and** skills setup, not only the tree. Tree-pristine is not proof-of-behaviour.

On each axis use SET-subset, never equality on a prose list (an exact list reds on the next legit addition).

## Verifying the live `$HOME` setup (behaviour, not file-drift)

Build the profile root from `pathlib.Path.home()` — `PROFILES = pathlib.Path.home() / ".hermes" / "profiles"` — **never** a hardcoded `/home/<user>` (owner rule #2145). Gate it: `grep -nE '/home/[a-z_]+' <script>` must find nothing. When reporting a path, rewrite the resolved home to `$HOME/...` so a failure message never encodes one machine's account name.

Per live lane, assert:
1. **SOUL contract elements** exist (report-line `BOT <lane> · working on #<id>`, never-merge, bookend, versioned-edit under `agents/<profile>/`, own-duty, a communication commitment).
2. **`skills-materialised`**: at least one non-archived `SKILL.md` exists under `skills/`. Use `rglob` and skip any path containing `.archive` — a flat glob misses lane skills that live in a category subdir (false `NO`), and a `skills/` holding only `.archive` stubs passes file-drift but has nothing live to load (a real gap).

**Prove it is not a rubber stamp — negative controls must fail (rc=1):** empty SOUL, SOUL with every file-matching element but no report line, SOUL that reports to nobody, and a lane whose `skills/` holds only `.archive` stubs. A checker that passes all four is a rubber stamp; record the four rc=1 results alongside the `N/13 pass` line.

The per-lane duty map and the six contract elements are the checker's data, not its logic — keep them in the script (versioned under `agents/<profile>/`), so a rebuild cannot lose them and review can see them.

## Steps
1. **Enumerate lanes.** `git ls-tree --name-only origin/main agents/ | grep '^agents/llgenie-'` — the roster under `agents/`.
2. **Presence gate (tree axis).** Per lane: does `agents/<lane>/SOUL.md` exist AND does it ship at least one `skills/<name>/SKILL.md`? A lane with no SOUL or no skill has nothing diffable/reviewable for its own behavior. Then re-run the same presence+contract check on the LIVE `$HOME/.hermes/profiles/<lane>/` (see "Verifying the live `$HOME` setup" above) — the tree gate alone does not prove the lane can load and obey it.
3. **Role split.** Read `agents/manifest.json` `profiles[].rules` (never-implement / never-merge / etc.) and each SOUL's one-line mission. Overlap = two lanes claiming the same verb with no cross-reference deferring the other way; gap = a responsibility stated nowhere. A healthy boundary is cross-referenced: "X is `lane-b`'s job, never mine" (e.g. BA defers priority/scope/acceptance to PM; PM defers duplicate re-triage to the planner).
4. **Idle-audit encoding (the recurring gap).** The owner 2026-11-01 contract requires EVERY operational lane (security, documentation-maintainer, ci-pipelines-maintainer, engine-improver, reviewer, rebase-conflicts) to encode, in ITS OWN SOUL/skill, the empty-queue → own-domain continuous-improvement audit with named domains + the `re-audited at <sha>, no findings` clean record. Measure: `git show origin/main:agents/<lane>/SOUL.md | grep -icE 'empty queue|own-domain|audit|continuous|idle|pin validity|serving drift|review-process'`. A lane scoring 0 is a filing opportunity even if the planner's own SOUL carries the full block — the planner dispatching is not the lane obeying.
5. **File one refined six-section issue PER gap**, labeled `continuous-improvement` + `agent:refined`, body naming: the measured grep hit-count and sha, why it matters (a quiet lane indistinguishable from idle), the exact fix surface (`agents/<lane>/SOUL.md` + the relevant skill reference), and acceptance criteria (`make check-docs` + `make lint` green, change-note + fragment per #1123, PR authored by the OWNING lane closing the issue).
6. **Route to the owning lane** — on-issue dispatch anchor (comment naming owner + scope) AND a `message_agent` to that lane. The lane updates its OWN SOUL/skill and authors the PR (#791); the planner never edits a peer lane's files (never-implement). One vehicle per issue (#824).

## State the evidence, not the claim
Quote the grep command, the hit count, and the measured sha alongside each gap. `gh issue view <n> --json state,labels` to confirm the filed issue is OPEN with the two labels and no existing vehicle before dispatch (vehicle-detection-before-dispatch).

## Pitfalls
- Do not file a gap on a lane that genuinely has no operational domain (the planner forcing itself onto an audit it already runs is drift, not a finding).
- Do not couple multiple lanes' gaps into one issue — each lane authors its own PR, so one issue per lane keeps the vehicle set clean.
- Do not "implement" the gap yourself as the planner — that is exactly the peer-lane edit every lane rule forbids; dispatch it.
- When the completion-integrity check demands a "changed path", the coordinator's deliverable is GitHub REST state (issues + anchors) plus the reference file written to the planner's own skill — a scratch file plus a tree-commit is the durable trail, not a fabricated repo-dir PR.
- A verifier that grounds on the live profile must not false-`NO` on a lane whose skill lives in a category subdir (use `rglob`), nor false-`PASS` a lane with only `.archive` stubs (skip `.archive`). Both are the same root cause: the search scope is wrong, not the lane.
