# Tasks

- [x] 1. Write the proposal + spec for the PR fix-bot (issue #222).
- [x] 2. `scripts/fix_loop.sh`: check -> agent -> re-check, `FIX_ROUNDS` (default 3), early stop,
      loud give-up, misconfiguration refusal, and no git access at all.
- [x] 3. `scripts/fix_bot_rules.md`: the agent's contract (fix the code, never mock/weaken/skip,
      verify through the Makefile, do not edit workflows to change an outcome, no credentials).
- [x] 4. `scripts/fix_bot_report.py`: the PR comment when the loop gives up.
- [x] 5. `.github/workflows/fix-bot.yml`: `workflow_dispatch` only (no `workflow_run`), actor
      guard, PR resolution that refuses main, PAT checkout + one-commit push, PR comment,
      concurrency, 120-minute timeout.
- [x] 6. `scripts/fix_bot_sweep.py` + the workflow's own `schedule`: the sweep decides which PR to
      repair (open, non-draft, same-repo, at least one failing check, fewer than three
      `fix(bot):` commits, oldest first, one per sweep) and dispatches the repair. The decision
      lives in code because issue #107 forbids a CI job with a skipping `if:` — an earlier
      `dispatch-fixbot` job in `ci.yml` failed
      `tests/test_ci_images.py::test_no_ci_step_or_job_is_skipped` and was removed.
- [x] 6b. `tests/test_fix_bot_sweep.py`: fork/draft/base-branch/green refusals with reasons, the
      attempt cap, the oldest-first pick, exactly one dispatch per sweep, dry mode, and the
      attempt counter reading only `fix(bot):` headlines.
- [x] 7. `scripts/install_hermes_ci.sh`: the Hermes install seam, loud when nothing works — used at
      IMAGE BUILD time, so the runner never installs the agent on the fly.
- [x] 7b. `containers/agent/Dockerfile` + the CI registry entry (`scripts/ci_images.py`'s `agent`):
      the test image plus the Hermes CLI, git, `gh` and the docker CLI, with the base pinned and
      the tag derived from the Dockerfile, the install script and the base's hash. The workflow
      resolves the ref for its own commit (`ci_images.py ref agent`) and runs the loop inside it
      with `NOUS_API_KEY`/`GH_TOKEN` passed as run-time env — the same thing `make fix-loop-image`
      does locally. Verified by building through the registry's own path (`ensure agent`), which
      is the flat build context CI uses.
- [x] 7c. `tests/test_ci_images.py` gained the first-publish case: a missing registry cache ref
      must not break the build (`--cache-from` only when the cache exists), and the Dockerfile
      COPYs the flat context name CI provides.
- [x] 8. `tests/test_fix_loop.py` (real loop, stub agent on PATH): rounds, early stop, loud
      give-up, misconfiguration, the rules reaching the agent, and "no git mutation".
- [x] 9. Wire the test into the test recipes and add `make fix-loop` as the local entry point.
- [x] 10. Verify: `make lint`, `make check-wiring`, both workflows parse, the fix-loop tests
      green, `make openspec-validate NAME=pr-fix-bot` valid.
- [x] 11. Commit as one atomic change, push, open the PR against `asimov-agent/llgenie` linking
      #222, and stop there for review (never merge).
