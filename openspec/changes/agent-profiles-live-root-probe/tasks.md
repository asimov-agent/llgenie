# Tasks: agent-profiles-live-root-probe (#923)

## 1. Baseline

- [x] 1.1 Record the failing probe on the base commit: `HERMES_PROFILE_HOME=/nonexistent-home python3 scripts/check_agent_profiles.py` exits 2 with the PermissionError abort at `4f3fc1ef2`.

## 2. Probe fix

- [x] 2.1 Make the shape probe unreadable-tolerant in `scripts/check_agent_profiles.py`: unreadable candidate → not a profile, continue; unlistable base → no live comparison.
- [x] 2.2 When a provided variable's base is rejected, name the resolved base in the skip line and in the OK-line caveat source; keep the no-variable wording unchanged.

## 3. Tests

- [x] 3.1 Fixture: mode-000 candidate inside a readable profiles home — comparison runs, probe does not abort.
- [x] 3.2 Fixture: unlistable base (mode 111) — skip caveat names the resolved base, exit 0.
- [x] 3.3 Fixture: provided variable resolving to a profiles-less parent — skip line names the parent path.
- [x] 3.4 Positive control test: tree-prefix-of-live still reds `live-longer` through the new probe.

## 4. Verify

- [x] 4.1 `pytest tests/test_agent_profiles.py` green on the lane tree.
- [x] 4.2 Host probe after the fix: `HERMES_PROFILE_HOME=/nonexistent-home python3 scripts/check_agent_profiles.py` exits 0, prints the skip caveat naming `/`, no abort line.
- [x] 4.3 `make check-agent-profiles`, `make profile-drift`, `make lint`, `make check-docs` exit 0 on the unmodified lane tree.

## 5. Ship proofs

- [x] 5.1 Full unit battery `make test-unit` exits 0 on the committed lane head.
- [x] 5.2 `make openspec-validate NAME=agent-profiles-live-root-probe` exits 0 on the final lane tree.
