# Lint + PR gates: sharp edges

## `scripts/lint_linefeeds.py` lints the SCRIPT's repo, not your worktree

`_repo_root()` is `parent.parent` **of the script file**. Running the script by absolute path from a
`/tmp` worktree lints the *main clone* and can return rc=0 while the branch tree actually fails — a
false pass that cost hours of chasing a phantom green. Always run it from inside the target worktree
(`cd <wt> && make lint`, or via that worktree's own `scripts/` path), never by absolute path from
elsewhere.

`make ci-lint` == `make lint` == this script. Two rules: **trailing newline** required on every
tracked text file, and **a markdown heading must be preceded by a blank line** — a `## Foo` glued to
the last line of a list is the recurring red (flag names the line number).

## Gate semantics that red a fold PR's `scope` / `guard` job

- **check-docs (#1123) change→note:** a changed surface under `agents/.../skills/` owes an
  `agent-wiki/` note **in the branch diff** — the note merely *existing in `main`* is not enough. A
  ref-only corrective fold must amend the existing note (or add a row) so the diff carries an
  `agent-wiki/` change.
- **check-pr-closing (#1329):** an `agent/*` PR needs an adjacent `closes #N` in the squash commit
  **and** the PR body. A stale base that predates a `main` move re-trips it — rebase onto current
  `main` fixes it.
- **check-pr-acceptance (#1792/#1797):** a PR body's `closes #N` is HELD when issue `#N`'s LIVE
  `## Acceptance criteria` still carries `- [ ]` boxes. The gate reads the issue at merge time
  (`scripts/check_pr_acceptance.py check --body-file <pr-body> --repo <o/r>`; `report` prints the
  per-issue ticked count), so it reds on the wire even when your diff is fine. Two ways it clears:
  (a) tick the boxes via the verdict-gated write-back (`references/acceptance-writeback-seam.md`) —
  a reviewer verdict is what authorizes it (#1644); or (b) name each unmade criterion under a
  `## Not covered` bullet ending in a `#<n>` (the gate matches the criterion's first three words
  beside a `#<n>`), but ONLY for criteria the PR genuinely does NOT cover.
  **A bot-implementing-its-own-issue PR reds this by DESIGN pre-review — do not fake it away.** Its
  criteria are implemented (so `## Not covered` would be a lie) and cannot be self-ticked without a
  verdict, so the PR is OPEN/MERGEABLE with this gate red until the reviewer verdict + #1644
  write-back land. Fleet precedent: sibling implementing PRs sit in exactly this state. Report it as
  "held by the by-design acceptance gate, awaiting reviewer verdict"; stop at the reviewable PR and
  do not merge/arm it (#1088).
- **check-pr-openspec-change:** a diff the gate classifies as product code — `scripts/`, `Makefile`,
  workflows, `.hermes/skills/**`, AND **`agents/<profile>/skills/**`** (a versioned profile skill or
  its `references/*.md` is product code, NOT docs — `_is_docs_only` exempts only `docs/`,
  `agent-wiki/`, `CHANGES.md`) — needs its OWN `openspec/changes/<name>/` (proposal + spec + tasks,
  all `[x]`), or the PR body needs an `OPENSPEC: <name>` line naming an existing active change.
  **The change→note trio does NOT satisfy this gate** — a note + changes.d row + CHANGES.md clears
  check-docs (#1123) but leaves check-pr-openspec-change red, so a skill-doc fold needs both. To
  find a name to cite: `gh api repos/<o/r>/contents/openspec/changes --jq '.[].name'`; an
  `agents/<profile>/skills` fold cites the profile-tree change (`agent-profile-tree` while it is
  active). Pass the body via `--body-file`; `--body` takes a literal string, so handing it a file
  path reads nothing and the gate misfires. `openspec-tasks-check` is pure-python and runnable
  locally to prove the tasks before the gate runs.

## Adding a HOST agent skill (`.hermes/skills/<name>/`)

`scripts/check_agent_skills.py` iterates the skill dirs, so a NEW dir auto-appears in `found`. If no
leg under `.hermes/legs/` preloads it, `check-agent-skills` reds it unless its name is added to
`HOST_SKILLS` in that script — that one script line is the only code change such a PR normally needs.
The skill's frontmatter `name:` must be the human/hyphenated form (matching the dir) with the exact
`## Inputs` / `## Output` / `## Rules` headings the gate checks. Because the `HOST_SKILLS` edit sits
under `scripts/`, the PR also owes the OpenSpec presence change and the change→note trio
(`references/change-note-gate.md`).

## Scope job matrix

The `scope` check runs a matrix; a single sub-step doing `make ci-lint` or `make check-docs` can
fail while the others pass. Read the sub-job log that names the file/line, not the summary status.
