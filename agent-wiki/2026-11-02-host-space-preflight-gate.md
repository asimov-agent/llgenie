# 2026-11-02 — issue #1583: a host /tmp headroom preflight, codified not habit

## What was wrong

The host `/tmp` (a 32G / 1,048,576-inode tmpfs) is a shared, finite resource every lane uses for
worktrees, probes and container builds, and it had NO headroom gate — no workflow, script or make
target measured it, and the planner's dispatch flow had no preflight. Measured 2026-11-02: a single
probe tree (`/tmp/trtllm-probe`, 15G / ~197k inodes) drove the tmpfs to 71% space AND 100% inodes
simultaneously and wedged two lanes in one pass — the implementer's tool channel (containerized
probes) and the reviewer's worktree-add ENOSPC. Both were caught only after the lane failed. The only
space tooling was `ci-free-disk` (CI-runner disk for engine images), which is host-agnostic and out of
scope for host tmpfs.

## What the change is

- **`make check-host-space`** (via `scripts/check_host_space.py`) is the measurable preflight: it reads
  BOTH axes of the shared tmpfs (`df -h` space and `df -i` inodes), and exits 1 below the documented
  threshold (<20% space free OR <50k inodes free), naming the offending axis. A `report` mode prints
  the measurement and always exits 0; an unreadable `df` is an error, never a silent pass. It measures
  and refuses only — occupant attribution and cleanup stay the owner's call.
- **The standing behaviour is committed under `agents/llgenie-planner/`** (the #791 versioned home): run
  `make check-host-space` before dispatching a lane onto a `/tmp` worktree or container build and refuse
  the doomed run below threshold; heavy worktrees default to real disk under
  `/home/asimov/repository/git/llgenie-wt/`; `/tmp` holds at most small/scratch files and never a
  multi-GB probe tree.
- **`ci-free-disk` is unchanged** — the host check is ADDED as a sibling, never a replacement.

## Proof

- `python3 -m pytest tests/test_check_host_space.py` — 7 passed (hermetic, fake `df` on PATH).
- Real host measurement this branch: `/tmp: 76% space free, 171,159 inodes free` → `make
  check-host-space` exits 0 (`OK: /tmp above the headroom threshold`). A synthetic below-threshold
  `df` (fake `df` in the test) exits 1 and names the axis.
- `make check-docs`, `make check-wiring`, `make openspec-validate NAME=host-space-preflight-gate`,
  `make check-host-space` all rc 0.

Issue: #1583
