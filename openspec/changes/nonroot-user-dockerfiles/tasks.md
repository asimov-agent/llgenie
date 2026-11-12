# Tasks — nonroot-user-dockerfiles (#2504)

- [x] 1. Create this OpenSpec change (`make openspec-new NAME=nonroot-user-dockerfiles`)
- [x] 2. Patch `scripts/engine_skills.py`: idempotent uid/gid 1000 create constants; `USER 1000:1000` + create `RUN` in `render_base_dockerfile`; engine create `RUN` + `USER 1000:1000` before `HEALTHCHECK` in `render_dockerfile`; `USER root` after every derived `FROM`
- [x] 3. `containers/test/Dockerfile`: user create + `git config --system safe.directory` + trailing `USER 1000:1000` (stages keep `-u root` from the Makefile)
- [x] 4. `make generate-engine-params` re-renders all 36 generated Dockerfiles; `make check-engine-params` rc=0 (0 stale); `make lint` rc=0
- [x] 5. Targeted engine gates: `tests/test_engine_skills.py`, `tests/test_engine_bump.py`, `tests/test_ci_variant_matrix.py` green (188 passed rc=0 at rebased head `73fda671a`; `matrix(changed="HEAD")` diffs must run against a committed tree, or a dirty worktree fakes a failure)
- [x] 6. Trivy proof at rebased head `73fda671a`: `make security-scan TOOL=trivy` rc=0 with **0** `DS-0002` findings in `security-reports/trivy.json`; negative control with the same pinned image `ghcr.io/asimov-agent/llgenie/trivy:0abec50ba0db` against a full-tree scan of base `614838fb8` reports **37** `DS-0002` and the head scan reports **0** with **0** new findings (DS-0026 12→12, DS-0001 1→1 unchanged)
- [x] 7. `make test-unit` is green (3625 passed, 0 failed at head `73fda671a`, log testunit2504b.log)
- [x] 8. Docs trio: `docs/changes.d/` fragment + `CHANGES.md` + `agent-wiki/` entry (`make changes-index` rc=0, `make check-docs` rc=0)
- [x] 9. Final verification: `make openspec-validate NAME=nonroot-user-dockerfiles` rc=0 and `python3 scripts/check_pr_acceptance.py check --body-file <PR body>` replays rc=0 against the body carrying `closes #2504` (both rc=0 at head `73fda671a`)
- [x] 10. `tests/test_ci_publish_order.py`: a moved engine Dockerfile now defers that engine from the registry-required publish set (same retag reason as the #823 tag-computation rule — the context hash covers the Dockerfile, and this PR's producer publishes the new tag); harness branch/base fix + deterministic new test; 23 passed rc=0 at head `73fda671a`
