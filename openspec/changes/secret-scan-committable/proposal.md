# `make secret-scan` scans what could be committed, not the whole filesystem

## Why

`_secret-scan` runs gitleaks in `dir` mode over the checkout:

```make
GITLEAKS_RUN := $(RUNTIME) run --rm -v "$$PWD":/repo -w /repo $(GITLEAKS_IMAGE)
_secret-scan:
	$(GITLEAKS_RUN) dir /repo --config /repo/.gitleaks.toml --redact --no-banner --exit-code 1
```

`dir` mode walks the filesystem and honours **no** `.gitignore`, so it reads build artifacts that
nobody can commit. Measured on `main@2e04fa3` with **no uncommitted change**, in a checkout that had
run `make test-unit`:

```
$ make secret-scan
6:43AM WRN leaks found: 2
SECRET SCAN FAILED: a credential shape is present in the working tree.
$ git check-ignore -v tests/__pycache__/test_scrub_log.cpython-311-pytest-8.3.5.pyc
.gitignore:2:__pycache__/	tests/__pycache__/test_scrub_log.cpython-311-pytest-8.3.5.pyc
```

The two findings are the suites' own deliberate sentinels, compiled into `tests/__pycache__/*.pyc`.
CI never sees them (a fresh runner has no cache), so this only ever bites the human who runs the
documented command — and it makes the one message that must never be ignored ("rotate the key") fire
on a cache directory. A real finding would sit in the same list.

The loop's own container runs as root (`docker run … -u root`), so those `__pycache__` trees are also
root-owned in the checkout — a second reason not to scan them.

## What Changes

- **`scripts/secret_scan.py`** computes the **committable set** — `git ls-files -z -c -o
  --exclude-standard` (tracked files plus untracked files that are not ignored, which is exactly what
  `git add` would take) — exports it to a temporary tree, and points the same pinned gitleaks image and
  the same `.gitleaks.toml` at that tree. `--list` prints the set; `--runtime` picks the container
  runtime, like the self-test already does.
- **`_secret-scan` calls it**, so the scan reports a finding only for content that could be committed.
- **`make secret-scan` keeps its contract**: non-zero on a credential VALUE in a tracked file, zero on
  a clean tree, and the remediation text unchanged.
- **Tests** (`tests/test_secret_scan.py`, hermetic, in `make test-unit`): the committable set includes a
  tracked file and a fresh untracked file, and **excludes** an ignored path — the regression that
  reddened the command — plus the real-tree case that no `__pycache__` path is in the set.

## Impact

- Affected specs: `secret-scan` (new capability in this change).
- Affected code: `scripts/secret_scan.py` (new), `Makefile` (`_secret-scan`), `tests/test_secret_scan.py`,
  `README.md`.
- `secret-scan-history` (`gitleaks git` over the real clone) is untouched: history is not a working tree.

## Not covered (each its own issue)

- Wiring `make agent-fetch` into a bot leg and the coverage report: #380 (separate work item).
- Rotating a live key a scan finds: a human action on the provider and the GitHub secret.
