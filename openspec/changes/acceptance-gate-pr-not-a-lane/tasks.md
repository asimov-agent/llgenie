# Tasks

- [x] Reproduce: the pre-fix gate emits `rollout-lane-open` for an OPEN PR that cites the umbrella back, and for an already-CLOSED close target (new tests red on `origin/main`'s script: 2 failed)
- [x] Read the PR/issue distinction in `_fetch_issue_meta` (`gh api repos/<repo>/issues/<n>` → `pull_request`), returning `(body, state, is_pull_request)`
- [x] `rollout_lane_findings` skips a referenced pull request, whatever its state
- [x] `main()` short-circuits an already-`CLOSED`/`MERGED` close target before the lane probe (the acceptance verdict still runs)
- [x] Regression tests: umbrella cites an OPEN PR that cites it back → zero findings; already-closed close target → no lane finding, with the OPEN-target control still red; the #1859 OPEN-**issue**-lane hold unchanged
- [x] Change-note trio (`agent-wiki/`, `docs/changes.d/`, rendered `CHANGES.md`) + `check-docs` / `lint` / `check-wiring` green
