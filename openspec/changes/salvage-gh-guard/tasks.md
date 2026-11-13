# tasks — salvage-gh-guard

## 1. The guard

- [x] 1.1 `run()` catches `OSError` beside `subprocess.SubprocessError` (FileNotFoundError no longer escapes) — AC1
- [x] 1.2 `main()` prints the degraded note when `shutil.which("gh")` finds nothing and still returns 0 — AC1

## 2. The regression test

- [x] 2.1 a test in `tests/test_rebase_lane_scripts.py` drives the script with `gh` absent from PATH and asserts rc=0, no `Traceback`, degraded note — AC2

## 3. Proof

- [x] 3.1 the script run inside the gh-less test container exits rc=0 with no traceback (AC1 replay) — AC1
- [x] 3.2 `tests/test_rebase_lane_scripts.py` green in the test container (no `gh` mount) — AC2

## 4. Documentation

- [x] 4.1 `agent-wiki/` entry + `docs/changes.d/` fragment + `make changes-index` row, referencing #2638 and #2460

## 5. CI

- [x] 5.1 PR CI green on the PR head; this PR closes only issue #2638
