# Tasks: agent-image-install-sha

- [x] 1. Worktree cut off the latest `origin/main`; OpenSpec change created via the CLI
- [x] 2. Measure the live installer content hash (`c73dad4d…`, 68,015 bytes, 2026-11-20)
- [x] 3. proposal.md + specs/agent-image-install-integrity/spec.md written
- [x] 4. Dockerfile: `ARG HERMES_INSTALL_SCRIPT_SHA` pin + ENV export to the install step
- [x] 5. `install_hermes_ci.sh`: fetch-to-file → sha256 verify → run (container proof with a wrong pin: refusal printed, rc=1, twice — incl. the final script text)
- [x] 6. `tests/test_agent_image_refresh.py`: updated ARGS-forwarding pin to the verified-temp-file invocation + new content-pin/order test (7/7 green)
- [x] 7. Real agent-image build with `--build-arg HERMES_INSTALL_SCRIPT_SHA=<all zeros>` exits non-zero at the install step (WRONGSHA_BUILD_RC=1, drift refusal printed in the build log)
- [x] 8. Real agent-image build with the default (correct) pin completes rc=0 (GOODSHA_BUILD_RC=0: verified-against-pin line + `[agent-image] chain OK` in the same build)
- [x] 9. `make openspec-validate NAME=agent-image-install-sha` exits 0
- [x] 10. `make test-unit` green on the lane (4210 passed, rc=0); docs mirrored (agent-wiki entry + changes.d fragment)
- [x] 11. `make lane-preflight` prints `preflight: OK`; push + PR with closing keyword and mirrored AC block
