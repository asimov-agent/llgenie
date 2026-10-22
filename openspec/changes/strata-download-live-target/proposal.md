# Strata's live download/serve checks get their own target

## Why

`macos / unit` went red on `08983fa96d5c` (issue #437) with nine errors, every one of them the same
cause — the session fixture in `tests/test_strata_download.py` leaves the machine:

```
ERROR tests/test_strata_download.py::test_every_choice_file_name_is_what_setup_py_builds_and_maps_back
  - subprocess.CalledProcessError: Command '['git', '-C', '…/strata0/src', 'fetch', '-q', '--depth',
    '1', 'https://github.com/Niko1221/Strata', '16374b3e…']' returned non-zero exit status 128.
4889 passed, 3 deselected, 9 errors in 5154.33s (1:25:54)
```

`strata_src` shallow-fetches Strata's pinned commit over git; `setup_py` imports it; `strata_python`
pip-installs its requirements; other cases read the live Hub at Strata's pinned revisions and run the
engine's real `serve/server.py`. The tree was fine — GitHub refused or dropped the fetch — and the gate
that every change runs reported it as a defect in the change.

`make test-unit` is documented as the hermetic gate (issue #438 excluded the live-Hub checks from
`tests/test_trend_pick.py` for exactly this reason). `tests/test_strata_download.py` is the same class of
work and was never moved out, so any network hiccup on GitHub or the Hub reds a gate that is supposed to
be reproducible offline.

## What Changes

- **`tests/fixtures/unit-suite.json`** — `tests/test_strata_download.py` is recorded in `excluded` (a
  dated decision: reason, issue #437, date, owning target), so discovery keeps it out of the hermetic
  suite. Discovery is unchanged, so the file is the only thing that moves.
- **`make test-strata-live`** — the target that owns it: runs the whole file in the test image, `.PHONY`,
  with a `##` help line and a README entry.
- **`tests/test_strata_live_target.py` (new)** — pins both halves hermetically: the file is out of the
  gate the aggregator computes, the target names the file (no `-k`), it is `.PHONY`, and the file still
  contains the live-fetch fixture it was excluded for (so a rewrite back to a hermetic file has to move
  the decision with it).
- **`README.md` + `agent-wiki/2026-10-22-strata-download-live-target.md`** — the boundary and the target.

## Impact

- `macos / unit` and the Linux unit job no longer depend on GitHub serving an arbitrary sha or on the Hub
  answering: the gate is hermetic again, as it is documented to be.
- The Strata checks still run, with their own name, on demand: `make test-strata-live`.
- No test is skipped or deleted: the nine cases keep running, just through the target that owns them.
