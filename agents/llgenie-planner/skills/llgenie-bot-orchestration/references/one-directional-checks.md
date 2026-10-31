# A check answers a neighbouring question

Nine defects corrected in one evening, and every one had the same shape: a command, gate or field
answered a question adjacent to the one being asked, and the reader assumed the exact one. This is the
catalogue, the tell for each, and the rule that covers them.

## The catalogue

| instrument | answers | the question being asked | how it was caught |
|---|---|---|---|
| `mergeable` / `mergeStateStatus` | do the two commits differ | will this merge | a PR read UNKNOWN while GitHub recomputed; `DIRTY` and stale look alike |
| `check_docs` (CLI) | does the aggregate parse | does `committed == rendered` | the suite red four PRs while the CLI said rc=0 (#1100) |
| `changes_index.py check` | are the fragments accounted for | does the committed table equal a render | "ok: 276 fragment(s)" while two rows were swapped (#1100, #1094) |
| a frozen `run.updated_at` | when was the last event | is this hung | it does not advance during a long step; a cancelled run read as a 32-min freeze |
| `cancelled` | why it stopped | is it green | three PRs carried "13 success" with the deciding gate cancelled (#1111) |
| `skipped` after a cancelled fan-out | no decision existed | this diff needs no job | byte-identical to a legitimate scope skip (#1111) |
| `autoMergeRequest.enabledAt` | when was arming requested | is this head armed | unchanged across three head moves; a disarm is undone in 2 min (#1106) |
| `reviewDecision` | is there an approval now | has this been reviewed | resets on every push with no record (#1106) |
| set sizes subtracted | arithmetic on two counts | the size of a set difference | 303−31 said 272 uncovered; the truth was 154 (#1102) |
| `grep -c <name>` | does this string appear | is it a co-author trailer / a real hit | prose matched; `^co-authored-by` gave 0 |
| `git log --all` / `for-each-ref` | is it reachable from a ref | does this commit exist | a force-pushed-away head is unreachable and present |
| `git diff main...<tip>` | do these commits differ | does this branch contain work main lacks | squash merges made a merged replay look 133-branches unique; the truth was 6 (#864) |
| an unanchored grep for a filename | does this path appear anywhere in the output | did this path conflict | `merge-tree --messages` prints `Auto-merging <path>`; use `grep -E '^CONFLICT'` |
| `tools_block()` output vs the lint gate | does the generator emit what it emits | does it match the committed form | marker→heading with no blank line; lint rejects it (#1119) |
| `check-docs` note→fragment | does a note have a fragment | does a change have a note | 16 of 40 recent PRs carried neither (#1123) |
| `gh api …?per_page=100` | is it on the first page | does it exist | a posted comment read as missing, twice in one evening |
| `git rev-list --count main..HEAD` on a worktree | how many commits are not on main | is this work recoverable | **0 commits ahead means the work exists only in the directory** — a prune's ancestry test calls it merged and deletes it; two lanes' uncommitted work was found this way (#864) |

## The three tells

1. **"nothing found" and "couldn't tell" print the same thing.** A detector whose empty result and
   unknown result are identical will silently stop watching. The rebase lane found this live: all
   eleven open PRs read `UNKNOWN` at once, the detector printed `conflicting: none`, and a genuine
   conflict in that window would have suppressed every later tick, because byte-stable output is what
   the monitor gate uses to stay quiet.
2. **A count that is identical before and after the fix.** Main's `test_host_bot_capabilities.py` has
   six test defs with zero blank-line assertions; the fixed version has six too (the additions are
   assertions inside existing tests). "6 passed" cannot distinguish the two trees.
3. **An implausible number.** 133 unique branches, 272 uncovered targets, 39 minutes. Each was wrong
   by a factor or a unit, and each was caught by a control rather than by review.

## The rule

- **Never quote a field; quote the measurement behind it.** `conclusion` and `completed_at` for a run,
  `state` and `mergedAt` for a PR, `git cat-file -t` and the API for a sha, `test_*` for a gate.
- **After any state change, re-read the object, not its derived flags.** A status with a
  `completed_at` is a verdict and cannot revert; a status without one is a snapshot.
- **Where the head cannot be re-read in the same call that writes the line, write
  `pending at <hh:mmZ>`** — a fact with an expiry, the only form a reader can falsify.
- **A checker that only ever says OK is worthless.** Exercise the negative: commit a conflict marker
  and watch the verifier red; swap two rows and watch the render check red. If it cannot fail, it is
  a ritual.
- **A rule enforced in one direction is half a rule.** When a gate asserts A⇒B, ask what asserts B⇒A,
  and if nothing does, that absence is the defect.
- **Prove the subset, do not assume it.** Before copying one tree over another, count the lines that
  would be lost (`tree-only: 0`), and explain a negative diff as moved lines rather than waving it.

## Why this matters for an orchestrator

Every board line is a claim about a head. The drafting is not the risk; the reading is. Tonight the
planner quoted a `mergeable` as a verdict, adopted an analysis without re-running it, attributed one
lane's commit to another three times, and told a lane to arm a PR its charter forbids arming. Each was
plausible at the moment it was written. What corrected them was a command, not a second opinion — and
two lanes citing the same wrong command is not corroboration, it is one measurement counted twice.
