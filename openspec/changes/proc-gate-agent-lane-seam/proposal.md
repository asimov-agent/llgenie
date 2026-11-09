# proc-gate-agent-lane-seam — proposal

Issue: [#2229](https://github.com/asimov-agent/llgenie/issues/2229)

## Why

The `subprocess-without-returncode` policy (issue #797) is enforced by `scripts/check_proc_gate.py`
over a single literal: `SCRIPTS = "scripts"`, `(root / SCRIPTS).glob("*.py")`. The exit-code invariant
— a failed command must never read as a benign empty result — therefore stops at the top-level
`scripts/` directory while the same class is live in every agent-lane scripts dir and the whole test
tree. Measured at head: `agents/**/scripts/*.py` = 10 files / 15 bare sites (unpolicied), `tests/*.py`
= 127 files / ~370 sites (unpolicied), `scripts/*.py` = 95 files (already policied). Semgrep
(`--config=p/default`) fires no subprocess rule (`run-shell-injection`/`curl-pipe-bash`
`dynamic-urllib-use-detected` only), so the class is not caught by SAST either.

## What Changes

- **`scripts/check_proc_gate.py`** broadens the walk to three populations:
  - `scripts/*.py` — production runners, **ENFORCED** (a bare `subprocess.run/check_output/Popen`
    exits 1).
  - `agents/**/scripts/*.py` — production bot-lane runners, **ENFORCED** (new in #2229).
  - `tests/*.py` — the behavior harness, **SCANNED + SURFACED** in the census (so the 127-file class
    is never invisible again) but NOT a gate red: a test's job is to spawn subprocess and assert on
    it, and hard-gating it would force a whole-tree `# proc-allow:` carve (the #2229 AC3 weakening).
- The seam (`scripts/proc.py`) and a per-site `# proc-allow: <reason>` remain the only two escapes,
  in both enforced populations.
- The genuinely-rc-dropping sites (the exact #797 failure mode) migrate onto the seam:
  `measure_live_admission.py:41` → `run_text`; `resolve-fleet-triple.py:20` → `scripts.proc.run_text`
  via the repo-root sys.path bootstrap; `worktree_divergence_audit.py:60` → `run_ok`.
- Sites that already read returncode before use carry a `# proc-allow:` reason naming the inspection
  + migration, so they stay visible and the census shrinks from here:
  `docs_audit.py:28`, `verify_fold_identity.py:27`, `measure_lane_idleness.py:24`,
  `dirty-detector.py:88/92/109/115`, `tally-delta.py:93`, `salvage-four-bucket.py:45`,
  `pr_watch.py:33/329`.
- `tests/test_proc_seam_gate.py` gains 4 cases: a bare agent-lane `subprocess.run` reds `check`
  (AC4), a `# proc-allow:` there is the valid escape, a bare test subprocess is surfaced not red, and
  `check` prints both the enforced finding and the tests census.

## Impact

- Modified: `scripts/check_proc_gate.py`, `tests/test_proc_seam_gate.py`, 10 agent-lane
  `agents/**/scripts/*.py` files (migration or `# proc-allow:`); `docs/changes.d/` + `agent-wiki/`
  records; a `changes.d` fragment for this change dir.
- `check-proc-gate` / `proc-gate-report` (in `make ci-unit`) stay green at the fixing head.
- No gate weakened: no subtree allowlist, no `require_fix: false`, no inline `# noqa`.
