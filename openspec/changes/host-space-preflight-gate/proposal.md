---
name: host-space-preflight-gate
about: A measurable host /tmp headroom check the planner runs before dispatch, extending ci-free-disk (never replacing)
status: active
---

# Host-space preflight gate (issue #1583)

## Proposal

The host `/tmp` (a 32G / 1,048,576-inode tmpfs) is a shared, finite resource every lane uses for
worktrees, probes and container builds, and it has NO headroom gate — no workflow, script or make
target measures it, and the planner's dispatch flow has no preflight for it. Measured 2026-11-02: a
single probe tree (`/tmp/trtllm-probe`, 15G / ~197k inodes) drove the tmpfs to 71% space AND 100%
inodes simultaneously and wedged two lanes (the implementer's tool channel and the reviewer's
worktree-add ENOSPC); both were caught only after the lane failed. The only space tooling is
`ci-free-disk` (CI-runner disk for engine images) — host tmpfs is out of its scope.

This change adds a measurable host-space preflight:

- `scripts/check_host_space.py` reads BOTH axes of a mount (`df -h` space and `df -i` inodes) and
  exits 1 when the tmpfs is below a documented threshold (<20% space free OR <50k inodes free).
- `make check-host-space` runs it — the gate the planner (or any lane) runs BEFORE spawning a `/tmp`
  worktree or container build.
- The threshold, placement rule and refusal behaviour are committed under `agents/llgenie-planner/`
  in the six-section shape (issue #791 versioned home).

`ci-free-disk` is extended in scope conceptually (a sibling host check) but its own behaviour is
unchanged — this target is ADDED, never a replacement; no existing gate is weakened.

## Motivation

A planner cannot dispatch accurately and a lane cannot build if the shared tmpfs is full, yet neither
measures it before starting. The failure is double-barrelled: it wedges whichever lane touches `/tmp`
next, and it saves no tree state, so the lane cannot recover without an owner decision. Codifying the
check (not a private habit) makes it greppable and measurably enforced, and keeps the standing
behaviour reviewable under the lane's versioned home.

## Change

- `scripts/check_host_space.py` — parses `df -h <mount>` and `df -i <mount>`; `check_host_space.py
  [check|report] [--mount /tmp] [--space-min 20] [--inodes-min 50000]`; `check` exits 1 when either
  axis is below its threshold and names the offending axis; `report` prints the verdict and always
  exits 0; an unreadable `df` is an error (never a silent pass); `df` goes through `scripts/proc.py`
  and the tests drive it with a fake `df` on PATH.
- `Makefile` — `check-host-space` target (host preflight) with `.PHONY`, documented in `docs/BOTS.md`.
- `agents/llgenie-planner/SOUL.md` — standing behaviour: run `make check-host-space` before dispatching
  a lane onto a `/tmp` worktree/container build; refuse below threshold; heavy worktrees default to
  real disk under `/home/asimov/repository/git/llgenie-wt/`; `/tmp` holds small/scratch files only;
  occupant attribution/cleanup stay owner-gated.
- `tests/test_check_host_space.py` — hermetic tests via a fake `df` on PATH.
- `agent-wiki/` note + `docs/changes.d/` fragment + `CHANGES.md` re-render.

No existing gate is weakened; `ci-free-disk` keeps its exact behaviour.
