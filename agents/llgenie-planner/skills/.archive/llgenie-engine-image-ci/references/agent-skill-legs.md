# Bot legs load their contract from a Hermes project skill

Use this when a bot leg's rules live in an inline `hermes -z "…"` prompt (or a `*_rules.md`
concatenated into it) and should become a file the agent loads. Applies to every llgenie agent leg,
and to any repo with Hermes-driven legs.

## Shape

- One skill per leg at `<repo>/.hermes/skills/<name>/SKILL.md`, preloaded with
  `hermes -z "<pointer>" -s <name>,bot-unattended …`.
- `bot-unattended` carries the shared unattended contract ONCE (never ask, never wait; exit 3 means
  "asked for input", not "changed nothing"); every leg preloads it beside its own skill.
- Each skill has exactly three sections: `## Inputs` (files the host prepared), `## Output` (the ONE
  file the leg may write — the deterministic step after the agent does every GitHub write), and
  `## Rules`.
- The leg's inline prompt is a POINTER plus that run's parameters (input path, output path, `$(URL)`,
  `$(DOC)`), sized in the low hundreds of characters. The rules are not restated there.
- Adding a leg means adding a skill and a `-s` list. `skills/engines/` is NOT this: engine skills are
  read by `generate-engine-params` and are never loaded by an agent.

## Registration: use `skills.external_dirs`, not project trust

- Hermes reads skills from `$HERMES_HOME/skills` and from `skills.external_dirs`.
- Project discovery (`skills.trusted_project_dirs`, `.hermes/skills` under a trusted root) needs a
  recent CLI; the repo's pinned `hermes-agent==0.19.0` (also PyPI's latest) does NOT have it, so the
  leg would preload nothing and report success. `external_dirs` works on both and needs no cwd, so
  it is the one seam.
- Register the path the leg actually runs in (`/repo/.hermes/skills`), once, at image build time, and
  read the value back so a registration that did not land fails the BUILD, not a bot run.
- **Do not set it with `hermes config set`.** The value parser differs by version: a newer CLI
  refuses a bare string ("must be a list"), while 0.19.0 stores `'["/x"]'` as an opaque STRING that
  `get_external_skills_dirs()` turns into one non-existent path. Write a real YAML list with a small
  script (merge, dedupe, idempotent, `--check`, exit 2 on an unreadable config) and assert the result.
  A `COPY`ed helper script must also join the image's hash-input list in `scripts/ci_images.py`, or
  the image tag will not move when the script changes.

## Prove the load; do not infer it from a green gate

`agent.skill_commands.build_preloaded_skills_prompt([names])` is the function `hermes -z … -s` calls
before the first turn (see `hermes_cli/oneshot.py::_build_preloaded_skills_prompt`). It returns
`(prompt_text, loaded_names, missing)`. Drive it directly:

1. Build a throwaway `HERMES_HOME` and register the repo's skills with the same script the image runs.
2. Point `HERMES_HOME` at it and feed each leg's `-s` list.
3. Assert `missing == []`, every name in `loaded`, the preload preamble
   (`Treat its instructions as active guidance`) is present, and each skill's `description` appears in
   the rendered prompt — that is the content, not just the name.
4. Negative case: an unregistered home returns every name as missing and an empty prompt; that is the
   failure the build-time registration prevents.

Pitfalls:

- With `external_dirs` the proof is cwd-independent. With PROJECT discovery it is not:
  `find_project_root()` reads `resolve_agent_cwd()` (session cwd, then `TERMINAL_CWD`, then process
  cwd), so a test must pin `TERMINAL_CWD` or it silently resolves no project. A worktree `.git` FILE
  is accepted; the env ladder is the trap.
- Run it where hermes-agent is importable and make a missing import a LOUD failure, never a skip. The
  repo's `agents-read` venv (`make agents-read-venv`) is the natural home; the hermetic test image
  ships no hermes-agent.
- `format_missing_skills` exists only in newer trees; do not import it from the pinned venv — format
  `missing` yourself.

## A structural gate keeps the seam from rotting

Add a stdlib checker (wired to a make target in `ci-unit`, `.PHONY`, a `##` help line, README) that
fails: a leg with no `-s`; a name with no `SKILL.md`; frontmatter `name` != directory; a skill missing
`Inputs`/`Output`/`Rules`; a prompt over a fixed pointer budget; the unattended contract inlined in a
prompt; a skill no leg preloads; the retired rules file returning; and an `AGENTS.md` that no longer
states the rule. Prove each failure shape RED against a fixture tree, driving the real checker — a
happy-path-only suite passes on the defect it exists to catch.

## Moving a contract breaks tests that pinned the prompt text

`grep -rn` the test tree for the old prompt phrases before finishing. Tests asserting "the prompt says
X" will red; update each to assert the leg preloads the skill AND that the skill file carries the
rule. Deleting the assertion drops the lock the original change bought.

## Container-created dirs are root-owned

`make openspec-new` (and any containerized generator) leaves the change dir root-owned, so
`write_file` into it fails with EPERM. `sudo` cannot prompt in the agent shell; chown through a mount
instead: `docker run --rm -v "$PWD/openspec/changes":/c alpine chown -R "$(id -u):$(id -g)" /c/<name>`.
