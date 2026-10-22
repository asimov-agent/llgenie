# 2026-10-22 — Strata's live download checks leave the hermetic unit gate (#437)

## What the issue said

Issue #437 (filed by the run-failure reactor) tracked `macos / unit` red on `08983fa96d5c`: `make ci-unit`
ended with

```
4889 passed, 3 deselected, 9 errors in 5154.33s (1:25:54)
```

and every error was the same fixture:

```
subprocess.CalledProcessError: Command '['git', '-C', '…/strata0/src', 'fetch', '-q', '--depth', '1',
'https://github.com/Niko1221/Strata', '16374b3e…']' returned non-zero exit status 128.
```

## Diagnosis

`tests/test_strata_download.py` was in the hermetic gate, and it is not hermetic. Its session fixture
`strata_src` calls `strata_models.checkout()`, which shallow-fetches Strata's pinned commit over git; the
`setup_py` fixture imports that checkout, `strata_python` pip-installs its requirements, several cases read
the live Hub at Strata's pinned revisions, and the last one runs Strata's real `serve/server.py`. The tree
was fine — GitHub dropped the fetch — so the gate reported a network hiccup as a defect in the change.

This is the same class issue #438 fixed for `tests/test_trend_pick.py`: the gate every change runs must not
leave the machine, and work that does gets its own target recorded in the roster
(`tests/fixtures/unit-suite.json`).

## Implemented

- `tests/fixtures/unit-suite.json` — `tests/test_strata_download.py` in `excluded`, with reason, issue
  #437, `decided` 2026-10-22 and `target: test-strata-live`. Discovery is unchanged; the file is the only
  thing that moves (93 of 109 files selected, 16 excluded).
- `Makefile` — `test-strata-live` runs the whole file in the test image with `-p no:cacheprovider`, is
  `.PHONY`, and carries a `##` help line. `make test-unit` no longer names it.
- `tests/test_strata_live_target.py` (new, hermetic) — four cases: the file is out of the gate, the target
  names it and is phony, the roster entry names issue #437 and its target, and the file still carries the
  concern the decision describes (the git fetch through `sm.checkout()` and the live-Hub repository).
- `README.md` — the hermetic-gate section and the command list document the new boundary and target.

## Verification

Run through the Makefile, on this host's Python 3.11 with the pinned deps (`gguf 0.19.0`,
`huggingface_hub 1.30.0`, `numpy 2.4.6`):

- `make test-unit` — **`5014 passed, 6 deselected in 606.70s`, exit 0**.
- `make lint`, `make check-registry`, `make skills-validate`, `make check-engine-params`,
  `make check-strata-models`, `make check-wiring`, `make check-docs` — exit 0 (the `ci-unit` stage list
  of issue #437, minus the container parts).
- `make openspec-validate NAME=strata-download-live-target` — `Change 'strata-download-live-target' is
  valid` (openspec CLI 1.10.0, the version the image pins).
- `make test-strata-live` — **`30 passed in 15.15s`**, exit 0: the new target really runs the live file
  (git fetch of the pinned commit, the Hub revision reads, the pty picks and Strata's server), so the
  nine cases the gate used to red still run and pass when the network answers.
- `python3 scripts/check_openspec_tasks.py strata-download-live-target` — all tasks checked.
- `python3 scripts/unit_tests.py check` — `[unit-suite] OK 93 of 109 … 16 excluded … 6 node de-selected`.
- `tests/test_strata_download.py --collect-only` — **30 tests collected**, while `unit_tests.py list`
  names the file 0 times: the live cases still exist, they are only out of the hermetic selection.
- Red-before/green-after on the roster entry: with `excluded` entry removed the guard fails
  (`tests/test_strata_download.py is still in the hermetic gate`) and `unit_tests.check` refuses the
  target claim; restored, both pass.

**How the container gates were run here.** This agent container starts a docker daemon but the kernel
refuses what a container needs (`failed to register layer: unshare: operation not permitted`; a build
cannot mount its Dockerfile), so the image stages cannot start. The make targets were therefore driven
with `TEST_RUN=` (the same recipe, the host's Python 3.11 instead of `docker run llgenie/test:latest`)
and `MAKEOVERRIDES=` — the second is required because otherwise make propagates the `TEST_RUN=`
command-line override into the child `make` that `tests/test_rebase_bot_gates.py` spawns, and that child
then legitimately reports a recipe without the container mount. That was observed as one spurious
failure before the override was contained. The Linux container form itself, and
`make openspec-validate` through its container branch, run in CI.

## Relation to other work

- Follows the pattern of `unit-gate-hermetic` (issue #438); complements it rather than superseding it.
- Related gap filed separately as #519: `make check-strata-models` (same `ci-unit` job) also fetches the
  same pinned commit over git, so a GitHub fetch failure can still red that job through a different step.
