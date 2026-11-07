# Running the unit suite and OpenSpec gates WITHOUT the container

Fallback for when `docker run … llgenie/test` cannot start (e.g. a full `/tmp` tmpfs — see the
inode check below), and for telling a PRE-EXISTING host failure from one your change caused.
Everything here was measured green at ~131 tests passed on a real llgenie branch; it is a working
method, not a guess.

## First: is `/tmp` unusable?

When docker/containerd fails to unpack or pytest exits `2` with NO output at all, check inodes, not
bytes — `df -h` can show gigabytes free while writes still fail:

```
df -i /tmp        # 100% => inode exhaustion; df -h /tmp still shows free space
```

Do NOT delete another lane's build artefacts to reclaim inodes (a probe dir can hold 100k+ files and
belong to a running build). Redirect your OWN temp to the roomy root filesystem instead:

```
mkdir -p ~/.cache/tmp
export TMPDIR=~/.cache/tmp
export PYTHONPYCACHEPREFIX=~/.cache/pyc
```

pytest writes its scratch under `TMPDIR`; a full/inode-exhausted `TMPDIR` makes it exit `RC=2`
with the terminal showing nothing. If output looks empty, redirect to a file and read it:
`python -m pytest … > ~/.cache/tmp/run.txt 2>&1; echo rc=$?` then `read_file` it.

## Local venv (pytest + the conftest's imports)

`tests/conftest.py` imports `scripts.llgenie_serve` at COLLECTION time, which needs `gguf` (and
numpy). A bare venv with only pytest dies in collection with silent `RC=2` and no traceback — that
is a missing-dependency collection crash, not a test failure. Install both:

```
<somepython -m venv ~/.cache/pytest-venv
~/.cache/pytest-venv/bin/pip install -q pytest gguf numpy
TMPDIR=~/.cache/tmp PYTHONPYCACHEPREFIX=~/.cache/pyc ~/.cache/pytest-venv/bin/python -m pytest tests/test_agent_profiles.py -q
```

If a `python -m pytest` run hangs or dies before writing output even with a roomy TMPDIR, wrap
`pytest.main([...])` in `try/except SystemExit` — a collection error is raised as `SystemExit`, which
swallows every print after it; catching it prints the real error.

## Deselect PRE-EXISTING host failures, never "fix" them

Some gate tests compare the committed tree against the LIVE host (`~/.hermes/profiles/`) and red on
host drift that has nothing to do with your branch (e.g. `test_committed_tree_passes_the_gate`).
Before blaming your change, prove the failure is pre-existing:

```
git stash                     # or `git stash -u`
<pytest the same tests on base>   # identical failures => environmental, not yours
git stash pop
```

Then run green by deselecting them explicitly and SAY SO in the PR body (`131 passed, 7 deselected —
pre-existing live-profile-drift tests that fail identically on base`). Editing such a test to match
one host is the wrong fix; it bakes host state into the suite.

## OpenSpec without the container

The Makefile's `openspec-validate` falls back to an npm install; do the same to a USER prefix (no
root, no system pollution):

```
npm install -g @fission-ai/openspec@<version> --prefix ~/.local
~/.local/bin/openspec validate --changes    # summary line: 'N passed, 0 failed'
```

Scaffolding trap: `openspec new change <name>` under the spec-driven schema emits ONLY
`.openspec.yaml` — it does NOT author the three files the validator/gate expect. Write them by hand
to match a recent change:

```
openspec/changes/<name>/proposal.md
openspec/changes/<name>/specs/<capability>/spec.md   # one G/W/T scenario per requirement
openspec/changes/<name>/tasks.md                     # one '- [ ]' per step
```

Ticking `tasks.md` is not optional: an ACTIVE change with unchecked boxes reds `make ci-openspec`.
Tick each box the moment its work is verified (see `references/openspec-change-conclusion.md`).

## Never run the full suite in a FOREGROUND call of any kind

The hermetic suite takes 6-8 minutes. Both foreground paths kill it mid-flight: an `execute_code`
cell dies at its ~300 s cap, and a foreground `terminal` call is cut at the runtime foreground cap
(~420 s) even when you pass a larger `timeout`. When that happens the docker container is torn down
with the run still inside it — you get no summary line and no exit code, and a run that had already
reached 96% is simply lost. Launch every full-suite run as a background terminal process
(`background=true, notify=[...]`) writing to a log, then poll the log and quote the `N passed` line
and the captured `rc=`. Do not report a truncated foreground tail as a verdict in either direction.

Append a machine-readable sentinel as the LAST line of the background command so completion is a
grep, never a judgement about the tail:

```
make test-unit > /tmp/<id>_tu.log 2>&1; echo "TU<id>_RC=$? HEAD=$(git rev-parse HEAD)" >> /tmp/<id>_tu.log
```

Then `grep -c 'TU<id>_RC=' log` — `1` means finished, `0` means still running (a live log's tail
looks identical mid-run and complete at 100%, and repeated `sleep`+`tail` probes burn turns without
answering the only question that matters). The sentinel also records the head sha, so a verdict can
never be silently attributed to the wrong commit after a move.

## A docker run started before a rebase reads a LIVE mount — discard its verdict

`docker run -v "$PWD":/repo` bind-mounts the worktree, so a full-suite run that
started BEFORE you rebase/force-push/amend/edit a file is reading files that change
under it mid-iteration: its reds/greens describe a mixed tree spanning two states, not
any single one. Do not trust that run's verdict, and do not cancel it to free the slot
(canceling mid-flight is churn) — let it conclude and treat the result as
discarded. The real-tree docs gates (`test_changes_index.py`, `test_check_docs.py`)
are the tell: they re-read the worktree live, so a fragment/`CHANGES.md` you fix and
amend in DURING the run makes the in-flight run report `is not a row` / `is not
indexed` on a file you have since corrected — a phantom, not a defect. To tell a
phantom from a real red WITHOUT re-running the whole 6-8 min suite, re-run just the
failed test FILES in-container at the committed head — it reads the same live tree
and takes seconds:

```
docker run --rm -u root -e PYTHONPATH=/repo/scripts -v "$PWD":/repo:rw -w /repo \
  llgenie/test:latest python -m pytest tests/test_changes_index.py tests/test_check_docs.py -q -p no:cacheprovider
```

Green there while the full run red the same files == the race; chase only if it still
reds. Serialise heavy edits against a running full-suite gate rather than editing into
it. The authoritative full-suite verdict is the pushed-head CI matrix
(`linux/unit` runs the same `make test-unit`). Before launching ANY local full run,
first check whether `linux/unit` at your CURRENT head already completed green —
`gh api "repos/asimov-agent/llgenie/actions/runs?head_sha=<full-sha>"` then the
run's `/jobs` for the `linux / unit` conclusion; a duplicate local run that starts
seconds before you discover CI is already green buys nothing and muddies the report.

## Test-writing gotchas that cost a cycle here

- `capsys.readouterr()` CLEARS the buffer — read it once and assert on that variable; a second call
  returns empty and looks like the code printed nothing.
- Code that prints via `print(..., file=sys.stderr)` is caught by pytest's `capsys`, NOT by a
  hand-rolled `contextlib.redirect_stderr` over an inert `StringIO` in a helper — use `capsys`.
- A stub that matches a recorded argv uses LIST MEMBERSHIP per element, never substring search on the
  list: `"check-runs" in argv` asks whether some element EQUALS `"check-runs"`, so it never matches a
  URL element like `repos/o/r/check-runs` and the branch silently falls through to the empty-response
  path, making a correct implementation look like it made no call. Use
  `any("check-runs" in a for a in argv)` (or compare the whole argv) — and when a stub-test reds
  unexplained, print the recorded argv instead of guessing at what the code sent.
