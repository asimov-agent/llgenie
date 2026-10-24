# Bot legs run on project skills (issue #577)

**Status:** implemented, gates green on the host-side targets; `openspec validate` needs the
container image (no Docker daemon in this run).

## What changed

Every `hermes -z` bot leg used to carry its contract as one inline Makefile string, plus a
~500-character unattended paragraph repeated in each. The contract is now a project skill under
`.hermes/skills/<bot>/SKILL.md`, preloaded with `hermes -s <bot>,bot-unattended`:

- `bot-unattended` — the shared contract once (never ask, a question fails the run, the path a
  genuinely open decision takes).
- `issue-triage`, `issue-refiner`, `issue-dedup`, `issue-implement`, `architecture-doc`,
  `agent-fetch`, `rebase-conflict`, `pr-fix` — one per leg, each with `## Inputs`, `## Output`,
  `## Rules`.
- `scripts/fix_bot_rules.md` is retired into `pr-fix`; the fix loop and the rebase prompt read the
  skill instead of concatenating rules.
- `scripts/install_hermes_ci.sh` trusts `/repo` (`skills.trusted_project_dirs`) and proves the
  write landed, because Hermes discovers project skills only under a trusted root.
- `make check-agent-skills` (`scripts/check_agent_skills.py`, in `ci-unit`) is the gate; its
  failure shapes are proved red by `tests/test_agent_skills.py`. `make agent-skills-report` prints
  the legs, their prompt sizes and each skill's sections.

## Key decisions

- **Pointer budget 400 chars** (`MAX_PROMPT_CHARS`): the real legs measure 7–186, so a rulebook
  creeping back into a recipe reds the gate without constraining a legitimate parameter list.
- **`bot-unattended` is required by every leg**, and its wording is forbidden in a prompt — the
  duplication this change removes is now a finding, not a convention.
- **The rule's home.** `AGENTS.md` is a protected agent-instruction file: Hermes refuses an
  unattended write to it and needs a human's approval by design. This run therefore records the
  durable rule in `docs/AGENT-SKILLS.md`; `make check-agent-skills` accepts `AGENTS.md` or that
  document, and still reds when neither carries it. A human should apply the same section to
  `AGENTS.md` and this note can then point at the rulebook.
- **Discovery was proved for real, once, outside the hermetic gate**: with a trusted `/repo`,
  `hermes skills list` lists all nine skills as `project` / `enabled`. That is a live Hermes run,
  so the gate itself asserts the image's config instead (the issue's stated out-of-scope line).

## Verification

- `make check-agent-skills` → `OK (8 legs, 9 skills)`; `make agent-skills-report` → `findings: 0`.
- `make check-wiring`, `make check-docs`, `make check-secret-output` → exit 0.
- The whole hermetic suite (the exact command `make test-unit` runs, `python3 scripts/unit_tests.py
  run`) → **5090 passed, 6 deselected in 730.31s**.
- `make check-workflows` → OK; `python3 scripts/lint_linefeeds.py` → `LINT OK`;
  `python3 scripts/check_bash.py` → OK. `make test-unit` / `make lint` themselves are `docker run`
  wrappers and this leg cannot run a container at all: no daemon runs, and a `dockerd` started with
  `--storage-driver=vfs --iptables=false --bridge=none` fails to register a layer with
  `unshare: operation not permitted`. Their underlying commands were run directly instead.
- `make openspec-validate NAME=bot-skill-contracts` could not run: the OpenSpec CLI is a container
  image (or npm on macOS) and this leg has neither Docker nor node/npm. The change's spec/tasks
  follow the repository's format and `make openspec-tasks-check NAME=bot-skill-contracts` passes.

## Follow-ups (separate work items)

- Apply the `docs/AGENT-SKILLS.md` rule section to `AGENTS.md` (needs a human-approved write).
- Shrink the rulebook now that bot contracts no longer live in `AGENTS.md` (the issue's own
  out-of-scope item).
- A live `-s` resolution smoke inside the agent image (the issue's second out-of-scope item).
