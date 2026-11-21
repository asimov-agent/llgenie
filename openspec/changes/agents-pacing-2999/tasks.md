# Tasks — agents-pacing-2999

- [x] 1. AGENTS.md "Host-side task pacing" gains the continuous-lane rule: a pushed
      lane with CI in flight is DONE for scheduling; the next foreground action is the
      next board issue; CI re-polls live only in the background watcher; idle poll/sleep
      chains are a citable pacing violation.
- [x] 2. Docs gates pass with the new rule + work record indexed (issue #2999).
- [x] 3. `make openspec-validate NAME=agents-pacing-2999` exits 0.

Shipping steps (outside the tracked checklist): `make lane-preflight`, push, PR.
