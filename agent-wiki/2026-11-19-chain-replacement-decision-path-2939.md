# Chain-replacement decision path in the catalog drift issue (#2939)

Issue #2939 / PR #TBD (OpenSpec change `chain-replacement-decision-path`).

## What was verified

- `scripts/check_agent_model_catalog.py::issue_text` now renders a four-step
  decision path in `## How we fix it`: (1) name ONE budget-preserving drop-in
  candidate per named member and record the choice on the drift issue; (2) land
  the re-pin as its own issue -> branch -> OpenSpec -> PR whose body ends with
  `closes #<this issue>`; (3) `make apply-hermes-base-config --all`; (4) the
  weekly `make check-agent-model-catalog` re-verify + `make
  agent-image-profiles-check` prove the new pin, closing the drift issue with
  the PR so no repeat-alarm cycle remains.
- New `dropin_candidates()` lists, per named member in `## Technical`, every
  `:free` catalog id whose published `context_length` >= the member's committed
  budget (member itself excluded), or a `no drop-in` line when none qualify.
- `compare()` is untouched: same findings, same exit 1, same stdout (pinned by
  `test_decision_path_does_not_change_the_alarm_semantics`).
- Drift-issue acceptance items now mirror the path: record the chosen id on the
  issue; the re-pin PR closes the issue with both make proofs green.

## Key decisions

- Drop-ins are budget-preserving by construction (published >= committed), so a
  replacement never shrinks a profile's session window.
- The check still never edits `agents/hermes-base-config.yaml`; it only names
  candidates and the lane that carries the edit.

## Proof (at branch head, pre-squash)

- `python3 -m pytest -q tests/test_check_agent_model_catalog.py` rc=0 — 20
  passed (4 new tests: decision-path order+numbering, budget filter,
  no-drop-in line, unchanged alarm semantics).
- Live: `make check-agent-model-catalog` rc=0 (6/6 members, budgets match).
- Dry-run fixture (live catalog minus `qwen/qwen4-max:free`): rc=1, body
  carries all four numbered steps and
  `drop-in candidates for qwen/qwen4-max:free (budget 1000000):
  meituan/longcat-2.5:free, tencent/hy4-flash:free`.
- `make lint`, `make check-wiring`, `make check-issue-bodies` rc=0.

## Current status

Stacked on PR #2940's head (the producer only exists there until #2940 lands);
rebase onto main once #2940 merges. PR open, CI-driven landing via auto-merge.
