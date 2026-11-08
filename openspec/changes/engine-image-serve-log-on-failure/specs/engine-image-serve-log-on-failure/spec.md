## ADDED Requirements

### Requirement: a served engine that fails must print its own log before the container is removed

When a served engine does not become ready, or exits early, the runner SHALL capture and print the
engine's in-container serve log and the container's stdout tail BEFORE the container is removed.

`engine_runner.py serve` redirects the engine's real output to `$TMPDIR/engine-runner-serve.log`
inside the container, so `docker logs` carries only the launcher banner. The caller removes the
container in a `finally`, so without this capture the only evidence of why an engine failed is
destroyed before anyone reads it (issue #2080; measured run `42428390792`, job `128571645259`).

#### Scenario: a readiness timeout prints the serve log

- **GIVEN** a served engine that never becomes ready within the readiness bound
- **WHEN** the runner gives up
- **THEN** it prints the in-container serve log and the `docker logs` tail before returning 1
- **Test:** `tests/test_engine_image_serve_log.py`

#### Scenario: an engine that produced no output is named as such

- **GIVEN** a served engine whose serve log is empty or absent
- **WHEN** the runner reports the failure
- **THEN** it states `EMPTY/absent (no engine output captured)` rather than reporting nothing
- **Test:** `tests/test_engine_image_serve_log.py`

#### Scenario: an engine that exits early prints the same evidence

- **GIVEN** a served engine whose container exits before the readiness bound
- **WHEN** the runner detects the exit
- **THEN** it prints the serve log and the container tail before returning 1
- **Test:** `tests/test_engine_image_serve_log.py`

### Requirement: the capture weakens no gate and moves no image tag

The capture SHALL NOT change the readiness bound, the failure assertion, or the exit code, and SHALL
NOT touch any image-tag input, so that no engine is re-tagged or re-published by a diagnostics change.

#### Scenario: a failed serve still fails

- **GIVEN** a served engine that does not become ready
- **WHEN** the runner completes
- **THEN** it still returns 1 under the same bound as before the change
- **Test:** `tests/test_engine_image_serve_log.py`
