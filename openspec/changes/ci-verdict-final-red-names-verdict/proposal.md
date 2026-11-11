# ci-verdict-final-red-names-verdict

## Why

Issue #2222 (measured on run 42454987236, whose `judge` job reddened): the
`ci-verdict` step's OWN final line contradicts the verdict it just printed. A run
whose judged run genuinely FAILED (`linux/unit FAILED`, `verdict=red` in the summary)
still ended with the stderr line

```
[ci-verdict] FAILED: run 42454987236 has no verdict — see the summary line above...
```

"has no verdict" is only true when the verdict is `none`. For `red` the run HAS a
verdict — it is red, and the `RED: 1 job(s) FAILED (linux/unit)` summary line already
names the cause. #2279 fixed the summary's own misstatement (`NO VERDICT: ... 0
failures` beside a real failure) but never touched `scripts/ci_verdict.py`'s final
stderr line, which still fires the same `no verdict` wording for every red exit. A
board quoting the LAST line of a red verdict reads "has no verdict".

## What Changes

`scripts/ci_verdict.py::main`'s final `FAILED:` stderr line becomes verdict-aware:

- verdict `red` → the run HAS a verdict and it is red: `FAILED: run <id> is RED — N
  job(s) FAILED (<cause>); see the summary line above, which names them`. Never
  "has no verdict".
- verdict `none` → keep the #1111 wording exactly: `FAILED: run <id> has no verdict
  — see the summary line above, which is what a board must quote instead of a failure
  count`. This is the only case where "no verdict" is true.
- verdict `green` forced RED by `unjudged_reds` → the judged run is green but the head
  carries blocking unjudged check-runs: the final line says so and points at the
  UNJUDGED RED lines, never "no verdict".

Exit codes, the verdict, `counts`, the summary lines and the check-run payload are
untouched; this is a message-only change to the final stderr line, mirroring #2279.

## Impact

- **who**: every board or triager that quotes the LAST line of a red `ci-verdict`
  judge run (the run-failure reactor's log tail, `gh run view --log-failed`).
- **what**: a red verdict reads "is RED … FAILED (<jobs>)" instead of "has no verdict"
  beside the very failure it names.
- **regression surface**: tests pin the new RED line and the unchanged NONE line; the
  existing 57-test `tests/test_ci_verdict.py` suite stays green (verdict/counts/exit
  code byte-identical, since only the final message text changes).
