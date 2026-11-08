# ci-verdict own-workflow and cancelled-auto-merge rows — tasks

- [x] exclude rows whose workflow FILE is the verdict's own `.github/workflows/ci-verdict.yml` from
      `unjudged_reds` (by FILE, not by CHECK_NAME)
- [x] exempt an auto-merge row with `conclusion=cancelled` from `unjudged_reds`; keep any other
      auto-merge blocking conclusion red
- [x] derive the posted check-run `output.title` from the posted conclusion (green only when success)
- [x] tests: own-judge rows excluded, cancelled auto-merge excluded, real auto-merge failure red,
      title never `green` beside a non-success conclusion (green-head variant)
- [x] guard-prove: with the fix reverted, the new tests red; with the fix, green
- [x] measured: `make ci-verdict RUN_ID=42460411318` posts success (not failure) for the green judged
      run at `07a7db2a`
- [x] change-note trio (agent-wiki + docs/changes.d + CHANGES.md) keyed to #2221
- [x] openspec validate passes; PR body carries Issue:/Fix:/Benefit:/Technical: and `closes #2221`
