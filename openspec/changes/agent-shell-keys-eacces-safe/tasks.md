# Tasks: agent-shell-keys-eacces-safe (#3020)

- [x] T1: Reproduce the failing target on this host against the published agent image
      (`make agent-shell-keys-check` → `[Errno 13] Permission denied:
      '/root/.hermes/hermes-agent/tools/environments/local.py'`).
      (proven: make agent-shell-keys-check rc=2 at head cd1c357bb, /tmp/shellkeys-repro.log)
- [x] T2: Name the cause: `Path.is_file()` re-raises `PermissionError` on an unreadable candidate
      (`/root` is mode `0700`, container runs as uid 999 `agent`), so `hermes_root()` aborts before
      the readable install at `/home/agent/.hermes/hermes-agent` is consulted.
      (proven: docker run --rm ghcr.io/asimov-agent/llgenie/agent:latest bash -lc 'id; ls -ld /root;
      ls -l /home/agent/.hermes/hermes-agent/tools/environments/local.py' rc=0 — uid 999 agent,
      /root drwx------ root, the install agent-readable)
- [x] T3: Add the readable-only candidate probe in `scripts/agent_shell_keys_check.py` (skip on
      `PermissionError`) and print the chosen root plus any candidate skipped as unreadable.
- [x] T4: Add the negative-control tests in `tests/test_agent_shell_keys.py`: unreadable candidate
      skipped (fails pre-fix), only-readable-candidate chosen, no readable candidate stays loud.
      (proven: pytest tests/test_agent_shell_keys.py rc=1 (4 failed) with the fix stashed, rc=0
      (14 passed) with it applied)
- [x] T5: Prove the real target: `make agent-shell-keys-check` green in the published agent image.
      (proven: make agent-shell-keys-check AGENT_SHELL_CHECK_KEYS="NOUS_API_KEY GH_TOKEN TYPESAFE_API_KEY"
      rc=0 — `OK: 3 credential(s) visible in the agent's shell`, `/root` candidate reported skipped,
      log /tmp/shellkeys-final.log)
- [x] T6: Docs fragments (`docs/changes.d/`), `agent-wiki/` entry, `make changes-index`, fast gates
      (`lint`, `check-wiring`, `check-docs`), `make openspec-validate`.
      (proven: make -s changes-index, make lint, make check-wiring, make check-docs, make -s
      openspec-validate NAME=agent-shell-keys-eacces-safe all rc=0)
- [x] T7: Final pre-push proofs: `make lane-preflight` and `make test-unit` green at the commit head.
      (proven: make lane-preflight rc=0 (7 gates) and make test-unit rc=0 4405-passed 13638-deselected
      at the branch head, logs /tmp/g_preflight.log, /tmp/test-unit-3020b.log)
