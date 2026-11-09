# proc-gate-agent-lane-seam — extend the #797 subprocess seam to agent-lane runners

The `#797` exit-code policy was policied only in `scripts/*.py`. `check_proc_gate.py` now walks three
populations: `scripts/` + `agents/**/scripts/` (ENFORCED — a bare `subprocess.run` exits 1) and
`tests/` (SCANNED + SURFACED in the census, not gate-red: the behavior harness must spawn subprocess
to assert on it). The genuinely-rc-dropping sites migrate onto `scripts.proc` (`measure_live_admission`,
`resolve-fleet-triple`, `worktree_divergence_audit`); sites that already read returncode carry a
`# proc-allow:` tracked remainder. `check-proc-gate` / `proc-gate-report` stay green; no gate weakened
(no subtree allowlist, no `require_fix: false`, no inline `# noqa`).
