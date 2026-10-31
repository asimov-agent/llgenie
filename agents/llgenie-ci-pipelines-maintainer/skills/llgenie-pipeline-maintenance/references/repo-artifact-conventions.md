# Repo artefact conventions and measurement hygiene (llgenie)

Rules that cost a review cycle when missed. Each is a general rule + the mechanism that makes it bite.

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

## A head can carry several CI runs — aggregate, never `at_head[0]`

- `cancel-in-progress` leaves a **cancelled attempt beside a live re-run at the same head**. Taking
  the first run at the head reports a false `UNTESTED` for a PR that is actually testing.
- Classifier order: any still-live run → `in-progress`; any concluded `success` → `green`;
  `UNTESTED` only when nothing is live **and** every run at the head was `cancelled`. A cancelled
  suite is UNTESTED, never green — but a live re-run is never mislabelled either.
- Proof shape: revert the classifier to `at_head[0]` and the cancelled-beside-live and
  success-at-head tests must go red; restore and they pass. A classifier only ever run against the
  correct board proves nothing.

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
