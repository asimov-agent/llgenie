# Tasks

- [x] Reproduce the refused-write death: a fake `gh` whose label POST exits 1 with `HTTP 403`
      reds the change-issue step (run 42362469027, Makefile:337) — measured at head 6940f9e7
- [x] `registry_change_issue.set_labels` catches the credential-refused write (HTTP 403 /
      `not accessible by personal access token`): prints one loud `stderr` line naming the
      issue + reason and returns, so the leg survives and the sync-PR step still runs
- [x] Every other gh failure still raises; the silently-dropped-write redis the step via
      `SystemExit` naming issue + missing label (the #819 red, unchanged)
- [x] Guard proved: the new refused-write regression test FAILS on the pre-fix script and
      PASSES on the fixed one; existing `test_a_change_issue_that_cannot_be_labelled_fails_the_step`
      still passes
- [x] `make check-registry` green at head (the #1981 store follow resolved defect (a); store
      unchanged) and `make openspec-validate NAME=fix-registry-sync-label-refusal` passes
- [x] change-note + openspec scaffold + one atomic commit pushed; PR opened closing #775
