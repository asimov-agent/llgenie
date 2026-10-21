# The bot's implementer edits the mounted tree in place

- Issue: [#426](https://github.com/asimov-agent/llgenie/issues/426)
- OpenSpec change: `bot-implement-in-place`
- Branch: `fix/bot-implement-in-place`

## What was wrong

`AGENTS.md` tells an agent to work in `../llgenie-wt/<kebab>`. `make implement-issue` runs Hermes in a
`--rm` container with one writable mount: `-v "$(CURDIR):/repo" -w /repo`. Inside it, `../llgenie-wt` is
`/llgenie-wt` — outside the mount — so the first real run built the whole `hermes-smoke` tool-call
implementation there, "committed" it as `ad266c6`, reported success, and the host never saw it when the
container exited (run 39513850754).

## What changed

- `Makefile` `_implement-issue` — hard rule (5): the agent runs inside the container, `/repo` is the only
  writable checkout and the tree this job commits, so it edits in place and must **not** create a git
  worktree (AGENTS.md's worktree rule is for a host agent, which this leg is not); committing, pushing
  and touching `main` stay forbidden.
- `tests/test_bot_in_place.py` — the prompt carries that rule, the leg mounts exactly one writable tree
  (`-v "$(CURDIR):/repo"`, `-w /repo`) and hands the agent no path outside it, and the job still owns
  commit/push.
- `README.md` — the container contract next to the implementer's command list.

## Verified

Measured on this host with the same image geometry:

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

- `pytest tests/test_bot_in_place.py` → 3 passed.
- `make test-unit`, `make lint`, `make check-docs`, `make check-wiring`,
  `make openspec-validate NAME=bot-implement-in-place` — green.

## Notes

- The prompt is the fix, and #428 is the backstop: `make issue-bot-changed` measures `/repo`, so an agent
  that still writes elsewhere cannot be reported as a success — the job fails loudly naming the issue.
- The host-agent worktree rule in `AGENTS.md` is deliberately untouched: a `--rm` container with one
  mount is not a host agent, and the prompt now says where the difference is.
