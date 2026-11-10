## 1. Fold live-only tester files live→tree
- [x] 1.1 Fold `scripts/fold-live-profile.py` live→tree (commit b766d1c2)
- [x] 1.2 Fold the three remaining live-only references (commit 00d60cd7)
- [x] 1.3 Tag the subprocess line with the `# proc-allow:` marker (commit 3c7b00d5)

## 2. Verify
- [x] 2.1 The `# proc-allow:` marker is on the physical `subprocess.run(` line of the folded `scripts/fold-live-profile.py` at head `3c7b00d540c045e0e0897014e3c0f1b18e08477f` (verified by reading the file in-tree; the CI guard job's own verdict at this head is quoted on PR #2476 by the CI run, not asserted here)
- [x] 2.2 `make sync-agent-profile PROFILE=llgenie-tester CHECK=1` exits 0 at head 3c7b00d54 (measured rc=0 2026-11-10 after the tree→live sync made the profile the repository's copy; the two prior DIFFERS were tree-larger copies of the already-published SOUL.md and the tagged fold script)
