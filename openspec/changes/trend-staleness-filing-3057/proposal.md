# Proposal: trend-staleness-filing-3057

## Why

`ci-hf-live` named a live trend drift and then lost its refresh issue. Measured on run
[45366360390](https://github.com/asimov-agent/llgenie/actions/runs/45366360390) (push to `main`,
2026-11-24T09:35:47Z, job `hf-live`): `make check-trend-list-fresh` printed 4 disagreeing cells
(`metal/24/8|32|60|64`, Gemma 3 27B 6 GB -> 10 GB, fingerprint `866ec6ad00f3`) and exited 1 — the
ticketed path — but the step concluded with exit **2** and filed nothing: `scripts/trend_staleness_issue.py`
re-calls `staleness_read()` (`trend_staleness_issue.py:145`), so the filing path performs a SECOND live
trending build, and a Hub blip in that second read returns the unreadable-read code 2. The step log carries
no `make trend-staleness-issue` output (the annotation follows the `Error 1` line by 1.8 ms; a live re-read
costs ~33 s), and no `trend-staleness:` issue exists after the run. Issue: #3057.

## What Changes

- **ADDED**: `scripts/trend_list_matrix.py::staleness_read` names its drift to a handoff artifact
  `build/trend-staleness-drift.json` when it exits 1 (the cell diffs it already computed); a fresh read
  (exit 0) removes a stale handoff; an unreadable read (exit 2) leaves the handoff untouched so a named
  drift is never erased by a blip.
- **MODIFIED**: `scripts/trend_staleness_issue.py::main` files from that handoff when one exists — no
  second live trending build. It re-reads live ONLY when invoked standalone with no handoff, and a
  standalone re-read that cannot run prints its failure by name before returning 2.
- **MODIFIED**: `.github/workflows/ci-hf-live.yml` trend-staleness step guards the filing call
  (`make trend-staleness-issue || rc=$?`): a filing failure prints the failing leg by name and exits 3 —
  the step can no longer die with exit 2 from the filing path. The check's own exit-2 branch stays loud.
- **ADDED**: tests pin all three legs — handoff reuse (stubbed live read that must NOT be reached),
  the workflow step script shape (filing guarded, no exit-2 path through it), and the named standalone
  re-read failure (print + exit code).

Not changed: the `mk/engines.mk` target contracts (`check-trend-list-fresh` 0/1/2,
`trend-staleness-issue` 0/2/3), the dedupe marker contract, or the re-pin of the drifted cells itself
(issue #3056).
