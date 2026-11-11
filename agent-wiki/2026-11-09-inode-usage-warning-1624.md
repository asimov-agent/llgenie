# 2026-11-09 — issue #1624: /tmp inode-utilisation WARNING + owner decision point

## What was wrong

The host `/tmp` is a shared, finite 1,048,576-inode tmpfs every lane uses for worktrees, probes and
container builds. The #1583 headroom preflight (`make check-host-space`, `scripts/check_host_space.py`)
refuses a build/dispatch when the tmpfs is BELOW a documented threshold — `<20%` space free OR `<50k`
free inodes — read from `df -h`/`df -i`. That gate watches the **free-inode count**, but inode
pressure can rise on a *utilisation* percentage axis without tripping the free-count refuse (e.g.
85% of the inode table used while enough inodes remain to pass the count gate). Because that pressure
is a fleet-shared resource, it must be *announced* to the owner before it bites a lane — and the
cleanup decision is owner-gated, never automatic.

## What the change is

- **`scripts/check_host_space.py` gains an inode-UTILISATION probe** (`issue #1624`) alongside the
  existing free-count refuse axes. `inode_usage_pct()` reads `os.statvfs` `f_files`/`f_favail` (the
  ratio of inodes *used*) for the filesystem hosting `/tmp`, and `report()` prints a structured
  `[host-space]` **WARNING** when utilisation is `>= --inodes-use-max %` (default **85**, module
  constant `DEFAULT_INODES_USE_MAX_PCT`, tunable like the existing `--inodes-min` flag).
- The WARNING names the **mount point**, the **measured percentage** and the **threshold**, and
  routes to an **OWNER DECISION POINT** — this check never deletes, prunes or otherwise remediates
  (no unlink/rm/subprocess-delete; it only reads `/proc/mounts` + `statvfs`).
- A missing/non-tmpfs `/tmp` is an **INFO skip** (never aborts the preflight); a statvfs *failure* on
  a tmpfs-identified real mount raises `HostSpaceError` (same policy as an unreadable `df`).
- It reuses the #1583 surface exactly — no parallel framework, no new make target, no docs change in
  the product PR; the WARNING rides the existing `make check-host-space` report.

## Proof

- `tests/test_check_host_space.py` — hermetic `_statvfs`/`_MOUNTS_PATH` seam (autouse
  `hermetic_probe` fixture) + new cases: below threshold (INFO, no WARNING), at threshold
  (WARNING), above threshold (WARNING naming mount + measured % + threshold), threshold tuning
  (`--inodes-use-max`), statvfs failure on a tmpfs mount (raises `HostSpaceError`), non-tmpfs /
  missing mount (INFO skip). Containerised run: `13 passed`.
- `make check-import-roots`, `make check-proc-gate`, `make openspec-validate
  NAME=inode-usage-warning-1624` all green.
- Real host run of the module (`check_host_space.py report --mount /tmp`) prints the inode-usage
  INFO/WARNING line naming the mount and percentage; at/above 85% the WARNING hands the cleanup
  decision to the owner.

Issue: #1624
