# host-space-preflight-gate

- [x] `scripts/check_host_space.py`: parse `df -h` (space) and `df -i` (inodes); `check` exits 1 below threshold (<20% space OR <50k inodes) naming the axis; `report` prints + exits 0; unreadable `df` is an error; `df` via `scripts/proc.py`
- [x] `Makefile`: `check-host-space` host-preflight target + `.PHONY`, documented in `docs/BOTS.md`
- [x] `tests/test_check_host_space.py`: hermetic via fake `df` on PATH (healthy, low-space, low-inodes, boundary-at-thresholds, report-mode exit-0, unreadable-`df` error)
- [x] `agents/llgenie-planner/SOUL.md`: standing behaviour — preflight `make check-host-space` before dispatch, real-disk heavy worktree placement, /tmp small/scratch only, cleanup owner-gated (#791)
- [x] `agent-wiki/` note + `docs/changes.d/` fragment + `CHANGES.md` re-render
- [x] `make check-host-space`, `make check-docs`, `make check-wiring`, `make lint`, `make check-host-space`, `make test-unit` (subset), `make openspec-validate NAME=host-space-preflight-gate` green
