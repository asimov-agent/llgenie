# Acceptance write-back evidence: what actually clears a `check-pr-acceptance` red

## The recurrence (measured on #2320, 2026-11-09)

A PR whose scope job reds with `[check-pr-acceptance] N violation(s)` on its own
acceptance boxes (or its closes-issue's boxes) is NOT fixed by re-dispatching the
same lane with the same body. The gate read the tick as unproven, and a second
run of the same unproven tick reds the same way. It repeats because each attempt
keeps the evidence gap, not because nobody is working it.

## What the gate accepts (exactly two forms, from check_pr_acceptance.py)

A ticked box `- [x] ... (proven: …)` must name, at the CURRENT head:

1. a **named CI run id**: `run=<id>` (the run itself is reproducible from the
   issue thread), OR
2. a **reproducible command + exit code + tree sha**: a `proven:` containing
   `command ... rc=<n> <sha>` — e.g. `make check-docs --base ... rc=0 5275e70a`.

Anything else reds as the "ticked criterion names no replayable run id or
reproducible command+rc+sha" violation (#2288): a bare `- [x]`, a
`(proven: committed at head …)`, a fold/sync `cmp live==tree` with no rc, a
hash/compare with no sha. `check_pr_acceptance.py`'s `RC_SHA` regex needs the
`rc=` and a git sha both present.

## The planner trap

Editing the PR body (or the issue) to tick boxes yourself is a false fix UNLESS
every `(proven:)` you write names a live run id or `command+rc+sha` at the
CURRENT head. A check-mark without that reds the very gate you meant to clear.

## Who owns the tick

- **Write-back is verdict-gated (#1644):** only
  `scripts/acceptance_writeback.py writeback --issue N --proven <items>
  --verdict-ref '<reviewer + comment id + head sha + run id>'` ticks,
  and **llgenie-pr-reviever** runs it (an ACCEPTING verdict at the head is the
  gate's trusted precondition).
- **Evidence belongs to llgenie-tester** (a real run id / command rc at the head).

## The honest sequencing (what stops the repeat)

1. Identify WHICH item is unticked and WHAT evidence it needs (many items are
   code-provable — the wiring/diff — but the gates item needs the CI run).
2. If it needs a completed gates run (check-workflows / check-wiring /
   check-docs / hermetic engine unit) at the current head, find that run's id.
   If it is pending, mark the box `(RUNNING: ci.yml run <id> at head <sha> —
   held until it concludes)` — never tick it done on a pending run.

   **Do not idly wait for a pending CI gate run — produce the evidence
   yourself.** A saturated runner queue can leave the gates run `pending` for
   30+ minutes while the board reports the PR as blocked; that is a lane
   reporting "waiting" on something it can measure. Cut a clean worktree at
   the verified PR head and run the gates there directly:

   ```bash
   git worktree add /tmp/wt-<pr> origin/<pr-branch> -b planner-<pr>-gates
   cd /tmp/wt-<pr> && git reset --hard origin/<pr-branch>   # exact tip
   make check-workflows && echo rc=$?   # rc=0 at the head
   make check-wiring    && echo rc=$?
   make check-docs      && echo rc=$?
   make test-unit                          # hermetic leg (the CI linux/unit gate)
   ```
   Each green gate is a real `command rc=0 <sha>` — the second evidence form
   the gate accepts, with NO dependence on the CI queue. Run the hermetic leg
   via `make test-unit`, not a bare `pytest` (the worktree venv may lack
   pytest; the make target selects the provisioned interpreter). Post the
   measured `command rc=… <sha>` set on the issue as a comment, then let the
   reviewer's write-back cite it. This is the honest escape from the
   "pending run" loop, not a bypass of it.

3. **Bind evidence to the verified head only.** Confirm the PR head from the
   API pull object (`gh api repos/<S>/pulls/<n> --jq .head.sha`) and that it
   equals the branch ref head, immediately before running gates or writing
   evidence — `gh pr view` JSON, the commits list, and the branch ref can each
   be a beat stale and disagree, and evidence bound to the wrong sha re-reds
   the gate as "not at the current head". Then: if the gates are green at the
   verified head, the reviewer runs `acceptance_writeback --proven <item>
   --verdict-ref '<... run=<id> head=<sha>'` (or cites your measured
   `command rc=… <sha>` set); if red, name the failing gate and never force-tick.
4. Re-verify `check-pr-acceptance` green on the issue, on the wire, before
   calling the PR unblocked. A tick without read-back is a claim.

## Anti-patterns that caused this to repeat

- Re-dispatching the same lane with the same unproven body.
- Ticking a box with `(proven: committed at head …)` — no rc, no run id.
- Marking a pending gate's box done to "look green".
- Reporting the PR as fixed while `scope` still reds.
