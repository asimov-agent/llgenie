# Tasks

- [x] `scripts/check_proc_gate.py` walks three populations (scripts/, agents/**/scripts/ enforced; tests/ surfaced), hashing the `# proc-allow:` + seam escapes; `check` exits 1 on a bare site in an enforced population, `report` lists all three.
- [x] The genuinely-rc-dropping sites migrate onto `scripts.proc` (`measure_live_admission.py:41` → run_text; `resolve-fleet-triple.py:20` → run_text; `worktree_divergence_audit.py:60` → run_ok via repo-root sys.path bootstrap).
- [x] Sites that read returncode before use carry a `# proc-allow:` reason naming the inspection (#2229 tracked remainder): docs_audit:28, verify_fold_identity:27, measure_lane_idleness:24, dirty-detector:88/92/109/115, tally-delta:93, salvage-four-bucket:45, pr_watch:33/329.
- [x] `tests/test_proc_seam_gate.py` gains 4 cases (agent-lane bare reds; proc-allow is the escape; bare test is surfaced not red; check prints both); battery passes (10).
- [x] `make check-proc-gate` / `make proc-gate-report` / `make lint` green; docs per convention (changes.d fragment + agent-wiki note + this change dir); PR carries `closes #2229`.
