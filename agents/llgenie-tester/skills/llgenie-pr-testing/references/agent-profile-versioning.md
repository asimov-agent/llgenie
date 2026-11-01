# Versioning a host-agent profile in the repo (`agents/`)

The repository holds the canonical copy of each bot's behaviour; the live profile home is a copy of
it. Changing behaviour is therefore an issue + PR against `agents/<profile>/`, never a private edit to
`~/.hermes/profiles/<profile>/`.

## What the tree contains

| path | role |
|---|---|
| `agents/<profile>/SOUL.md` | the text the agent runs under: identity, the **canonical fleet block**, then `## This lane's rules` |
| `agents/<profile>/skills/<name>/SKILL.md` + `references/` | that lane's versioned skills, at a **flat** path |
| `agents/standing-rules.md` | the one copy of the fleet block; each SOUL states it verbatim |
| `agents/manifest.json` | which profiles are versioned and which rules each SOUL must state |
| `scripts/agent_profile_sync.py` | repo → live home copy; `--check` compares |

Gates: `make check-agent-profiles` (structure, declared rules stated, no secrets, and a `live-longer`
check) and `tests/test_agent_profiles.py` (includes a **byte-for-byte** comparison of the canonical
block against one SOUL).

## Procedure

1. **Find the real base.** These PRs stack. Do not assume the branch with the most files is the base;
   prove it:

   ```
   for b in $(gh pr list --state open --json headRefName -q '.[].headRefName'); do
     git merge-base --is-ancestor origin/<candidate-base> origin/$b && echo "$b descends from it"
   done
   ```

   The right base is the branch every lane's PR targets (the one carrying `agents/` itself → `main`).
2. **Create the lane** by copying the live profile's SOUL and the skill you want versioned. Keep the
   skill at `agents/<profile>/skills/<name>/` — a category subdirectory (`skills/software-development/
   <name>/`) syncs as "missing in the profile" because the comparison is flat.

   **Derive the lane's file set from the TREE (`git ls-files agents/<profile>`), never from an assumed
   layout.** The live home holds every skill on the machine; the tree holds only the versioned ones, so
   a hand-guessed path (`references/` one level above where they live, or a category directory) can
   match nothing and still report "in sync" — a fold that copies zero files looks identical to a fold
   with nothing to do. Use `scripts/fold-live-profile.py --profile <n>`: it enumerates the tracked tree
   files, hash-compares each against its live counterpart, flags live-only files under directories the
   tree already covers (the `skill-reference-missing` class), and with `--copy` moves only the drifted
   ones live → tree and re-hashes the destination. Re-run it at the start of EVERY round — the live
   half moves while the PR sits open.

   **Invoke it by its TREE path, which is NOT its live path.** The live profile keeps the tool under
   `skills/<skill>/scripts/fold-live-profile.py`; the tree holds it at repo-root **`scripts/`**
   (alongside the versioned `agent_profile_sync.py`). Running the live path from a branch worktree
   fails `Errno 2 … No such file or directory`, which reads like the file was never versioned. Get the
   path from the tree, not from memory: `git ls-files | grep -i 'fold-live-profile\|profile_sync'`.
   Run it from the worktree's root with the live home explicit, because its `--repo` default is `.`
   and its `--live-home` default is `~/.hermes/profiles`:

   ```
   cd <worktree> && python3 scripts/fold-live-profile.py --profile <n> --repo . \
       --live-home /home/asimov/.hermes/profiles
   ```

   Exit **rc=1** means drift (it prints the `DRIFT` lines and a `N same, M drifted` table) — that is a
   finding, not a crash. Add `--copy` to land the drifted files and print the `copied … OK` lines;
   re-hash both sides to confirm `tree == live` before committing. `rc=0` means already in sync, so a
   `0 drifted` result with no DRIFT rows is the no-op answer, never a tool failure.
3. **Register it** in `agents/manifest.json` with the rules the SOUL must state (`never-implement`,
   `never-merge`). The gate fails if a declared rule is absent from the SOUL.
4. **Adding a fleet rule:** write the bullet into `agents/standing-rules.md` **and** into every SOUL that
   carries the block, in the same commit. The byte-for-byte test compares a SOUL against the canonical
   file, so a bullet in one and not the other is an immediate red. Leave lanes whose SOUL is still a
   *seed* to their own PR — editing them only manufactures conflicts.
5. **Sync, then compare** — the sync is repo → live, so it changes your own profile:

   ```
   make sync-agent-profile PROFILE=<name>            # writes and reads back
   make sync-agent-profile PROFILE=<name> CHECK=1    # must print OK, N file(s) byte for byte
   ```
6. **Run the gates**: `make check-agent-profiles`, `pytest tests/test_agent_profiles.py`, plus
   `check-docs` and `check-wiring`. **The change record is a fragment, not a row in `CHANGES.md`**:
   one row per file at `docs/changes.d/<note-stem>.md` (plus the `agent-wiki/` note itself). Hand-editing
   the rendered `CHANGES.md` fails `check-docs` with "is not indexed", because the page is generated.
   Baseline the finding count: run `check-docs` on a clean worktree at the base sha too and report the
   identical count rather than assuming the red is yours.
   **The change→note gate reads COMMITTED paths, so an untracked note does not satisfy it.**
   `check_docs.py` derives the changed set from `git diff <base>...HEAD`; a freshly written
   `agent-wiki/<stem>.md` and `docs/changes.d/<stem>.md` that are still untracked are invisible to it
   and `make check-docs` keeps reding with the same "adds no agent-wiki/<stem>.md note" — which reads
   as though your note was wrong rather than unseen. `git add` + commit them, then re-run the gate;
   `make check-docs` passes on the committed tree. Order the cycle: write note + fragment → `make
   changes-index` (renders `CHANGES.md`) → `git add -A` + commit → `make check-docs`. Two more
   mechanical reds in the same edit: `lint_linefeeds.py` wants a trailing newline on every NEW file
   (a note/fragment written without one reds `ci-lint` after `check-docs` was already green), and a
   gate that maps the note to a `<stem>` wants the note stem to match the fragment stem and the
   branch identity, so pick one stem and use it for both files. **`check_docs.py` also requires every
   `agent-wiki/` note to name an issue or PR as a literal `#<n>`** — a note that describes the work in
   prose but never writes `(#1234)` reds with `references no issue or PR (\`#<n>\`)`. Put the id in
   the note's own heading or body; the check is a text match on the backtick-quoted form, so a bare
   issue number without `#` does not satisfy it. Two more traps around that red: an edit made with a
   line-rewrite (reassembling the file from `splitlines()`) silently DROPS the trailing newline and
   reintroduces the `lint_linefeeds` red in the same file, and because the gate reads COMMITTED paths
   the fix must be staged and amended before `check-docs` can go green — run
   `changes_index.py check && check_docs.py check && check_architecture_census.py check &&
   lint_linefeeds.py` as ONE chain and only then amend.
7. **Open it ready, never draft**, and state in the body that a base other than `main` schedules **no
   CI at all** — list the local gate results and the sha they were measured at, so an empty rollup is
   not later read as a verdict. That same fact decides the merge step: a stacked base has no required
   checks, so arming auto-merge there is an **immediate merge** into the parent branch, not a queue
   position. Report `auto=none (stacked base: no required checks)` and let the stack be merged
deliberately, top first.

## Failure shapes worth naming in the PR body

- **`TRUNCATED? … the tree copy is N b and the profile's is M b — syncing would REPLACE … of live
  behaviour`** — the live half moved and the tree is behind. This is not a sync: copy **live → tree**,
  commit it, then `--check` again. Re-run `--check` at the start of every editing round for that
  reason: the profile is the half that changes while your PR sits open (including from a lane that is
  not you), so a green `--check` ten minutes ago says nothing about now, and the direction to fix it
  is whichever side the guard calls truncated. **The size to sync to is the live file measured NOW
  (`wc -c`, or a fresh `--check`), never a byte count quoted in the dispatch or remembered from an
  earlier round** — a quoted size is a snapshot, so syncing the tree up to it REVERTS whatever the live
  profile gained since (a later round's lessons), while passing a stale check and losing the content.
- **`live-longer` finding** — "the tree has N b, the live profile has M b — the seed is a prefix of the
  rulebook". This fires on lanes whose SOUL is still a seed. Prove it is not yours: run the same gate
  on a clean worktree at the base sha and report the identical finding count, naming whose PR clears it.
- **`sync ... DIFFERS ... (missing in the profile)`** — the skill sits under a category directory, or
  was copied under a different name than the directory it lives in.
- **`check-agent-profiles` red for a rule the manifest declares** — the SOUL states the rule in prose
  that does not match the manifest's rule name; state it verbatim.
- **The tree copy states the fleet block TWICE and the first copy is stale.** The gates do not count
  headings, so a SOUL can carry the canonical text twice — once from before the last rule was added,
  once correct — and look fine. Detect it mechanically before deciding which side is right:

  ```
  python3 - <<'PY'
  from pathlib import Path
  H = "## Standing rules (fleet, learned 2026-10-28)"
  canon = H + "\n\n" + Path("agents/standing-rules.md").read_text().split(H, 1)[1].strip("\n")
  for label, p in (("TREE", <tree soul>), ("LIVE", <live soul>)):
      parts = Path(p).read_text().split(H)
      ok = [H + "\n\n" + part.split("\n## ")[0].strip("\n") == canon for part in parts[1:]]
      print(label, "blocks:", len(parts) - 1, "canonical?", ok)
  PY
  ```

  One block and `[True]` in the live profile against `[False, True]` in the tree means the **live
  side is the good one** and the re-take runs live → tree, even though the guard's message is phrased
  about a newer live mtime. Decide the direction from this comparison, never from the mtime alone.
- **A rebase can surface drift that was NOT there when you started — and it is LIVE that is ahead;
  re-take the whole drifted set in ONE amended head, never ship the older tree.** Live is edited by
  other lanes while your PR sits open, so a head that read `CHECK=1 … OK` an hour ago can, after a
  rebase onto newer `main`, report `live-longer` + `live-edited-not-tree` on files outside your
  change's topic (the pre-push gate doing its job, not a false positive). Pushing that tree
  downlevels live — `skill-reference-missing` reds CI and the runtime silently loses the newer
  lessons — and re-copying only the file you were editing leaves the rest still flagged. So: copy
  EVERY file the guard names live → tree byte-for-byte, re-run
  `agent_profile_sync.py --profile <n> --check` (must print OK, N of N) and the guard's `findings()`
  (zero naming your profile), then **re-hash the live files immediately before the push** — another
  lane may still be writing, and a byte that moved after your capture means the copy you are about to
  push is already stale; re-copy rather than push.
- **A sync is a CYCLE, not a one-shot: expect live to have grown again AFTER your sync PR merges.**
  The same working cycle that produces the sync also produces lessons, and live accumulates them while
  the PR sits open and after it lands — so a post-merge `--check` commonly reports fresh drift on files
  you just shipped, and the merged snapshot is already one round behind. That is the expected shape,
  not a failed sync: open a follow-up vehicle for the delta with its own `CHECK`/guard/lint gates, say
  in its body what it clears (and what it does NOT close), and never report "the sync is done" from
  the merged head. **But keep ONE fold vehicle in flight at a time — do not race live.** The delta is
  monotone accretion (live is never trimmed), so a follow-up opened while the current fold is still
  open or unmerged copies a superset of what the first vehicle already carries: the second lands a
  duplicate of the same content, burns a matrix, and produces two PRs whose diffs overlap. Sequence it
  strictly — land (or see merged) the existing fold, re-enumerate live, then open the next vehicle for
  whatever accrued since. "Live moved again" is not a reason to open another PR; it is the expected
  state the next round starts from, and waiting costs nothing because nothing is ever deleted. **Before copying, prove the live file is not MID-WRITE:** hash it, wait a couple of
  seconds, hash again — copy only when two reads agree, and treat a hash that moves between reads as
  another lane's active edit (re-read, do not snapshot). A capture taken mid-write ships a half-written
  file that passes `--check` because both sides carry the same truncation.
- **A fold's own proof lives at the MERGE COMMIT, computed against the CURRENT `origin/main` — not at
  your PR head and not against your PR's base.** A squash merge is a new tree whose sha you never
  authored, so `git cat-file blob <pr-head>:<path>` matching live says only that the head was right, and
  a drift table computed against the base you branched from reports files as drifted that have since
  landed. After the merge: fetch, then for each folded path compare
  `git cat-file blob <merge-commit>:<path> | sha256sum` against `sha256sum < "$LIVE/<path>"` and confirm
  `git merge-base --is-ancestor <merge-commit> origin/main` — that pair is "the fold held and it is on
  the default branch". When the same read shows live has already moved past the merge commit, report
  BOTH facts in one line (held at `<merge>`; drifted since at `<live>`): the next delta is the expected
  next round, never evidence the fold failed. Enumerate the drift against `origin/main`'s blob per file
  (a loop over `git ls-files agents/<profile>`), so a file that landed last round cannot be miscounted
  as open drift.
- **Never force a sync over a live file another lane just edited without reading both.** The live
  profile is edited by other lanes too; a `REFUSED … live newer than the source commit` can be a real
  in-flight edit. Read the diff, decide which side is correct (canonical-block comparison above), and
  if the tree is the defective side, take live → tree **on your own branch** — never push to a branch
  you were not dispatched for, and say in the thread which sha the copy came from.
- **A from-live re-take of a SKILL.md must carry every `references/<name>.md` it now links, in the
  same commit.** Landing the SKILL without a reference its body links re-creates the
  `skill-reference-missing` red (a tree copy goes from N references to N+1, and a single-file cp
  leaves a dangling link). List the references the live SKILL's body actually names and copy them
  live → tree byte-for-byte WITH it; verify with `agent_profile_sync.py --profile <name> --check`
  that the count moved. Enumerate live-only files mechanically before pushing:
  `find ~/.hermes/profiles/<name>/skills -type f | sort` minus
  `git ls-files agents/<name>/skills | sed 's|^agents/|~/.hermes/profiles/|' | sort`.
  Measured (#1152 @ `bf2796e9`, job 124452357268, 3 failed/3321 passed): `skill-reference-missing`
  is a HARD finding — `scripts/check_agent_profiles.py check` exits **rc=1** — and three
  `tests/test_agent_profiles.py` legs (`test_committed_tree_passes_the_gate`,
  `..._names_duplicate_canonical_rules_and_the_gate_does_not_fail_on_them`,
  `..._check_command_names_duplicate_rules_but_stays_green`) read that rc, so it reds
  `linux / unit` IN CI. By contrast the `live-longer` / `live-edited-not-tree` /
  `absent-from-tree` findings CANNOT fire in CI (the runner has no live home — its check logs
  `live-profile comparison SKIPPED`), which is why main sat green with 58 locally-measured
  findings: only TREE-INTERNAL inconsistencies (dangling reference links, tree-side duplicates)
  gate CI. A sync PR therefore owes one pre-push check beyond the lint: the guard's
  `findings()` over the synced tree must carry ZERO entries naming YOUR profile.
- **`sync ... REFUSED ... the live file was edited AFTER the tree copy was committed`** — the guard is
  **mtime**, not content, so it fires on your own earlier sync too. Diff first (`diff` the live file
  against the tree copy) and only force when the bytes are identical. **`make sync-agent-profile`
  documents `FORCE=1` but its recipe never passes `--force`** — the target help promises an option the
  command does not receive, so call the script directly:
  `python3 scripts/agent_profile_sync.py --profile <name> --force`, then `--check` to prove the result.
  Report the missing flag as a finding; it belongs to whoever owns the Makefile.

## Pitfall: trust the recipe, not the `##` help line

Every `##`-documented option on a repo make target is prose until you read the recipe under it. Open
`Makefile` and confirm the flag is actually passed (`$(if $(FORCE),--force,)`) before you rely on it —
a target that documents an escape hatch it does not forward turns a two-minute sync into a detour.

## Pitfall: the live profile is EXEMPT from the repo's markdown lint

A from-live copy can carry markdown the TREE's gate rejects: `scripts/lint_linefeeds.py` fails
"markdown headings not preceded by a blank line" on a `## Heading` that sits directly under an HTML
comment (the live SKILL's `<!-- host-bot-tools:begin -->` above `## Tools` is the known one). The live
profile is never linted, so the defect is invisible until the sync PR's `scope`→`ci-lint` job reds it
AFTER you have opened and armed it. Run `python3 scripts/lint_linefeeds.py` on the synced tree BEFORE
pushing, and fix the blank line in the LIVE source too (live→tree: add it to live, then re-copy) — a
tree-only fix leaves the two divergent and the next `CHECK=1` reds on the one-byte difference.

## Pitfall: a green `--check` in your worktree is NOT a fix on the branch that lands

`sync-agent-profile … CHECK=1 → OK, N file(s) byte for byte` compares the tree in YOUR checkout
against your live profile. It says nothing about the branch the PR will merge: a commit that exists
only locally leaves the PR head's tree still carrying the truncated files, so the divergence the
planner flagged is still open on the vehicle. **A local sha is not a landed fix** — verify against the
FETCHED branch head, never your worktree:

```
git fetch origin <branch>
git show origin/<branch>:agents/<profile>/SOUL.md | wc -c   # must equal live size, not the truncated one
```

If those bytes are still the old (truncated) size, the fix is local-only — commit it onto the branch
head and push, and report the BRANCH-HEAD sha that carries it, not your worktree's.

- **Do not measure remote bytes with `git show <ref>:<path>` piped through the shell — it truncates at
  ~50 KB and strips the trailing newline, so a byte-identical file reads as a 1-byte (or 50 KB) DIFF.**
  An apparent `wc -c` skew of one byte, or a SKILL.md showing "50 KB", is the shell munging, not
  divergence. The authoritative comparison is a content hash of the blob, not a size read of streamed
  text: `git cat-file blob <fetched-head>:<path> | sha256sum` against
  `sha256sum < "$LIVE/<path>"`. Confirm with the sha256 pair before concluding anything, and quote the
  matching hash in the report — a size read that disagrees with the hash is the artifact.

- **Version live-only edits by carrying them on the SAME open reconstruction PR, not a new branch.** When
  a live-skill lesson is discovered mid-PR (the checker flags a live-only edit), copy the current live
  byte-for-byte onto the PR branch, commit, fast-forward-push (never force — the base never moved, so it
  is a clean fast-forward), and let the same PR carry it. A `--auto` arm request on a PR with non-null
  `enabled_at` stays live and the PR head update is the vehicle. Re-run `sync-agent-profile CHECK=1`
  (7/7) and post the new head sha.

- **A rebase rewrites shas without changing a byte — verify by CONTENT, not by ancestry.** After
  another lane rebases the branch, your commit's sha changes (the same tree replayed under a new
  parent); `git merge-base --is-ancestor <your-old-sha> <head>` then reads NO even though NOTHING was
  dropped. Do not read "not an ancestor" as "lost": compare the content at the FETCHED head
  (`git show <head>:agents/<profile>/SOUL.md | wc -c`, or a sha256) against live — byte-identical
  means the reload is intact under a new sha. Quote the head sha fetched in the moment PLUS its
  content hash, never a sha from a prior snapshot, or every rebase turns your report into a claim
  about a tree that no longer exists. Confirm the whole 6-file gate at that head with
  `make sync-agent-profile PROFILE=<n> CHECK=1` at a worktree checked out on the fetched head, not
  on your old commit.

## Rebasing a sync PR onto fresh `main`: three mechanics that stop you dead

A sync PR that has sat open long enough to go `DIRTY` needs a rebase, and each of these three reads
as an error when it is only an unfinished step. All three: stop, do the missing step, continue.

- **`Terminal is dumb, but EDITOR unset` from `git rebase --continue` is a missing editor, not a
  broken rebase.** The continue wants to write a commit message and has no TTY to ask in — your
  conflict resolution is NOT lost. Re-run with `GIT_EDITOR=true git rebase --continue` (or
  `git commit --no-edit` then `--continue`). Never `git rebase --abort` on this message: that
  discards the resolution you just staged and replays the original broken pick.
- **`--force-if-includes` REFUSES after a rebase, and that is correct, not a broken lease.** The flag
  only permits the force when your local history already CONTAINS the remote tip. A rebase leaves you
  on a fresh lineage that no longer contains `origin/<branch>`'s old commit, so the precondition is
  unsatisfiable by construction. The safe replacement is an explicit lease pinned to the sha you just
  read:

  ```
  git fetch origin <branch>
  R=$(git ls-remote origin refs/heads/<branch> | cut -f1)   # the tip NOW, not one quoted in chat
  git push origin HEAD:<branch> --force-with-lease=<branch>:$R
  ```

  Read `$R` immediately before the push and state in the report that the lease was pinned to it —
  that pair (remote tip unchanged + lease pinned to that tip) is the safety argument, and it is what
  you cite instead of `--force-if-includes`. A `--force-if-includes` refusal is likewise NOT evidence
  the remote moved: confirm that separately with `git ls-remote`, or you re-fetch and re-rebase for
  nothing.
- **A rebase conflicting in a GENERATED file (`CHANGES.md`, a rendered index) is REGENERATED, never
  hand-merged.** Those files are output: their conflict hunks are two renderings of the same source
  set, so picking "ours" or "theirs" silently drops rows. Resolve by re-running the generator over
  the rebased tree — `make changes-index` reconciles every fragment from both sides — then
  `git add <file>` and `git rebase --continue`. Prove the resolution after the rebase: `git status
  --short -- <file>` empty means the tree already matches the generator's output; a diff there means
  you committed before the generator ran.

- **A push that would cancel a live run WAITS; automate the landing, do not force it.** If the branch
  head has a run `in_progress`/`queued` and the workflow sets `cancel-in-progress`, a push to land your
  commit destroys that run's matrix. Do not push into it, and do not sit idle waiting for a re-ping:
  launch a background `gh run watch <run-id> --exit-status --interval 30` whose next step is
  `git push origin HEAD:<branch>` — it lands the instant the run concludes, with no cancelled matrix.
  Push through the live run ONLY if the owner explicitly says so; absent that the hold stands, and you
  report the landed head sha when the watcher fires. **Exception — a run that is HUNG, not merely
  slow, is superseded rather than waited on:** when the run's `updated_at` (or step `started_at`) is
  frozen past ~2× its normal duration, the Hub probes healthy, and OTHER PRs' same stage is stalled too
  (the systemic-stall compare in the SKILL §5), the run will never conclude — so a docs-only diff that
  provably cannot affect the stuck job may be pushed to supersede it, with that evidence stated. This
  is the one case the wait does not bind; never push past a run that is merely SLOW.
