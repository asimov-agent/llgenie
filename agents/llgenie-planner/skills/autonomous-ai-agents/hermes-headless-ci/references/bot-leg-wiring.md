# Wiring a NEW bot leg into a gated repo — the checklist

Every item below is a gate that reds AFTER the code is written, so walk the list once instead of
discovering them one CI run at a time. Ordered as the work happens.

## 1. Before any code: the issue, the branch, the change dir

- Open the GitHub issue first when the repo's rules require it (issue → branch → change → PR).
  A work request that arrived in chat still gets an issue when the repo says so.
- Cut a worktree off the freshly fetched base (`git worktree add -b feat/<kebab> …  origin/main`).
  Never edit the user's checkout.
- If the change system's CLI runs in a container (`make openspec-new NAME=<kebab>`), the directory
  it creates is owned by **root** (the container writes as uid 0). Your first `write_file` into it
  fails `Permission denied`. Fix immediately, before writing anything:

  ```bash
  sudo chown -R "$(id -u):$(id -g)" openspec/changes/<kebab>
  ```

## 2. The leg itself

- One project skill at `.hermes/skills/<leg>/SKILL.md` with `## Inputs`, `## Output` (the ONE file
  it may write) and `## Rules`; frontmatter `name:` must equal the directory name.
- The make leg: `require_env.py <KEYS>` as the FIRST recipe line, the agent image, and the stream
  through the redaction macro (`$(call scrubbed_run,…)`). The inline prompt is a pointer plus this
  run's parameters — keep it well under the repo's budget (llgenie: 400 chars).
- Two make targets per leg minimum: the deterministic `-brief` and the agent leg, plus the
  deterministic `-publish`. The publish step is the ONLY thing that writes GitHub state.
- Add every new target to `.PHONY:` and to the user-facing help/`##` line, and document it in the
  docs page the repo's docs gate reads (automation targets belong in the bots doc, not the README).
- Add a row to the repo's agent-skill index (`.hermes/skills/README.md` in llgenie).
- Run the repo's skill gate if it has one (`make check-agent-skills`): it refuses a missing `-s`, an
  unknown skill name, a name/directory mismatch, a missing section, or an over-long prompt.

## 3. The workflow

- **Copy the trigger guard VERBATIM from an existing workflow.** Repos that pin one guard body
  byte-identically (a test YAML-dumps each step's `name`/`env`/`run` and asserts ONE distinct body)
  refuse a hand-written variant even when the logic looks the same. Extract it programmatically from
  a sibling workflow rather than retyping it.
- **The cron minute must be an odd minute no other bot owns.** A pipeline-isolation test expands every
  schedule into `(minute, weekday)` slots and fails on a collision — pick from the free odd minutes
  and state why in a comment.
- **Every secret-spending step behind the deterministic decision** (`if: steps.brief.outputs.action ==
  'review'`), so the scheduled run costs nothing when there is no work.
- Only `make` targets run (`grep -n "python3 scripts/" <workflow>` must be empty); the only upload is
  the REDACTED transcript.
- If the repo GENERATES a dispatch table in its docs, regenerate it with the repo's own report target
  and splice it between the markers programmatically — never hand-edit the rows.
- `make check-workflows` / `check-dispatch-forms` / `check-docs` / `check-wiring` are the fast gates;
  run all four before the suite.

## 4. Run inputs (the scratch files the leg reads and writes)

A repo that enforces "every bot run input is gitignored" keeps a roster test (in llgenie:
`tests/test_bot_scratch_ignored.py`) plus a block in `.gitignore`. A new leg's files must be added to
BOTH, inside the roster's own block region (the test parses the block between its markers), or the
suite fails on `git check-ignore` returning non-zero for your file.

## 5. Verifying

- Run the new test file alone in the test container first — from a worktree you MUST also mount the
  parent repo at its real path (the `.git` file points there), exactly as the Makefile's
  `WORKTREE_MOUNT` does. A fast hand-run is `docker run --rm -u root -v "$PWD":/repo:rw -v "<parent
  repo>":"<parent repo>":rw -w /repo <test-image> python -m pytest tests/<file> -q`; skipping the
  second mount makes every git-dependent test fail with `not a git repository: …/worktrees/…`.
- Tick the change's `tasks.md` boxes AFTER the work is verified, then re-run the tasks gate: the
  loop's `openspec-tasks` stage exits 2 on any `- [ ]`, which looks like a code failure and is not.
- Run the full loop/gate in the BACKGROUND with a log file and read its `EXIT=`/`RESULT:` line; a
  12-40 minute suite outlives a foreground tool call.

## 6. Landing

- `git remote -v` BEFORE the first push: agent clones often have `origin` = UPSTREAM and the personal
  fork under another name (`fork`). Pushing a feature branch to upstream creates a stray branch there;
  delete it (`git push origin --delete <branch>`) and push to the fork.
- PR base = upstream, head = `<fork-owner>:<branch>`.
- After the repo's CI merges it, verify the landed content (`git log origin/main -1`, the files exist
  on the merge tree) and that the body's closing keyword closed the issue.
