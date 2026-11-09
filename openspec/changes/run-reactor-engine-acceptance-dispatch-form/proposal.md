# run-reactor-engine-acceptance-dispatch-form — an engine-build acceptance criterion names the dispatch run, never a local build

## Why

Every issue the run-failure reactor filed for a failing `engine-build` cell asked the implementer to
satisfy an acceptance criterion no legitimate fix can meet: "the failing make target is green locally
on this host, with its real output recorded".

For an ENGINE-lane failure that wording demands a LOCAL build of an inference-server engine image,
which this repository forbids:

- AGENTS.md — "Inference servers run ONLY in their container images"
- `agents/llgenie-engine-improver/SOUL.md` — "Never build an inference-server engine image locally"

and for a GPU cell the local build is impossible anyway. The acceptance gate therefore redded the
engine-build lane's fix PR on a line its own rules make unsatisfiable. The provable form is a REAL
RUN of the failing cell — the single-cell `engine-build` dispatch CI owns — with that cell's own log
recorded.

## What changes

- `scripts/run_failure_reactor.py::issue_body` — the `engine-build` acceptance template states the
  provable form: "the failing cell is green in a real run of the failing cell, with its own log
  recorded". The engine branch is selected by `is_engine = lane == ENGINE_LANE`; non-engine failures
  keep the existing local-build wording.
- `scripts/check_pr_acceptance.py` — when an unticked criterion names a local build (`LOCAL_BUILD`),
  the `acceptance-unchecked` / `acceptance-proven-awaiting-writer` finding appends the dispatch form
  (`DISPATCH_FORM` / `local_build_hint`), so the implementer sees the correct restatement in the gate
  log.
- Regression tests in `tests/test_run_failure_reactor.py` and
  `tests/test_check_pr_acceptance.py` that FAIL on the old "locally on this host" wording and PASS on
  the new run form.

## Impact

- A future engine-build failure issue needs no hand restatement of criterion 1: the reactor renders
  the dispatch form itself.
- No engine image is built anywhere in this change; no `enforce_events` movement; the security-scan
  gate is untouched.
