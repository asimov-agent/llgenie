# A docs-only PR stops paying for the 28-job matrix

**Issue:** #824 (824a — the trigger-level selection and the classifier). **Measured:** 2026-10-28,
`origin/main@17cdcf36`.

## What was measured before the change

`ci.yml` runs one 28-job matrix for every pull request. Two docs-only PRs, the same floor:

| PR | diff | jobs queued |
|---|---|---|
| #767 | `docs/ARCHITECTURE.md` (one file) | 28 (`gh run view 40679882983 --json jobs`) |
| #825 | six markdown files + one OpenSpec change, `+150/−0` | 28 (run 40711614430) |

The only variable was how much documentation the author happened to touch, and every row — the four
`engine-base-*` builds, `scanner-images`, the published-image tests — was demanded by a diff that
cannot affect any of them.

## What the change does

1. **`scripts/ci_scope.py`** classifies a diff from its PATHS alone: nine classes (`docs`, `skills`,
   `workflows`, `scripts`, `tests`, `data`, `containers`, `engines`, `security`), ten wildcard paths
   that select every class (a change to `Makefile`, `.github/**`, `scripts/ci_*.py` or `AGENTS.md` can
   change what any gate proves), and one entry per job family naming the classes that select it.
   Stdlib only, so it runs in the test image with no git, no network and no third-party action.
2. **`ci.yml`'s `pull_request` carries `paths-ignore`** for the docs class. GitHub applies that clause
   only when EVERY changed path matches, so one code file brings the whole matrix back; `push` to
   `main` is deliberately unfiltered.
3. **`scope.yml`** — no filter of its own — runs the classifier on every PR and reports one check
   named `scope`: the classes it detected, the jobs they select, the jobs they skip. A path matching
   no class fails it loudly. This is the legibility half: with no required status checks in the
   repository, an absent stage must be a stated decision, not a silent hole (the #801 lesson).
4. **`docs.yml`** runs, for that same docs class, the gates a documentation change can still break:
   `make ci-lint`, `check-docs`, `check-wiring`, `check-issue-bodies`, `check-workflows`,
   `check-dispatch-forms`, and `make ci-openspec`.

The selection is at the TRIGGER, never in a job `if:`: `tests/test_ci_images.py` allows exactly four
job-level shapes and a path selection is not one of them, and a condition that skips a job leaves
nothing in the job list to read.

## Verified

```
$ python3 scripts/ci_scope.py jobs --paths docs/ARCHITECTURE.md
[ci-scope] classes: docs
[ci-scope] jobs (5 of 22): guard, linux/lint, linux/openspec, macos/lint, macos/openspec

$ make ci-scope                      # this branch's own diff: it edits .github/** and Makefile
[ci-scope] classes: containers, data, docs, engines, scripts, security, skills, tests, workflows
[ci-scope] jobs (22 of 22): …
```

- `pytest tests/test_ci_scope.py` → 10 passed (one case per class, one per wildcard, a docs-only diff
  under ten jobs, an unknown path failing, and three wiring pins: `ci.yml` filters only the docs
  class and never `push`, `scope.yml` has no filter and runs `make ci-scope`, `docs.yml` runs the
  docs gates).
- `pytest tests/test_ci_images.py tests/test_workflows_valid.py tests/test_ci_scope.py` → 49 passed
  (the "no job or step is skipped" invariant is untouched: no new `if:` value anywhere).
- `make check-workflows check-dispatch-forms check-wiring check-docs check-issue-bodies lint` → all
  exit 0; `make openspec-validate-all` → 242 passed, 0 failed.

## Not covered

- **824b** — per-stage selection inside `ci.yml` for the code classes (`unit`, `install`, `top-tier`,
  `cpu-health`, `agents-read`). It needs `pipeline.yml` to accept a stage list and changes the job
  graph this change is still proving.
- **No required check.** `branches/main/protection` answers 404 and ruleset `24862727` carries only
  `deletion` and `non_fast_forward`, so nothing enforces the applied set today; `scope` buys
  legibility. Making it required is an owner decision, not part of 824a.
