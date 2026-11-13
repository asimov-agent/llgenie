# Salvage audit degradation without `gh`

## ADDED Requirements

### Requirement: the salvage audit degrades gracefully where `gh` is absent

`salvage-four-bucket.py` must never raise an uncaught exception because the `gh` binary is
missing: its `run()` seam treats `OSError` (including `FileNotFoundError`) like any other failed
call, and when `gh` cannot be found the audit prints a degraded note stating that PR identity
could not be checked and that orphan tips are classified conservatively, then completes the
git-only audit with exit code 0.

#### Scenario: the audit runs inside the gh-less test container

Given the unit-test container (which ships no `gh`) with the repo mounted,
when `salvage-four-bucket.py` is run without arguments,
then it exits rc=0, prints no `Traceback`, and its output carries the degraded note.

#### Scenario: a missing gh is proven by a regression test

Given `PATH` reduced so `shutil.which("gh")` finds nothing,
when the shipped script is executed,
then a test asserts rc=0, the degraded note, and the absence of a traceback, so the crash class
stays covered.
