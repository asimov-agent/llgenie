# Tasks: zombie-run-retire

- [x] 1. Retirement record read/write: `zero-job-zombie-retired` marker helpers, `zombie_retired_run_ids`
      (issues open OR closed), `file_retirement_issue` through `issue_body.render`.
- [x] 2. Classification retires marker-matched candidates before any cancel/file/RED; fix mode routes a
      `already completed` refusal to retirement instead of stranded filing; exit 0 when all candidates
      are retired, red unchanged for live starvation.
- [x] 3. Tests: read-only retirement from a marker, fix-mode confirm+record (rc 0, no RED/stranded),
      live-starvation arms unchanged, mixed zombie+live scan.
- [x] 4. Live proof on the real board: `make check-zero-job-pending FILE=1 CANCEL=1` confirms the five
      phantoms and exits 0; a following plain scan reports zero findings and exits 0.
- [x] 5. File the out-of-scope issue (admin delete arm), mirror issue #2600 body to the measured truth,
      docs fragment + agent-wiki note, gate replays rc=0 before push.
