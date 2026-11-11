# When a test asserts an OS-branched make recipe

llgenie runs the same stage two ways. `Makefile` sets `HOST_OS := $(shell uname -s)` and
`ifeq ($(HOST_OS),Darwin)` picks the native 3.11 venv (`VENV_GUARD` + `python ...`) while
Linux expands the same variable to `$(RUNTIME) run $(TEST_OPTS) $(TEST_IMG)` — a container,
`TEST_OPTS` carrying the volume mount, `llgenie/test:latest` the image. `engine_test` and
`ENGINE_TEST_RUN` branch the same way.

A test that asserts the *shape* of an expanded recipe (`make -n <target>`) therefore encodes
one host's shape. On a Linux dev box it passes, `linux / unit` passes, and the defect only
appears in `macos / unit` — the last job to finish, ~25 minutes in. Treat a PR as unverified
until BOTH unit jobs are green: `gh run view <run> --json jobs` and read `linux / unit` AND
`macos / unit`, never just the conclusion of the job you happened to open.

## Rule

Branch the assertion the way the Makefile branches, and put the shared invariant where every
host resolves it:

1. **OS-neutral invariant → read the resolved variable, not the recipe.** `make -p -n <target>
   REPO=<slug>` dumps make's database on stdout; variables defined outside the `ifeq` block
   (`TEST_OPTS`, `ROOT`, `REPO`) are there on both hosts. Parse with
   `line.startswith(f"{name} ")` then `line.split("=", 1)[1].strip()` (works for `:=`, `=`, `?=`).
   `TEST_OPTS` is exactly what the container gate mounts, so `-v "<checkout>":/repo:rw` and
   "the slug is never a volume source" are checkable on Linux and macOS alike.
2. **Recipe shape → assert per host.** Container host: the checkout mount AND the test image
   appear in `make -n <target>`. Darwin: the native command appears and there is NO `-v ` and
   NO test image. Derive the branch from `platform.system() != "Darwin"`, the same source of
   truth the Makefile reads.
3. **Never weaken the assertion to fit both hosts** — keep the real mount/image check under the
   container branch and the "no volume exists here" check under the native branch. A test that
   asserts only the intersection of two shapes stops locking either one.

## Verifying the Darwin branch from a Linux box

`HOST_OS := $(shell uname -s)` is a makefile assignment, so an environment variable does NOT
override it (`make HOST_OS=Darwin ...` still takes the Linux branch). Environment only wins
with `-e`:

```bash
make -e HOST_OS=Darwin -n lint REPO=asimov-agent/llgenie   # the real macOS expansion
make -e HOST_OS=Darwin -p -n lint REPO=asimov-agent/llgenie | grep -E '^TEST_OPTS '
```

To exercise the test's own Darwin branch, patch the host detection and inject `-e` into every
`make` call, then run the OLD and the NEW test against the same real output:

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

Proving the previous test FAILS on that output and the new one PASSES is the verification: it
shows the assertion was wrong rather than the product behaviour. Report both results; "the
macOS CI job will tell us" is not verification.

## Bookkeeping the fix lands with

A host-shape fix is still a change: a spec scenario for the native host with its
`- **Test:**` line (name the `CONTAINER_HOST is False` branch and the `macos / unit` job when a
real Mac is what exercises it), the `tasks.md` items ticked, the `agent-wiki/` entry amended
(run id, the failing job, the cause), README untouched when no user-facing target changed, and
a short PR-body section naming the failing job and the new host split. The commit message
carries Issue / Fix / Benefit / Technical.

## Triage commands that got there

```bash
gh run view <run> --repo asimov-agent/llgenie --json jobs \
  -q '.jobs[]|select(.name|test("unit"))|.name+": "+(.conclusion//"-")'
gh run view <run> --repo asimov-agent/llgenie --job <job-id> --log-failed | tail -80
```

The last block of `--log-failed` holds the failing assertion, the `file:line` and the
`N failed, M passed` line — read the assertion text before theorising; a one-line
expected-vs-actual usually names the cause outright.
