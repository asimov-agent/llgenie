# Tasks: reconcile-lane-skill-drift

- [x] 1. Fold live §12 (ci(verify) dispatch-only tickets) into
      `agents/llgenie-tester/skills/llgenie-pr-testing/SKILL.md`; do NOT fold the
      pre-#2510 `--force-if-includes` line-691 variant.
- [x] 2. Fold the `mk/*.mk` glob fix into
      `agents/llgenie-documentation-maintainer/skills/llgenie-docs-maintainer/scripts/docs_audit.py`.
- [x] 3. Prove the tree carries no retired text: `git show 6e3f25ffc --name-only`
      covers 28/28 drift files; tree copies byte-unchanged by this PR.
- [x] 4. Re-sync the seven drift lanes from the reconciled tree
      (`make sync-agent-profile PROFILE=<lane>`) and prove
      `make check-agent-profiles` exits 0 with zero per-lane FAIL lines.
- [ ] 5. Sync issue #2679 body + PR body to the reconciled acceptance (referee
      rule), tick ACs with replayable proven strings.
- [ ] 6. Final verification at head: `make check-agent-profiles`,
      `make check-docs`, `make lane-preflight` all green.
