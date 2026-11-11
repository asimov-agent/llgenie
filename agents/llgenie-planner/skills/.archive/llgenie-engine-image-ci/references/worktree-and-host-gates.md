# Working across worktrees, and testing host-branched recipes

## One worktree per change, absolute paths in scripts

Every change is cut in its own worktree (`../llgenie-wt/<kebab>`) and the host checkout is left
alone. When a script or `execute_code` call edits files, give it ABSOLUTE paths into the
worktree — a relative path resolves against the process cwd (the host checkout), so a scripted
multi-file edit lands in the wrong tree and dirties the user's clone.

After ANY scripted edit, prove where it landed:

```bash
git status --porcelain            # in the worktree: the files you meant
git -C /path/to/host/clone status --porcelain   # must be empty
```

Recovery is `git checkout -- <paths>` in the host clone — the edit is reproducible from the
script, so throw it away rather than merging it forward.

The OpenSpec CLI runs as root inside its container, so a new change directory lands root-owned
and the first write fails with `Permission denied`. Fix ownership by running the chown INSIDE a
container over the bind mount (`docker run --rm -v "$PWD":/w -w /w llgenie/test:latest chown -R
"$(id -u):$(id -g)" <path>`) — `sudo` may not be available non-interactively.

## A `make -n` recipe is host-branched

`TEST_RUN` / `TEST_OPTS` are defined under `ifeq ($(HOST_OS),Darwin)`: Linux expands a recipe to
a container run with `-v "<checkout>":/repo:rw` and the test image, macOS to a native venv
command with no volume at all. A test asserting the container form therefore CANNOT pass on a
macOS runner — assert the invariant where both hosts resolve it, and the recipe shape per host.

Read a variable the way make resolved it (works on both hosts, because most of these are
defined outside the branch):

```python
for line in make("-p", "-n", "lint").splitlines():
    if line.startswith(f"{name} ") and "=" in line:
        return line.split("=", 1)[1].strip()
```

and then branch the recipe assertion on `platform.system() != "Darwin"` (container shape) vs
Darwin (no volume, no image, the script still named).

## Simulate the other host locally

A makefile `:=` assignment overrides the environment, so `HOST_OS=Darwin make …` changes
nothing. Use `make -e HOST_OS=Darwin -n lint` (env precedence restored) to see the Darwin
expansion, and drive a misbehaving test's own branch by patching both inputs in one throwaway
script:

```python
import platform, subprocess
platform.system = lambda: "Darwin"
_orig = subprocess.run
def run(args, **kw):
    args = list(args)
    if args and args[0] == "make":
        args = ["make", "-e", "HOST_OS=Darwin", *args[1:]]
    return _orig(args, **kw)
subprocess.run = run
```

Run the OLD test against that simulation to prove it fails for the reported reason, and the new
one to prove it passes — a fix is not proven until both directions are shown.

## Byte-identical workflow steps

The repo keeps some steps (notably the trigger guard) byte-identical in every workflow, and a
test enforces it. Change the body ONCE in one file, then apply the same old/new strings to every
site and assert each file had exactly one occurrence:

```python
for p in sorted(workflows.glob("*.yml")):
    t = p.read_text()
    if t.count(OLD) == 0: continue
    assert t.count(OLD) == 1, p.name
    p.write_text(t.replace(OLD, NEW))
```

When a test slices the file with `split("make auto-merge")`, a newly added sibling target whose
name starts with the same prefix truncates the slice — split on the following `- name:` line
instead.
