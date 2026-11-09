# Changing this lane's own SOUL/skill (issue → PR)

When the work is "encode rule X into my own `agents/<profile>/SOUL.md` or skill", not a rebase.
Behaviour is versioned by issue + PR under `agents/<profile>/` — never a private edit of the live profile.

## Procedure

1. **Fresh base, then claim.** `git fetch origin main` (canonical `asimov-agent/llgenie`; a fork named
   `origin` is not upstream), make a worktree branched from the sha fetched **in that moment**, write that
   sha into a start comment on the issue. Re-read the issue thread first: an existing `bot-claim:` or a
   live branch on the same files outranks your plan; an analogous issue in another lane is separate scope
   unless the files collide.
2. **Mirror an existing encoding.** Find the lane that already encodes the same contract clause
   (`git log --oneline -- docs/changes.d | grep <topic>`, then read its SOUL + skill + note pair) and copy
   its structure. Two edits must agree: a SOUL rule bullet **and** the matching section in the skill's
   `SKILL.md`. One without the other is half the contract.
3. **Change-note pair (#1123).** Every change ships two files:
   - `docs/changes.d/<YYYY-MM-DD>-<slug>.md` — a single pipe-table row
   - `agent-wiki/<YYYY-MM-DD>-<slug>.md` — the note body, naming the issue it closes
4. **`make changes-index`** — regenerates `CHANGES.md` from the fragments. Run it *after* adding the
   fragment, before the gates. Confirm the row landed (`grep -c '<slug>' CHANGES.md` → 1) and that
   `git status` shows **only** your intended files. The fragment count in a fresh worktree is authoritative
   for the fetched tree — do not compare it against a count from an older checkout.
5. **Gates, in this order:** `make check-docs` → `make lint` → `make check-pr-hygiene` →
   `python3 scripts/check_pr_base.py check --base refs/remotes/origin/main --rev HEAD` (#845) →
   `python3 scripts/check_pr_authors.py check --base refs/remotes/origin/main --head HEAD`.
   Run the closing gate against the **live PR body** once the PR exists — a body file that does not exist
   is a mistake, not a gate failure.
6. **Commit + identity.** Author must be an allowlisted identity (`Asimov Agent <support@docondee.com>`
   is the one this lane uses); a foreign author reds `check-pr-authors`. One atomic commit.
7. **Push + PR.** Both head-repo conventions exist — some lane PRs live in `asimov-agent/llgenie`, others
   in the `andyholst` fork. Check the head repo of a few recent merged PRs of the **same kind** instead of
   assuming; a self-authored lane change normally pushes to canonical. Open **ready-for-review (never
   draft)**, body ending with `Closes #<issue>` and citing the base sha.
8. **Bookend.** Finish comment on the issue: head sha, PR number, what changed per file, gate results,
   and the CI state measured from `check-runs` conclusions. Then report the same two lines to the planner.

## Syncing the live profile: measure read-only BEFORE any sync

Four commands, and their DIRECTION is not symmetrical — confusing them destroys behaviour:

| command | direction | effect |
|---|---|---|
| `make sync-agent-profile PROFILE=<p> CHECK=1` | read-only | parity report — use this to measure |
| `make sync-agent-profile PROFILE=<p>` | tree → live profile | **REPLACES live behaviour** with the tree's |
| `make tester-fold-live PROFILE=<p>` (no `COPY`) | read-only | drift report: `same / drifted / live-missing / live-only` |
| `make tester-fold-live PROFILE=<p> COPY=1` | live → tree | overwrites tree files with live content, **deleting tree-only lines** |

Before any real sync, prove the tree is the newer side: `git status --porcelain agents/<profile>/` empty
(no local edits), tree files byte-identical to `origin/main`, and `diff` against the live profile showing
only `>` (tree additions), never `<` (live-only lines a sync would destroy). A `LIVE-ONLY` row in the
drift report is not automatically lost contract — check whether the live `SKILL.md` actually links that
reference; an unlinked live-only reference is a working note, not behaviour anyone is running.

## Pitfalls

- **A duplicate skill directory makes the whole skill unloadable.** Two copies carrying the same `name:`
  under the profile's skills dir (e.g. `skills/<name>/` and `skills/<category>/<name>/`) make `skill_view`
  refuse with "Ambiguous skill name" and make `prompt-size` print `n/a` for that skill — so a "reload"
  silently does nothing while looking successful. Detect with
  `find <profile>/skills -maxdepth 2 -type d -name '<name>'`; keep the copy whose `SKILL.md` md5 matches
  `agents/<profile>/skills/<name>/SKILL.md`, move the other OUT of the skills tree (quarantine, never
  delete), then confirm `prompt-size` reports a real byte size and `skills list` shows exactly one entry.
- **`gh pr create --body-file <path>` needs the file to exist first** — write the body with a file tool
  before calling. A missing body file fails the create call; it is not a gate result.
- **`gh pr edit` has no `--jq`** — verify the body by reading it back with `gh api` / `gh pr view`, not by
  adding `--jq` to the edit call.
- **Self-authored lane PRs are owner-gated (#1088):** do not arm auto-merge on them; report
  `auto=none (owner approval)` and let the owner approve.
- **Several `guard` check-runs queued at the head is normal** — the guard job fans out per matrix. Poll
  `check-runs` conclusions; `status:"queued"` means *not yet*, never red.
- **A conflict-state PR can show an empty checks rollup** — that is the symptom of the base state, not a
  workflow fault. Read conclusions; do not narrate an empty rollup as a failure.
