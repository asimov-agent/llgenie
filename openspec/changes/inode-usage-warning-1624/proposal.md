---
name: inode-usage-warning-1624
about: Add a /tmp inode-UTILISATION WARNING + owner decision point to the host tmpfs preflight (issue #1624)
status: active
---

# Inode-usage WARNING on the host tmpfs (issue #1624)

## Proposal

The `make check-host-space` preflight (issue #1583, `scripts/check_host_space.py`) refuses a
build/dispatch when the shared host /tmp tmpfs is below its headroom threshold — `<20%` space free OR
`<50k` inodes free, read from `df -h`/`df -i`. That gate reads the **free-inode count** axis.

Issue #1624 adds a **distinct inode-UTILISATION-percentage WARNING**: the fs backing /tmp can reach
high inode *utilisation* (e.g. 85% of the inode table used) without tripping the free-count refuse
gate, and that pressure is a fleet-shared resource the owner must be told about before it bites a
lane. The change:

- adds an inode-usage probe via `os.statvfs` (`f_files`/`f_favail` — the ratio of inodes *used*),
  distinct from the df-based free-count refuse,
- prints a structured WARNING when inode utilisation is `>= --inodes-use-max %` (default **85**,
  tunable; module constant `DEFAULT_INODES_USE_MAX_PCT`), naming the **mount point**, the **measured
  percentage** and the **threshold**,
- routes to an **OWNER DECISION POINT**: the check never deletes, prunes or remediates — it reads and
  reports only (no unlink/rm/subprocess-delete),
- handles non-tmpfs / missing-mount / statvfs-success-but-unknown mounts gracefully as an INFO skip
  (never aborts the preflight), while a statvfs *failure* on a tmpfs-identified real mount surfaces as
  a `HostSpaceError` (same policy as an unreadable `df`),
- keeps the threshold a named constant / CLI flag mirroring the `--inodes-min` flag shape.

The check runs through the existing `make check-host-space` target; the WARNING is severity WARNING
(not a new refuse gate) so a host at high inode utilisation still runs its gate, but the pressure is
announced to the owner for a decision. No new make target, no docs change (docs are a separate card),
no parallel framework — the #1583 module and its test seam are reused.
