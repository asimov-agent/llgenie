# Tasks — agent-dockerfile-user-zero (#2970)

- [x] Replace `USER root` at `containers/agent/Dockerfile:108` with `USER 0` plus a comment naming the rule and issue #2970 (proven at head: the file has no literal `USER root` line and carries `USER 0`).
- [x] Add `test_agent_dockerfile_never_spells_user_root` to `tests/test_agent_image_refresh.py` (no `USER root` line; a `USER 0` line; last `USER` non-root) and prove it: `pytest tests/test_agent_image_refresh.py -q` → rc=0.
- [x] Prove the finding is gone: `make security-scan TOOL=semgrep` → rc=0 and zero `last-user-is-root` findings for `containers/agent/Dockerfile` in `security-reports/semgrep.json`.
- [x] Prove the edited Dockerfile builds: `ci_images._build_local('agent')` → rc=0.
