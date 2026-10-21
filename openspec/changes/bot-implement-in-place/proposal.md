# The bot's implementer runs in place: `/repo` is the only tree it can write

## Why

`AGENTS.md` tells every agent to work in its own git worktree, from the repo root:

```bash
mkdir -p ../llgenie-wt
git worktree add -b feat/<kebab> ../llgenie-wt/<kebab> origin/main
```

`make implement-issue` runs the agent in a container with exactly one writable mount and `--rm`:

```
$(RUNTIME) run --rm --init -v "$(CURDIR):/repo" -w /repo … $(AGENT_IMAGE) bash -lc 'make _implement-issue'
```

Inside that container `../llgenie-wt` resolves to `/llgenie-wt`, **outside the mount**. The first real
run followed the instruction literally and reported success. From run
[39513850754](https://github.com/asimov-agent/llgenie/actions/runs/39513850754):

```
[agent] Verification rerun as a clean test command: `pytest -q tests/test_hermes_smoke.py`
        -> `8 passed in 0.04s` (worktree `/llgenie-wt/hermes-smoke-tool-call`).
[agent] The task-relative change remains in place and committed at `ad266c6`: …
```

`ad266c6` never existed on the host. Measured for real on this host, with the same image geometry:

```
$ docker run --rm -v "$PWD":/repo -w /repo alpine:3 \
    sh -c 'mkdir -p ../llgenie-wt/probe && echo lost > ../llgenie-wt/probe/f'
inside the container it exists: lost
$ ls ../llgenie-wt/probe
ls: cannot access '../llgenie-wt/probe': No such file or directory
$ docker run --rm -v "$PWD":/repo -w /repo alpine:3 sh -c 'echo kept > /repo/.mount-probe'
$ cat .mount-probe
kept
```

So the leg's only correct behaviour — edit `/repo` in place — is the one its instructions forbid, and
`--rm` turns the mistake into silence (issue #426).

## What Changes

- **`Makefile` `_implement-issue`** — the prompt states the container contract as a hard rule: the
  agent runs inside the container, `/repo` is the only writable checkout and the tree this job commits,
  so it edits in place and does **not** create a git worktree (AGENTS.md's worktree rule is for a host
  agent, which is not what this leg is), and does not commit or push.
- **`tests/test_bot_in_place.py` (new)** — the recipe must carry that rule, and the leg must mount
  exactly one writable tree at `/repo` with `-w /repo` (a second mount of the parent, or a prompt that
  points the agent elsewhere, reds `make test-unit`).
- **`README.md` + `agent-wiki/`** — the container contract, so the next reader does not "fix" the prompt
  back to the host rule.

## Impact

- The worktree a bot agent creates (if it ignores the prompt) is no longer a silent success:
  `make issue-bot-changed` measures `/repo` and the job fails loudly when nothing changed (that gate is
  #428; this change removes the reason the agent would write elsewhere in the first place).
- The host-agent workflow in `AGENTS.md` is untouched — it applies to an agent with a real filesystem
  and a user's checkout, not to a `--rm` container with one mount.
