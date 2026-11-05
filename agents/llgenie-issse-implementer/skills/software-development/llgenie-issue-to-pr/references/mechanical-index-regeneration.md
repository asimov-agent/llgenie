# Regenerating a generated index (red on merged main)

Quick map of the renderer's subcommands: `scripts/changes_index.py render` PRINTS the table
 to stdout; `write` rewrites `CHANGES.md`; `check` verifies committed == rendered. Running
 `render` and seeing your row is a NO-OP on disk — `git status` stays clean and the file is
 unchanged. Only `write` (or `make changes-resolve` / `make changes-index`) lands it.

## Resolving a `CHANGES.md` conflict during a rebase

`CHANGES.md` is a single append region, so it conflicts almost every time main advances.
Do not hand-merge the markers in a rebase:

1. Take EITHER side of the file wholesale, e.g. `git checkout --ours -- CHANGES.md`,
   `git add CHANGES.md`.
2. Regenerate from the fragments that are now on disk: `python3 scripts/changes_index.py
   write` (or `make changes-resolve BASE=<fresh-main-sha>`). Both sides' fragments are in
   the tree, so the renderer re-emits every row.
3. Confirm your row survived exactly once: `grep -c '<note-stem>' CHANGES.md` → 1.
4. `git add CHANGES.md` and `GIT_EDITOR=true git rebase --continue`.

**`--ours`/`--theirs` are INVERTED during `git rebase`:** `--ours` is the upstream base you
are replaying onto and `--theirs` is YOUR commit — the opposite of merge intuition. This is
exactly why step 1 says take either side and let the renderer decide: reasoning about
which side is "mine" during a rebase is where the wrong-resolution mistake comes from.

A generated index (`docs/CHANGES.md`, rendered by `make changes-index` /
`scripts/changes_index.py` from the `docs/changes.d` fragments) can be RED on the merged
main while every PR head was green. This is the most common "main is red, docs lane
refused it, mechanical fix" dispatch. Treat it as an index-only repair.

## Symptom

`tests/test_changes_index.py` fails with "CHANGES.md carries a row `make changes-index`
would never write": the committed table disagrees with what the renderer produces
(committed ∉ rendered). PR-head CI was green because the fragment correction landed in a
different PR than the re-render — the index was never regenerated after the correction.

## Why (mechanism)

Index rows are RENDERED from the fragments. Each row stamps the target file's md5, byte
size and line count. When a later PR corrects a fragment (e.g. strengthens an agent-wiki
note so its md5/size change) but does not re-run the renderer, the committed row keeps the
pre-correction stamp. Committed table then ≠ render of the current fragments.

## Diagnose (git + renderer, no container needed)

- Read the failing row and its stamped `md5 <x>, <N> B, <L> lines`.
- Read the on-tree fragment / agent-wiki note it points at; compare the actual md5/size.
- Run the renderer and diff committed vs rendered — the diff should be exactly the stale
  stamp plus (optionally) a lagging row.

## Fix discipline (scope is index-only)

- Regenerate ONLY the index file: `make changes-index`. Commit only that file.
- NEVER hand-edit a fragment to match a stale index — the fragment is the source of truth.
- NEVER touch source files or fragments; they are already correct.
- The render may also ADD a row the committed table lags (a newer fragment not yet
  indexed). That is allowed: a stale index may lag, never invent.
- Prove scope: `git diff --stat <base>..HEAD` must show exactly the one index file.

## Verify

- Run the renderer twice — a second render must change nothing (idempotent ⇒ committed ==
  rendered).
- `scripts/changes_index.py check` — OK.
- Run the SPECIFIC test file in the container, not the full suite:
  `docker run ... llgenie/test:latest pytest tests/test_changes_index.py`.
  `make test-unit` over the whole suite runs 7+ minutes and times out a tool call; the
  targeted file is the authoritative proof that the failing assertion is green. Let the
  pushed-head CI matrix carry the full-suite verdict.
- `python3 scripts/check_pr_closing.py check --body-file <f> --base <sha> --rev HEAD`
  before opening the PR.

## Pitfalls

- **`render` writes nothing; only `write` does.** A `changes_index.py render` output showing
  your row is printed to stdout — the file on disk is untouched. Use `write` and verify with
  `git diff --stat`.
- **Shallow clone makes an ancestor pointer unresolvable.** `check-docs`/census gates
  quote an ancestor sha that a `git clone --depth 1` cannot see — it looks like a fold
  defect but is a shallow-clone artifact. Deepen the clone (`git fetch --deepen` / clone
  with a larger `--depth` or full) and re-run the gate before concluding anything is
  broken.
- **A subprocess-authored fix trips the completion monitor.** The change is made by
  `make changes-index` + `git` + `gh`, which a monitor that only tracks direct
  `write_file`/`patch` cannot see, so it reports "no task-relevant mutation". Do NOT
  fabricate a byte-identical write to flip it. Ground the committed change from the live
  remote instead: `git ls-remote <url> refs/heads/<branch>`, an independent clone's
  `git diff --stat base..HEAD`, and `gh pr view --json`; quote the bytes and hold.
- **Post the PR body/comment with `--body-file`, never inline.** A body containing backticks
  or `$(...)` inside a double-quoted shell string is substituted (or heredoc-expanded) and
  arrives blank or mangled — GitHub then rejects it with "Body cannot be blank". Write the
  markdown to a file and pass `gh pr comment <n> --body-file <file>`.
