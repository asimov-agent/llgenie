# docs(bots): document the inode-utilisation preflight WARNING and OWNER DECISION POINT in the BOTS.md Preflight runbook (issue #1624)

## What changed

The `### Preflight` operator runbook in `docs/BOTS.md` now describes the inode-utilisation probe that
`make check-host-space` gained (implementation PR #2389, `scripts/check_host_space.py`): a third,
read/measure-only axis on a tmpfs `/tmp`, distinct from the space axis and from the pre-existing `df -i`
free-count refuse. The paragraph names:

- the measurement — inode **utilisation**, not bytes: `os.statvfs` `f_files`/`f_favail`
  (`used = f_files - f_favail`), on a mount `/proc/mounts` confirms is a tmpfs;
- the severity — `[host-space] WARNING` at `>= --inodes-use-max %` (default
  `DEFAULT_INODES_USE_MAX_PCT = 85`), naming the mount, the measured % and the threshold, then an
  **OWNER DECISION POINT**; the check never deletes, prunes or remediates;
- the edge handling — a missing or non-tmpfs `/tmp` INFO-skips the probe (never aborts the preflight),
  while a `statvfs` failure on a tmpfs-identified mount raises `HostSpaceError` like an unreadable `df`;
- owner guidance on the WARNING — inspect inode consumers on the shared tmpfs
  (`find /tmp -xdev -printf '%h/%f\n'` or `df -i /tmp` attribution), decide on cleanup, escalate to the
  owner. Framed strictly as owner action, never as an automated remediation.

Docs-only follow-on to issue #1624 (from #1583). No script, test, workflow or `docs/ARCHITECTURE.md`
census change; the code-side note trio for #2389 already covers the implementation.

## Reference

- #1624 — the inode-utilisation WARNING feature; implementation PR #2389 carries the code.
- #1583 — the host-side headroom preflight that `make check-host-space` is part of.

## Verification

- `make -s check-docs lint check-wiring check-pr-authors check-issue-bodies check-pr-hygiene` → rc 0 at
  the head.
- The documented facts re-measured against `scripts/check_host_space.py` at PR #2389 head
  `ca111a98`: `inode_usage_pct()`, `DEFAULT_INODES_USE_MAX_PCT = 85`,
  `--inodes-use-max` (default 85), `[host-space] WARNING` + `OWNER DECISION POINT`, INFO-skip edges.
