# `make secret-scan` reads the committable set, not the whole filesystem

Issue #382 (follow-up of #357 / #360). OpenSpec change: `secret-scan-committable`. PR: #398.

## What was wrong

`_secret-scan` ran `gitleaks dir /repo` over the checkout. `dir` mode walks the filesystem and honours
no `.gitignore`, so it read gitignored build artifacts. Measured on `main@2e04fa3` in a checkout that
had run the tests, with no uncommitted change:

```
$ make secret-scan
WRN leaks found: 2
SECRET SCAN FAILED: a credential shape is present in the working tree.
```

Both findings sat in `tests/__pycache__/*.pyc` — the suites' own deliberate sentinels, compiled. CI
stayed green only because a fresh runner has no cache, so the false alarm fired at the human running
the documented command, and it made the "rotate the key" message untrustworthy.

## What changed

- **`scripts/secret_scan.py`** computes the **committable set** — `git ls-files -z -c -o
  --exclude-standard`, i.e. tracked files plus untracked files that are not ignored, exactly what
  `git add` would take — exports it to a temp tree, and runs the same pinned gitleaks image and the
  same `.gitleaks.toml` against that tree. `--list` prints the set; `--runtime` picks the engine.
- **`_secret-scan` calls the script.** `secret-scan` now separates the two non-zero exits: exit `1` is
  a finding (the remediation text), **any other** non-zero is "the scan could not run, and this is not
  a clean tree and not a finding" — measured while building this: a crash inside the script had been
  reported as *"a credential shape is present in the working tree"*, which is the same class of false
  signal this issue is about.
- `tests/test_secret_scan.py` pins the set (ignored path excluded; tracked and fresh untracked
  included), the real tree (no ignored path is ever in the set), and the wrapper's two messages.

## Measured before/after (real checkout, real container)

| case | `gitleaks dir` (old) | `make secret-scan` (new) |
|---|---|---|
| planted value in gitignored `tests/__pycache__/leaked.txt` | **found** (rc=1) | clean (rc=0) |
| planted value in an untracked, not-ignored file | — | **found** (script rc=1) |
| planted value in a tracked file | — | **found** (script rc=1) |
| clean tree | clean | clean (rc=0) |
| runtime missing | — | rc=2, "could not run", never clean |

## Verification

- `pytest tests/test_secret_scan.py` → 8 passed (in `llgenie/test:latest`).
- `make check-wiring`, `make check-docs`, `make check-workflows`, `make check-secret-output`, `make lint`,
  `make openspec-validate NAME=secret-scan-committable`, `make test-unit`.

## Note on the plant

The first plants were too weak to trip any gitleaks rule (low-entropy values), which made an early
"old scan found nothing" reading look like a fix that was already there. The proof above uses a
`GITHUB_TOKEN=<high-entropy value>` assignment, which the scanner catches as `generic-api-key` — a test
whose plant the scanner would not catch proves nothing.
