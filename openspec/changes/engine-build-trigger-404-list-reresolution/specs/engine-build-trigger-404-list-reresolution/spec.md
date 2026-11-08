## ADDED Requirements

### Requirement: a 404 on the single-run endpoint is re-resolved from the run list

The engine-build trigger SHALL NOT treat a 404 from the single-run endpoint
(`/actions/runs/<id>`) as "the producer has not concluded". It SHALL re-resolve the same run from
the run-LIST endpoint before deciding, because that endpoint is readable earlier than the run's own
resource and the run may already have concluded (issue #2059).

A 404 response body parses as `{"message":"Not Found","status":"404"}`, whose `status` matches none
of the await loop's terminal branches — so the pre-change code polled the full wall-clock bound and
failed a green build on a visibility race.

#### Scenario: a producer that 404s then is visible concludes as success

- **GIVEN** a dispatched producer run
- **AND** the single-run endpoint answers 404 for it
- **AND** the run list reports that same run as `completed`/`success`
- **WHEN** the trigger awaits the producer's verdict
- **THEN** the wait concludes successfully with the resolved run id named
- **AND** it does not run to the wall-clock bound
- **Test:** `tests/test_engine_build_trigger.py` (the 404-then-visible regression test)

#### Scenario: a run invisible on both endpoints still fails at the bound

- **GIVEN** a dispatched producer run that answers 404 on the single-run endpoint
- **AND** is absent from the run list
- **WHEN** the await loop reaches its wall-clock bound
- **THEN** the wait fails, and the message names that the last known status was `404`
- **Test:** `tests/test_engine_build_trigger.py` (the instant-expiry test)

### Requirement: the 404 failure message distinguishes a poll race from a real expiry

The trigger's failure message SHALL name whether the producer's last known status was `404`, so a
reader can tell a poll-visibility race from a genuine build-conclusion expiry.

#### Scenario: the expiry message carries the last status

- **GIVEN** a producer run whose only known status is `404`
- **WHEN** the wait bound expires
- **THEN** the failure message includes `last status 404`
- **Test:** `tests/test_engine_build_trigger.py` (the instant-expiry assertion on the message)
