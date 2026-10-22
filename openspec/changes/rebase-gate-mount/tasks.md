# Tasks — rebase-gate-mount

- [x] 1. OpenSpec change
- [x] 2. Makefile: mounts use $(ROOT), an override of the checkout path
- [x] 3. tests/test_rebase_bot_gates.py
- [x] 4. README + agent-wiki
- [x] 5. Verified: `pytest tests/test_rebase_bot_gates.py` → 2 passed
- [x] 6. Fix the test's host assumption: macOS expands the lint recipe natively, so the mount
      invariant is asserted on `TEST_OPTS` and the recipe against the shape its own host runs
- [x] 7. Verified: Linux branch `pytest tests/test_rebase_bot_gates.py` → 2 passed; Darwin branch
      asserted against real `make -e HOST_OS=Darwin` output (the previous test fails there, this one
      passes)
