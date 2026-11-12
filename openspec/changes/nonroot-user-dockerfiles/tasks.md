# Tasks — nonroot-user-dockerfiles (#2504)

- [x] 1. Create this OpenSpec change (`make openspec-new NAME=nonroot-user-dockerfiles`)
- [x] 2. Patch `scripts/engine_skills.py`: idempotent uid/gid 1000 create constants; `USER 1000:1000` + create `RUN` in `render_base_dockerfile`; engine create `RUN` + `USER 1000:1000` before `HEALTHCHECK` in `render_dockerfile`; `USER root` after every derived `FROM`
- [x] 3. `containers/test/Dockerfile`: user create + `git config --system safe.directory` + trailing `USER 1000:1000` (stages keep `-u root` from the Makefile)
- [x] 4. `make generate-engine-params` re-renders all 36 generated Dockerfiles; `make check-engine-params` rc=0 (0 stale); `make lint` rc=0
- [x] 5. Targeted engine gates: `tests/test_engine_skills.py`, `tests/test_engine_bump.py`, `tests/test_ci_variant_matrix.py` green (187 passed rc=0 at head `b31cdde09`; the one earlier failure was a dirty-tree artifact of `matrix(changed="HEAD")` diffing HEAD against the uncommitted worktree, green once committed)
- [x] 6. Trivy proof: `make security-scan TOOL=trivy` at the head reports zero root-user findings (rc=0, 0× "Image user should not be 'root'" in `security-reports/trivy.json`); negative control: the same pinned image `ghcr.io/asimov-agent/llgenie/trivy:0abec50ba0db` against a detached `origin/main` worktree reports **37** (rc=0)
- [ ] 7. `make test-unit` is green
- [x] 8. Docs trio: `docs/changes.d/` fragment + `CHANGES.md` + `agent-wiki/` entry (`make changes-index` rc=0, `make check-docs` rc=0)
- [ ] 9. Final verification: `make openspec-validate NAME=nonroot-user-dockerfiles` rc=0 and `python3 scripts/check_pr_acceptance.py check --body-file <PR body>` replays rc=0 against the body carrying `closes #2504`
