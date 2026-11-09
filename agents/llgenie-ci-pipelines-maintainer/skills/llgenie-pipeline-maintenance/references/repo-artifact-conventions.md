# Repo artefact conventions and measurement hygiene (llgenie)

Rules that cost a review cycle when missed. Each is a general rule + the mechanism that makes it bite.

## Run docs gates on the HOST, not inside the repo container

- `make check-docs` inside the `llgenie/test` container reports two reds that are **artifacts of the
  bind mount, not your change**: the change→note gate prints `skipped (no base ref)` and the
  architecture census prints `UNREADABLE: git could not read this checkout`. A worktree's `.git` is a
  pointer file into the real repo's `.git/worktrees/<name>`, which the container can't resolve.
- Run the gates on the host where git works: `PYTHONPATH=scripts python3 scripts/check_docs.py check`
  (set `CHECK_DOCS_BASE=<base-sha>` to exercise change→note, not just changes-index). A green run
  still prints the change→note line only if the base resolves.
- The census `UNREADABLE` is a separate, pre-existing break on main — **not** something your PR must
  cure. Confirm your diff doesn't touch it: `git diff <base>...HEAD --name-only | grep -E
  'ARCHITECTURE|check_architecture'` empty = your PR is clean of the gate it can't read.

## A merge event is not a verdict; neither is a local probe that skipped a leg

- A PR reading `MERGED` records the merge *decision*, not that CI passed — owner/auto-merge can land
a PR whose head run is still `in_progress` or red (measured: several PRs merged while their head's
`ci-unit` had not concluded). `merged: true` and `mergeStateStatus` are decisions, never test verdicts.
- A local gate probe that prints `skipped (no base ref)` / `UNREADABLE` (the container/worktree
artefact above) ran only PART of the gate; it is not the verdict either. Reporting "main green" off a
probe or a merge event is the exact false claim to avoid.
- The verdict is the COMPLETED CI run at the merged head: filter
`gh api "repos/<o>/<r>/actions/runs?head_sha=<sha>"` to `status=="completed"` for the heavy
`ci-unit` / `linux/unit` job, wait for it (it legitimately runs ~1h45m, see SKILL.md "date the job"),
and read the failing step's log. "main green" means every job at that sha concluded `success` — not
that the PR merged, and not that one local check passed.

## A stale generated dispatch table is usually a pre-existing main red

- `docs/BOTS.md`'s dispatch table is generated from the dispatchable workflows and verified by
`check-dispatch-forms`; `ci-unit` ALSO verifies it via `tests/test_dispatch_forms.py` and
`tests/test_issue_bot_manual_pick.py`. A PR can merge while the table has drifted from a NEW dispatch
`input:` (a `model`, an `arch`, a `dry`) — then every main-tip `ci-unit` fails those two tests even
when your diff never touched a workflow.
- So a "main green" claim needs those two tests run, not `check-docs` alone. The fix is a one-line
regeneration (`make check-dispatch-forms report` → splice the rows between the markers); prove it with
the gate printing `OK`, both tests passing, and a one-row diff. Probe the base commit to confirm the
drift predates your diff — a red you did not cause is a report, not a silent heal.

## A `docs/changes.d/` fragment is exactly ONE row

- A change adds **its own** file `docs/changes.d/<note-stem>.md` holding a **single** row:
  `| date | summary | [note](agent-wiki/<stem>.md) | #issue |`. Two changes add two files, so no
  merge can re-dirty an open PR (the change index is a directory, never one shared table).
- `scripts/changes_index.py` `parse_row` rejects anything but one row: a `NEXT_DATE` comment, a
  blank line, or any second line fails with `holds N line(s); a fragment is exactly one row`. Write
  **only the row** — no header, no comment, no trailing prose.
- The linked note lives at `agent-wiki/<stem>.md` and must name an issue or PR.
- **Never edit `CHANGES.md` by hand.** Run `make changes-index` (`python3 scripts/changes_index.py write`)
  to render it from the fragments. `make check-docs` is the gate and checks: every user-facing make
  target's `##` help line is documented, every `agent-wiki/` entry has its own index row in
  `docs/changes.d/`, and `CHANGES.md` links no missing note. A green run prints the fragment count
  it rendered.

## Check the worktree is at upstream/main BEFORE you measure a claim

- A worktree can be dozens of commits behind and **not** an ancestor of main. Measuring a gate or
  a `file:line` claim there produces a confident FALSE finding — the file content you read is a tree
  main already replaced.
- Before asserting any drift/gate claim, run `git rev-list --count upstream/main..HEAD` (0 = at or
  ahead of main) and `git merge-base --is-ancestor HEAD upstream/main` (non-zero = branch from a
  different lineage). Report the sha you measured at, beside every finding.
- Branch from a freshly fetched `origin/main` at the sha you fetched **in that moment** — never a
  branch you already had, never a sha quoted in a chat message.
- **Never push `HEAD:<branch>` from a worktree you did not commit in.** A shared `main` worktree's HEAD
  is main's tip (or a stale checkout), so `cd <main> && git push <remote> HEAD:agent/...` pushes the
  WRONG commit onto your feature branch and the PR opens from an unrelated head. Push the explicit sha
  (`git push <remote> <sha>:<branch>`) and only after `git rev-parse HEAD` in the worktree you edited
  equals that sha; if you already pushed the wrong head, force-push your real sha over your OWN
  just-created ref (`--force-with-lease=<ref>:<wrong-sha>`), never over another lane's.

## A head can carry several CI runs — aggregate, never `at_head[0]`

- `cancel-in-progress` leaves a **cancelled attempt beside a live re-run at the same head**. Taking
  the first run at the head reports a false `UNTESTED` for a PR that is actually testing.
- Classifier order: any still-live run → `in-progress`; any concluded `success` → `green`;
  `UNTESTED` only when nothing is live **and** every run at the head was `cancelled`. A cancelled
  suite is UNTESTED, never green — but a live re-run is never mislabelled either.
- Proof shape: revert the classifier to `at_head[0]` and the cancelled-beside-live and
  success-at-head tests must go red; restore and they pass. A classifier only ever run against the
  correct board proves nothing.

## `git diff HEAD...<base>` is empty when `<base>` IS the parent — use two-dot to prove a commit's change

- Three-dot `git diff A...B` diffs `merge-base(A,B)` against `B`. When you are ON your commit and compare
  against its own parent (`HEAD...1db367a2` where `1db367a2` is `HEAD~1`), the merge-base is the parent, so
  the diff is empty — a committed change **looks like zero files changed**. That is a diff-mode artefact,
  not an empty commit.
- To prove what a commit actually changed, use the two-dot form: `git diff --name-only HEAD~1 HEAD` (or
  `git show --stat <sha>`). Reserve `base...HEAD` for "everything this branch adds over where it forked".
- Corroborate with the strongest independent proof: the committed blob's hash equals the source you meant
  to copy — `git show HEAD:<path> | md5sum` == `md5sum < <live-or-source-file>`. A matching blob at the PR
  head is proof the content landed regardless of how any diff command renders.

## Never hand-edit `CHANGES.md` — a manual row passes the gate but diverges from the renderer

- `make check-docs` / `changes_index.py check` pass on a hand-patched `CHANGES.md` row, so the error is
  invisible locally — but `CHANGES.md` is GENERATED from the `docs/changes.d/` fragments, and the next
  `make changes-index` re-renders it, silently dropping or reordering the hand-added row.
- Add ONLY the one-row fragment `docs/changes.d/<stem>.md` + its `agent-wiki/<stem>.md` note; run
  `make changes-index` (`python3 scripts/changes_index.py write`) to render `CHANGES.md`. If a fragment
  for a sibling PR's half is not in YOUR worktree (it lives on the other branch/PR), that is expected —
  do not hand-fill its row; each PR carries its own fragment.

## Negative control for every new guard

- Plant the bug, run the new rule against the OLD tree, count the violations it names, restore,
  count zero. A guard that has only ever run on the fixed tree has demonstrated nothing.
- When a value change moves how something is *expressed* (a literal ceiling, a status field, a
  `##` help line, an inline→make call), grep the suite for the OLD spelling first — a correct fix
  gets redded by a test asserting the shape it replaced.

## `gh` output: capture to a file, shell not subprocess

- If a `gh` call returns empty from a python subprocess (keyring-backed auth not inherited), run the
  same call in the shell redirecting to a file (`gh pr view N --json ... > /tmp/x.json`) and read the
  file. Retry-with-different-transport, never "gh is broken".
- A shell-quoted `\uXXXX` escape passed to `gh ... --title`/`--body` lands **literally** as the characters `\u2019`, not the character — the title then stores a backslash-u sequence. Put the real character in the argument, or pass long/edge-case bodies via `--body-file`. If a literal escape slipped in, fix it with `gh issue edit N --title "..."` and re-read `--json title` to confirm.
