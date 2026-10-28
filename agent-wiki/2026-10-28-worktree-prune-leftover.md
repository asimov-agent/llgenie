# worktree-prune-leftover — 2026-10-28

## What changed

- `scripts/worktree_prune.py`: a worktree `apply()` could not fully delete is a **leftover** — printed
  with its path, the reason, and the one command that clears it — and the branch is still deleted. A
  `Leftover` dataclass carries it; `Outcome.leftovers` holds them; `render()` prints
  `[worktree-prune] leftover <path> — <reason>; clear it with: <command>` and the summary gains
  `; N leftover(s)`.
- `apply()` no longer appends to `outcome.errors` for a failed worktree removal, so `main()` exits 0 for
  a run whose every planned action either happened or was reported as a keep/leftover. Exit 2 stays for
  a step that failed with no report (the `gh` lookup, an unexplained `git` call).
- `remove_worktree()` (new) clears debris through the container engine as root —
  `<runtime> run --rm -v <parent>:/wt <image> rm -rf /wt/<name>`, `LLGENIE_DEBRIS_IMAGE` overridable,
  `nerdctl` first then `docker`, `RUNTIME` wins — and retries `git worktree remove` once. When the engine
  is absent or refuses, the leftover is reported instead (a missing runtime is a `False`, never a
  traceback).

## Why

`make worktree-prune` unregistered a merged worktree, deleted nothing else and exited 2 when the
directory held `root:root` files a containerized `make test-unit` run left behind (#433). The sweep's own
exit code then read as "the prune is broken" while the branch delete had been the only thing missing —
the same class of confusion #593 fixed for a `git branch -D` refusal.

## Decisions

- **A directory that survives is a leftover, not an error.** The plan's intent (`prune this merged
  branch`) is either done or honestly reported; the exit code answers "did every planned action happen
  or get named", which is the only question a post-merge sweep can be trusted for.
- **The debris is deleted by the engine that created it.** `docker`/`nerdctl` `run --rm -v … rm -rf` is
  the same privilege boundary the container run used, so the common case needs no `sudo` and no human
  step, and the printed fallback command is byte-identical to what the sweep tried.
- **No `--force` on a worktree the planner called clean.** A removal failure can also mean the tree went
  dirty between the plan and the apply; forcing it would delete work the keep-rule exists to protect.
  The branch delete then hits git's `used by worktree at` refusal and lands on #593's keep path.
- **Tests use the `gh` seam, not permissions.** The sweep reads the worktrees before `gh pr list`, so a
  stub that removes the worktree's git registration reproduces the measured "unregistered, directory
  survives" shape on any host — including a container running as root, where `chmod` proves nothing.

## Gates

- `make test-unit` — green (5 new/updated cases in `tests/test_worktree_prune.py`).
- `make check-wiring`, `make check-docs` — green.

## Related

- Issue [#759](https://github.com/asimov-agent/llgenie/issues/759) · #431 (the sweep) · #593 (`apply()`'s
  keep path) · #433 (root-owned files from container runs) · #432 (fork-branch deletion, out of scope).
