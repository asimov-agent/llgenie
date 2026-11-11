# Host vs container: what a make recipe expands to, and who owns the files it writes

llgenie runs one code path per stage, but on macOS that path is a **native venv**, not the test image.
`Makefile` sets `HOST_OS := $(shell uname -s)` and branches: Linux gets
`TEST_RUN := $(RUNTIME) run $(TEST_OPTS) $(TEST_IMG)` (with `TEST_OPTS` holding
`-v "$(ROOT)":/repo:rw`); Darwin gets `TEST_RUN := $(VENV_GUARD) env PATH="$(VENV)/bin:$$PATH"`.
Any test that reads an expanded recipe is therefore host-branched, and CI runs it on **both** OSes.

## Asserting a recipe without breaking macOS

- Assert the invariant where both hosts resolve it: `make -p -n <target> REPO=…` prints the resolved
  value of a variable (`TEST_OPTS`, `ROOT`, `REPO`), so `-v "<checkout>":/repo:rw` can be required of
  `TEST_OPTS` on Linux and macOS alike. Parse the first line starting with `<NAME> ` and take what
  follows the first `=` (`:=` included).
- Assert the recipe against the shape its own host runs: with `platform.system() != "Darwin"` require
  the image and the volume; on Darwin require that the same recipe carries **no** `-v` and no image and
  does name the script. A container-shape assertion on macOS is a guaranteed red `macos / unit`.
- Verify the Darwin branch on a Linux host by faking happens: `make -e HOST_OS=Darwin -n <target>`
  (`-e` gives the environment precedence, which a plain `HOST_OS=Darwin` does not — the makefile's `:=`
  beats the environment) and drive the test itself with `platform.system` patched plus `subprocess.run`
  rewritten to inject `-e HOST_OS=Darwin`. That proves the assertions against real make output instead
  of trusting your reading of the branch.
- Prove the regression, not just the fix: run the previous version of the test (`git show <rev>:<file>`)
  through the same simulation and show it fails where the new one passes.

## `make openspec-new` writes as root

The OpenSpec CLI runs in `llgenie/openspec` as root (`-u root`), so
`openspec/changes/<name>/` lands owned by root and a host write there fails with `Permission denied`.
Fix the ownership with the same runtime, not with hand-editing:

```bash
docker run --rm -v "$PWD":/w -w /w llgenie/test:latest chown -R "$(id -u):$(id -g)" openspec/changes/<name>
```

`sudo` may not accept a password in a non-interactive session; the container is the reliable route.

## Worktrees and remotes

A worktree created with `git worktree add -b <branch> <dir> origin/main` shares the parent clone's
remotes, so the fork push (`git push -u fork <branch>`) and a `gh pr create --repo <upstream>
--head <owner>:<branch>` work from the new directory with no extra setup. Reuse an existing worktree
for the same branch when `git worktree list` shows one; rebase it onto `origin/main` before touching
code.

Container-toolchain note: the host python venv (`~/llama-gguf-tools/.venv`) runs `pytest` and the
stdlib guards directly, which is enough for a focused re-run; a guard that itself builds a venv (see
`tests/test_wiring.py`) can fail on the host while CI's container is green — check it on a pristine
branch before blaming the change.
