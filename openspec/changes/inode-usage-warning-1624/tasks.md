# inode-usage-warning-1624

- [x] `scripts/check_host_space.py`: `inode_usage_pct()` reads statvfs `f_files`/`f_favail`; `report()` prints the inode-utilisation WARNING at `>= --inodes-use-max %` (default 85) naming mount + measured % + threshold + OWNER DECISION POINT; constant `DEFAULT_INODES_USE_MAX_PCT`; `--inodes-use-max` CLI flag; non-tmpfs/missing mount INFO-skips; statvfs failure on a tmpfs-identified mount raises `HostSpaceError`; no remediation side effect (read/measure only)
- [x] `tests/test_check_host_space.py`: hermetic seam (`_statvfs` + `_MOUNTS_PATH` injection, autouse `hermetic_probe` fixture) + cases for below / at / above threshold (naming fields), threshold tuning, statvfs failure, non-tmpfs/missing skip
- [x] `make check-host-space` still passes (the #1583 gate target is unbroken) — verified locally via the containerised suite
- [x] `make openspec-validate NAME=inode-usage-warning-1624` green
