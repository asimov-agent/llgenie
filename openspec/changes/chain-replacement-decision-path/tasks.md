# Tasks: chain-replacement-decision-path

- [x] OpenSpec change `chain-replacement-decision-path` created + validated + committed first
- [x] `issue_text` renders the four-step decision path in `How we fix it` (name one candidate →
      record the choice → own closing PR lane → post-landing check)
- [x] `issue_text` lists per-member `:free` drop-in candidates with published budgets >= the
      member's committed context_window (or "no drop-in") in the Technical section
- [x] Tests prove: dry-run body carries the decision path steps; a synthetic retired member gets
      a named drop-in candidate; `compare()` FINDING lines and exit codes unchanged
- [x] Live proof: `make check-agent-model-catalog` rc=0 against the live catalog; DRY fixture rc=1
      with the decision-path body printed
- [x] agent-wiki entry + docs/changes.d fragment + CHANGES.md row; gates green
- [x] Final alignment: issue #2939 body, PR body, and commit text carry identical ticked ACs
      (verified by reading all three), ticked the moment proven
