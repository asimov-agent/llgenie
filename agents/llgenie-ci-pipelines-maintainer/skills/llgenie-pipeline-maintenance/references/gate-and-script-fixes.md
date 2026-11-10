# Fixing a gate or script in llgenie (`scripts/*.py`)

The procedure for the recurring case where a defect is in a gate, a script, or a make
invocation this lane owns — not in product code. Ordered; pitfalls attach to the step.

## 1. Establish the true base before touching anything

```bash
git fetch upstream main            # canonical remote is asimov-agent/llgenie
git rev-parse --short upstream/main # write THIS sha into your start comment
git worktree add ../llgenie-<issue>-<slug> -b fix/<issue>-<slug> upstream/main
```

**Pitfall — a stale fork-main worktree lies to you.** `git grep HEAD` searches the
*worktree's* HEAD, not upstream. A file can resolve at `HEAD` and be absent from the
current upstream tip at the same time — the issue's cited `file:line` then looks wrong
when it is merely being measured against the wrong sha. If `git grep` and
`git ls-tree upstream/main` disagree, the worktree is stale; branch from the freshly
fetched sha before you read or edit anything.

## 2. Read the target function AND its neighbour guard

Read the function the issue names and the tests that already pin its shape. Gates in this
repo carry their own invariants — when the issue is "X lacks the guard that Y has", copy
Y's exact idiom (same exception, same message shape, same exit code) rather than inventing
a parallel one. Example class: a paginated GitHub API listing (`?per_page=50`) must compare
the response's `total_count` to the returned page length and **raise / exit non-zero** on
mismatch — never treat a truncated page as a verdict. A 2500-run branch silently yields a
false green or false red from the first 50 rows alone.

## 3. Guard-proof BOTH directions, in the CI container

**Pitfall — a new MODE honoured by one entry point silently collapses in its siblings.** When a flag
means "sweep every value" and the script keeps a single-value driver underneath, every other caller of
that driver keeps the old single-value meaning. Adding `--arch all` to a `check` subcommand left the
`report` subcommand calling `report(bindir, arches[0])` — it printed one backend and looked clean, which
is the human-readable face of the gap the flag exists to close. So after introducing a mode: grep the
flag name and the shared driver across the whole script (`grep -n 'sys.argv\|add_argument\|<driver>(' `),
make each entry point honour the mode, and add a test per entry point — the check-side test passes while
the report side is still wrong.

The module's tests run via pytest inside the pinned image — there is usually **no**
`make check-<thing>` target for a script's unit tests (e.g. `make ci-verdict` is the
*runtime* gate invocation, not a test runner):

```bash
docker run --rm -u root -e PYTHONPATH=/repo/scripts \
  -v "$PWD":/repo:rw -w /repo -e HOME=/root llgenie/test:latest \
  python -m pytest tests/test_<module>.py -q
```

**Prove the new test fails on the un-fixed tree** (stash/revert the guard, run, count the
failure, restore, run, count zero). A test only ever run green has demonstrated nothing.

## 4. A gate-behaviour change needs a docs record or `check-docs` reds

A behaviour change to a gate is user-facing by the repo's own rule. Ship, in the same
commit:

1. `agent-wiki/<YYYY-MM-DD>-<slug>.md` — the note: issue, what changed, what was verified.
2. `docs/changes.d/<YYYY-MM-DD>-<slug>.md` — ONE table row naming its own note:
   `| date | prose | [note](agent-wiki/<note>.md) | #issue |`
3. Regenerate the index: `python3 scripts/changes_index.py write` (rewrites `CHANGES.md`
   from every fragment — never hand-edit `CHANGES.md`).

Then verify, all three:

```bash
python3 scripts/lint_linefeeds.py
python3 scripts/check_docs.py check --base upstream/main
# re-run the container pytest from step 3
```

## 5. Commit and PR ceremony

The commit and the PR body both carry `Issue:` / `Fix:` / `Benefit:` / `Technical:` and
`closes #<issue>`. **Write the message to a FILE and use `git commit -F`/`--amend -F`** — a backtick
inside a double-quoted `-m` string runs command substitution, so `` -m "... `--arch all` ..." `` executes
`--arch` and bakes `--arch: command not found` (or its output) into the commit body. Read it back with
`git log -1 --format=%B` before pushing; a mangled body under a pushed sha costs a force-push cycle. The `AGENTS:` line is `sha bytes lines` of `AGENTS.md` **at the base
sha you branched from** (not at HEAD):

```bash
B=<base-sha>
echo "AGENTS: $(git rev-parse $B:AGENTS.md) $(git cat-file -s $B:AGENTS.md) $(git cat-file -p $B:AGENTS.md | wc -l)"
echo "BASE: $B"
```

Open the PR **ready-for-review** (never draft), base `main`, head `andyholst:<branch>`.
Check it back: `gh pr view <n> --json state,isDraft,headRefOid,baseRefName` and confirm
`draft=false`. A `ms=BLOCKED` with all legs `QUEUED` is an in-flight queue, not a red —
never cancel or clear it.
