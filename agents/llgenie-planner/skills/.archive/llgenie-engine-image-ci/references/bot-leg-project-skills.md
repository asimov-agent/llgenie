# Bot legs load their contract from a Hermes project skill

Companion to the `llgenie` skill. The repo moved every bot leg's rules out of
the inline `hermes -z "…"` string and into `.hermes/skills/<name>/SKILL.md`,
preloaded with `-s <name>,bot-unattended`.

## The skills

| skill | leg |
|---|---|
| `bot-unattended` | shared: never ask, never wait, decide and report |
| `issue-triage` | the decision leg (implement / refine / close) |
| `issue-refiner` | the review leg |
| `issue-dedup` | the duplicate-pair leg |
| `issue-implement` | the implementation leg |
| `architecture-doc` | the docs rewrite leg |
| `agent-fetch` | the masked Firecrawl fetch leg |
| `rebase-conflict` | the conflict-resolution leg |
| `pr-fix` | the fix-bot loop (replaces `scripts/fix_bot_rules.md`) |

Each has `## Inputs`, `## Output` (the ONE file it may write) and `## Rules`.
The inline prompt is a pointer plus that run's parameters, kept under 400
characters.

## Registration

`scripts/hermes_skills_register.py` writes `/repo/.hermes/skills` into
`skills.external_dirs` of the Hermes home as a real YAML list (the pinned
`hermes-agent==0.19.0` misreads a JSON literal from `hermes config set` as one
opaque directory and resolves nothing). `scripts/install_hermes_ci.sh` runs it
at image build time and `--check`s the value back.

## Gates and tests

- `make check-agent-skills` (`scripts/check_agent_skills.py`, in `ci-unit`): a
  leg with no `-s`, an unknown skill name, a name/directory mismatch, a missing
  section, an over-budget prompt, an inlined unattended contract, an unclaimed
  skill, or a returned `scripts/fix_bot_rules.md`.
- `make agent-skills-report` prints every leg with its prompt size and preload
  list, and every skill with its frontmatter.
- `tests/test_agent_skills.py`: every failure shape against fixture trees, plus
  the real registration script.
- `make test-agent-skills-live`: feeds each leg's `-s` list to
  `agent.skill_commands.build_preloaded_skills_prompt` against a home
  registered by the image's own script; asserts every name resolved and each
  skill's description reached the rendered prompt; plus the negative
  (unregistered home resolves nothing). Run where hermes-agent is importable
  (the `agents-read` venv), not in the hermetic test image.

## Pitfalls specific to this repo

- Running a hand-rolled `docker run -v "$PWD":/workspace …` from a git
  **worktree** breaks every `git` call inside the container: the worktree's
  `.git` file points at the absolute host path and the container does not mount
  it. The Makefile's `WORKTREE_MOUNT` handles this; `make test-unit` works,
  manual docker does not.
- Tests that asserted literal rules in the inline prompt were repointed at the
  skill file. The skill is canonical — align the test to the skill's wording.
- `git` as root in a mounted volume returns 128; use
  `git -c safe.directory=<path>` rather than changing global config.
